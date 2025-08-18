# ======================================================================================
# File: bot/services/ai_content_service.py
# Version: "Distinguished Engineer" — MAX Build (Aug 16, 2025)
# Description:
#   Unified AI service with OpenAI (primary) + Google Gemini (fallback) and
#   Gemini-Vision support for image moderation / OCR-ish extraction / spam heuristics.
#   - OpenAI used if OPENAI_API_KEY present; Gemini otherwise / on fallback.
#   - JSON mode helpers, summarization, consultant answers.
#   - Vision:
#       • analyze_image()   -> text or JSON (schema) using Gemini 1.5 (pro/flash)
#       • moderate_text()   -> lightweight heuristics + (optionally) OpenAI if present
#       • spam_score_image()-> 0..1 heuristic score for spammy images (stickers/promo)
#   - Safe, backoff'ed Google calls; no blocking I/O in event loop.
# ======================================================================================

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
from typing import Any
from collections.abc import Sequence

import backoff

# ---- OpenAI (primary) ---------------------------------------------------------
try:
    from openai import OpenAI  # SDK v1+
    from openai import APIConnectionError, RateLimitError, APIStatusError
except Exception:  # noqa: BLE001
    OpenAI = None  # type: ignore[assignment]
    APIConnectionError = RateLimitError = APIStatusError = Exception  # type: ignore[misc,assignment]

# ---- Google Gemini (fallback) -------------------------------------------------
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from google.generativeai.types import GenerationConfig

from bot.config.settings import Settings, AIConfig

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------


def _clip(s: str, n: int = 4000) -> str:
    return s if len(s) <= n else (s[: n - 1] + "…")


def _is_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://") or s.startswith("tg://")


def _guess_mime_from_bytes(b: bytes) -> str:
    # very light signature sniffing; default to PNG (Telegram often gives JPEG/WEBP too)
    if b[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if b[:4] == b"RIFF" and b[8:12] in (b"WEBP",):
        return "image/webp"
    return "image/png"


# --------------------------------------------------------------------------------------
# AIContentService
# --------------------------------------------------------------------------------------


class AIContentService:
    """
    Unified wrapper around OpenAI (primary) and Google Gemini (fallback).
    Also provides Gemini-Vision utilities for image analysis and spam detection.
    """

    # ------------------------------ lifecycle ---------------------------------

    def __init__(
        self,
        settings: Settings | None = None,
        ai_config: AIConfig | None = None,
    ) -> None:
        self.settings = settings
        self.config: AIConfig = ai_config or (settings.ai if settings else AIConfig())

        # ---------- OpenAI (primary) ----------
        self.oai_client = None
        self.oai_model = (
            os.getenv("OPENAI_MODEL")
            or getattr(self.config, "openai_model", None)
            or "gpt-4o-mini"
        )
        oai_key = os.getenv("OPENAI_API_KEY")
        if OpenAI and oai_key:
            try:
                self.oai_client = OpenAI(api_key=oai_key)
                logger.info(
                    "AIContentService: OpenAI initialized (model=%s).", self.oai_model
                )
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "AIContentService: failed to init OpenAI: %s", e, exc_info=True
                )
                self.oai_client = None
        else:
            if not OpenAI:
                logger.info(
                    "AIContentService: `openai` package not installed — Gemini only."
                )
            else:
                logger.info("AIContentService: OPENAI_API_KEY not set — Gemini only.")

        # ---------- Google Gemini (fallback) ----------
        self._gemini_enabled = False
        self.gemini_pro = None
        self.gemini_flash = None
        g_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        self.gemini_model_name = getattr(
            self.config, "model_name", "gemini-1.5-pro-latest"
        )
        self.gemini_flash_name = getattr(
            self.config, "flash_model_name", "gemini-1.5-flash-latest"
        )
        if g_key:
            try:
                genai.configure(api_key=g_key)
                # IMPORTANT: do not pass tools in constructor, it triggers field validation errors
                self.gemini_pro = genai.GenerativeModel(self.gemini_model_name)
                self.gemini_flash = genai.GenerativeModel(self.gemini_flash_name)
                self._gemini_enabled = True
                logger.info(
                    "AIContentService: Gemini initialized (pro=%s, flash=%s).",
                    self.gemini_model_name,
                    self.gemini_flash_name,
                )
            except Exception as e:  # noqa: BLE001
                logger.critical(
                    "AIContentService: Gemini init failed — disabled fallback: %s",
                    e,
                    exc_info=True,
                )
                self._gemini_enabled = False
        else:
            logger.info(
                "AIContentService: GOOGLE_API_KEY/GEMINI_API_KEY not set — Gemini disabled."
            )

    async def close(self) -> None:
        """For symmetry with other services; nothing to close explicitly here."""
        return None

    # ------------------------------ internals ---------------------------------

    @staticmethod
    def _extract_text(resp: Any) -> str:
        return (getattr(resp, "text", None) or "").strip()

    @staticmethod
    def _format_history(history: list[Any] | None) -> list[dict[str, str]]:
        """
        Normalize to OpenAI-compatible messages: [{role, content}, ...]
        Supports:
          - list[str]
          - list[dict{role:str, content:str}]
        """
        if not history:
            return []
        msgs: list[dict[str, str]] = []
        for h in history:
            if isinstance(h, str):
                msgs.append({"role": "user", "content": h.strip()})
            elif isinstance(h, dict):
                role = str(h.get("role", "user")).strip() or "user"
                content = str(h.get("content", "")).strip()
                if content:
                    msgs.append({"role": role, "content": content})
            else:
                msgs.append({"role": "user", "content": str(h).strip()})
        return msgs[-10:]

    # ---- OpenAI helpers ----

    async def _oai_chat(
        self,
        *,
        system_prompt: str | None,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        if not self.oai_client:
            raise RuntimeError("OpenAI client is not initialized")
        oai_messages: list[dict[str, str]] = []
        if system_prompt:
            oai_messages.append({"role": "system", "content": system_prompt})
        oai_messages.extend(messages)

        def _call():
            return self.oai_client.chat.completions.create(
                model=self.oai_model,
                messages=oai_messages,
                temperature=temperature
                if temperature is not None
                else self.config.default_temperature,
            )

        resp = await asyncio.to_thread(_call)
        try:
            return (resp.choices[0].message.content or "").strip()
        except Exception:  # noqa: BLE001
            return ""

    async def _oai_json(
        self, *, system_prompt: str | None, user_prompt: str
    ) -> dict[str, Any] | None:
        if not self.oai_client:
            raise RuntimeError("OpenAI client is not initialized")
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        def _call():
            return self.oai_client.chat.completions.create(
                model=self.oai_model,
                messages=messages,
                temperature=0,
                response_format={"type": "json_object"},
            )

        resp = await asyncio.to_thread(_call)
        raw = ""
        try:
            raw = resp.choices[0].message.content or ""
            return json.loads(raw)
        except Exception:  # noqa: BLE001
            try:
                s = raw.strip()
                i, j = s.find("{"), s.rfind("}")
                if i != -1 and j != -1 and j >= i:
                    return json.loads(s[i : j + 1])
            except Exception:
                pass
            return None

    # ---- Gemini helpers ----

    @backoff.on_exception(
        backoff.expo,
        (
            google_exceptions.GoogleAPIError,
            google_exceptions.RetryError,
            google_exceptions.ResourceExhausted,
        ),
        max_tries=3,
    )
    async def _gemini_request(
        self,
        model: Any,
        *,
        contents: Any,
        generation_config: GenerationConfig | None = None,
        use_search: bool = False,
    ) -> Any:
        if model is None:
            raise RuntimeError("Gemini model is not initialized")

        tools = None
        if use_search:
            try:
                Tool = genai.protos.Tool
                GoogleSearch = genai.protos.GoogleSearch
                tools = [Tool(google_search=GoogleSearch())]
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "Gemini: failed to construct google_search tool: %s — proceed without.",
                    e,
                )
                tools = None

        if hasattr(model, "generate_content_async"):
            return await model.generate_content_async(
                contents=contents, tools=tools, generation_config=generation_config
            )
        return await asyncio.to_thread(
            model.generate_content,
            contents=contents,
            tools=tools,
            generation_config=generation_config,
        )

    # ----------------------------------------------------------------------------------
    # Public text helpers
    # ----------------------------------------------------------------------------------

    async def generate_summary(self, text_to_summarize: str) -> str:
        """Short RU summary in 3–4 bullets. GPT → (fallback) Gemini."""
        system_prompt = "Суммируй кратко и по-русски следующий текст в 3–4 пунктах."
        if self.oai_client:
            try:
                return await self._oai_chat(
                    system_prompt=system_prompt,
                    messages=[{"role": "user", "content": text_to_summarize}],
                    temperature=0.3,
                )
            except (APIConnectionError, RateLimitError, APIStatusError, Exception) as e:  # noqa: BLE001
                logger.warning(
                    "OpenAI summary failed (%s). FALLBACK → Gemini.", e, exc_info=True
                )

        if self._gemini_enabled:
            try:
                model = self.gemini_flash or self.gemini_pro
                resp = await self._gemini_request(
                    model, contents=f"{system_prompt}\n\n{text_to_summarize}"
                )
                return self._extract_text(resp) or ""
            except Exception as e:  # noqa: BLE001
                logger.error("Gemini summary failed: %s", e, exc_info=True)
        return ""

    async def get_structured_response(
        self,
        prompt: str,
        json_schema: dict[str, Any],
        *,
        use_grounding: bool = False,
        system_prompt: str | None = None,
        **_: Any,
    ) -> dict[str, Any] | None:
        """Strict JSON by schema. GPT JSON-mode → (fallback) Gemini JSON via response_mime_type."""
        if self.oai_client:
            try:
                oai_system = (system_prompt or "").strip()
                oai_prompt = (
                    "Сформируй JSON строго по следующей схеме (без комментариев и Markdown).\n"
                    f"Схема-подсказка: {json.dumps(json_schema, ensure_ascii=False)}\n\n"
                    f"Задание:\n{prompt}"
                )
                data = await self._oai_json(
                    system_prompt=oai_system or "Ты генерируешь только валидный JSON.",
                    user_prompt=oai_prompt,
                )
                if data is not None:
                    return data
            except (APIConnectionError, RateLimitError, APIStatusError, Exception) as e:  # noqa: BLE001
                logger.warning(
                    "OpenAI structured failed (%s). FALLBACK → Gemini.",
                    e,
                    exc_info=True,
                )

        if self._gemini_enabled:
            try:
                model = self.gemini_flash or self.gemini_pro
                gen_cfg = GenerationConfig(response_mime_type="application/json")
                sys_txt = (system_prompt or "").strip()
                full_prompt = f"{sys_txt}\n\n{prompt}" if sys_txt else prompt
                full_prompt += (
                    "\n\nОтветь ТОЛЬКО корректным JSON без комментариев и Markdown.\n"
                    f"Схема (пример): {json.dumps(json_schema, ensure_ascii=False)}"
                )
                resp = await self._gemini_request(
                    model,
                    contents=full_prompt,
                    generation_config=gen_cfg,
                    use_search=use_grounding,
                )
                text = self._extract_text(resp)
                if not text:
                    return None
                s = text.strip()
                i, j = s.find("{"), s.rfind("}")
                if i != -1 and j != -1 and j >= i:
                    s = s[i : j + 1]
                return json.loads(s)
            except Exception as e:  # noqa: BLE001
                logger.error("Gemini structured failed: %s", e, exc_info=True)
        return None

    async def generate_structured_content(
        self,
        prompt: str,
        json_schema: dict[str, Any],
        *,
        system_prompt: str | None = None,
    ) -> dict[str, Any] | None:
        return await self.get_structured_response(
            prompt, json_schema, use_grounding=False, system_prompt=system_prompt
        )

    async def get_consultant_answer(
        self,
        user_text: str,
        history: list[Any] | None = None,
        *,
        system_prompt: str | None = None,
        use_grounding: bool = False,
        temperature: float | None = None,
    ) -> str:
        """Longer RU assistant answer. GPT → (fallback) Gemini."""
        messages = self._format_history(history)
        messages.append({"role": "user", "content": (user_text or "").strip()})

        if self.oai_client:
            try:
                return await self._oai_chat(
                    system_prompt=system_prompt
                    or "Ты — помощник по криптовалютам и майнингу. Отвечай лаконично и по-русски.",
                    messages=messages,
                    temperature=temperature
                    if temperature is not None
                    else self.config.default_temperature,
                )
            except (APIConnectionError, RateLimitError, APIStatusError, Exception) as e:  # noqa: BLE001
                logger.warning(
                    "OpenAI consultant failed (%s). FALLBACK → Gemini.",
                    e,
                    exc_info=True,
                )

        if self._gemini_enabled:
            try:
                model = self.gemini_flash or self.gemini_pro
                sys_preamble = (
                    system_prompt
                    or "Ты — помощник по криптовалютам и майнингу. Отвечай лаконично и по-русски."
                )
                history_block = (
                    "\n".join(f"{m['role']}: {m['content']}" for m in messages[:-1])
                    if messages[:-1]
                    else ""
                )
                prompt_parts = [sys_preamble]
                if history_block:
                    prompt_parts.append(
                        "Контекст диалога:\n" + _clip(history_block, 6000)
                    )
                prompt_parts.append(
                    "Вопрос пользователя:\n" + _clip(user_text or "", 6000)
                )
                full_prompt = "\n\n".join(p for p in prompt_parts if p)

                gen_cfg = GenerationConfig(
                    temperature=temperature
                    if temperature is not None
                    else self.config.default_temperature
                )
                resp = await self._gemini_request(
                    model,
                    contents=full_prompt,
                    generation_config=gen_cfg,
                    use_search=use_grounding,
                )
                return self._extract_text(resp)
            except Exception as e:  # noqa: BLE001
                logger.error("Gemini consultant failed: %s", e, exc_info=True)

        return ""

    # ----------------------------------------------------------------------------------
    # Vision: Gemini 1.5 (pro/flash)
    # ----------------------------------------------------------------------------------

    def _to_gemini_image_part(
        self, image: bytes | str | dict[str, Any]
    ) -> dict[str, Any]:
        """
        Convert input to Gemini image part:
          - bytes -> {"mime_type": "...", "data": bytes}
          - str(URL) -> {"mime_type":"image/png","data": <not fetched>}  # we DO NOT fetch URLs here
          - dict -> returned as-is if has mime_type+data
        NOTE: No network I/O here. Upstream should download Telegram file to bytes.
        """
        if isinstance(image, dict) and "mime_type" in image and "data" in image:
            return image
        if isinstance(image, bytes):
            return {"mime_type": _guess_mime_from_bytes(image), "data": image}
        if isinstance(image, str):
            # Do not fetch URL here (no requests in event loop).
            # Encourage upstream to provide bytes.
            logger.warning(
                "Gemini-Vision: URL string provided, but no fetching is performed. Provide bytes instead."
            )
            # Put a tiny placeholder so API doesn't fail hard:
            b = base64.b64decode(
                b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAH9gK1zD8tswAAAABJRU5ErkJggg=="
            )
            return {"mime_type": "image/png", "data": b}
        raise TypeError("Unsupported image type; expected bytes|dict|str(URL)")

    async def analyze_image(
        self,
        prompt: str,
        images: Sequence[bytes | str | dict[str, Any]],
        *,
        response_json_schema: dict[str, Any] | None = None,
        use_grounding: bool = False,
        temperature: float = 0.2,
        max_output_tokens: int = 2048,
    ) -> str | dict[str, Any]:
        """
        Analyze one or multiple images with Gemini-Vision (1.5). Returns TEXT or JSON.

        Args:
            prompt: task instruction in RU (or any).
            images: list of image bytes (preferred) or dict parts {"mime_type","data"}.
            response_json_schema: if provided, service will request JSON and parse it.
            use_grounding: enable GoogleSearch grounding tool.
            temperature: sampling temperature.
            max_output_tokens: upper bound for response size.

        Returns:
            str (text) or dict (parsed JSON).
        """
        if not self._gemini_enabled:
            raise RuntimeError("Gemini is not configured — cannot run vision.")

        parts: list[Any] = [prompt]
        for img in images:
            parts.append(self._to_gemini_image_part(img))

        gen_cfg = GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_mime_type="application/json" if response_json_schema else None,
        )
        model = self.gemini_flash or self.gemini_pro
        resp = await self._gemini_request(
            model, contents=parts, generation_config=gen_cfg, use_search=use_grounding
        )
        text = self._extract_text(resp)

        if response_json_schema:
            if not text:
                return {}
            s = text.strip()
            i, j = s.find("{"), s.rfind("}")
            if i != -1 and j != -1 and j >= i:
                s = s[i : j + 1]
            try:
                data = json.loads(s)
            except Exception:  # noqa: BLE001
                # Very defensive: wrap into schema root if it looks like array/other
                try:
                    if s.startswith("[") and s.endswith("]"):
                        data = {"items": json.loads(s)}
                    else:
                        data = {"raw": s}
                except Exception:
                    data = {"raw": s}
            return data

        return text

    # ----------------------------------------------------------------------------------
    # Heuristics / Moderation
    # ----------------------------------------------------------------------------------

    async def moderate_text(self, text: str) -> dict[str, Any]:
        """
        Lightweight moderation (heuristic). If OpenAI available, try to use it for a richer signal
        in a budget-friendly manner; otherwise use regex-based flags.
        """
        flags = {
            "links": bool(re.search(r"https?://|t\.me/|@[\w\d_]{3,32}", text, re.I)),
            "mentions": bool(re.search(r"@[\w\d_]{3,32}", text)),
            "promo": bool(
                re.search(
                    r"(free|бесплатн|скидк|прибыль|доход|guarantee|x\d+|pump|airdrops?)",
                    text,
                    re.I,
                )
            ),
            "scam": bool(
                re.search(
                    r"(giveaway|розыгрыш|раздач|купи|вложи|инвестируй|депозит|капитал|доход\s*\d+%|\d+%\s*в\s*день)",
                    text,
                    re.I,
                )
            ),
        }
        score = sum(0.15 for v in flags.values() if v)
        result = {"score": min(1.0, score), "flags": flags, "provider": "heuristic"}

        # Optional OpenAI moderation (very short budget call, wrapped)
        if self.oai_client:
            try:
                # Craft tiny prompt to classify risk 0..1 quickly
                sys = "Return a single JSON with keys {score: float in [0,1], reasons: string[]} based on spam/abuse risk."
                data = await self._oai_json(
                    system_prompt=sys, user_prompt=f"Text:\n{_clip(text, 4000)}"
                )
                if isinstance(data, dict) and "score" in data:
                    # Blend scores (max to be conservative)
                    result["score"] = max(
                        float(result["score"]), float(data.get("score", 0))
                    )
                    result["reasons"] = data.get("reasons", [])
                    result["provider"] = "openai+heuristic"
            except Exception as e:  # noqa: BLE001
                logger.debug("OpenAI moderation skip: %s", e)
        return result

    async def spam_score_image(
        self,
        *,
        caption: str = "",
        ocr_hint: str = "",
        images: Sequence[bytes | dict[str, Any] | str] = (),
    ) -> dict[str, Any]:
        """
        Heuristic spam scoring for images using Gemini-Vision (if configured).
        - Extracts brief semantic labels and promo cues (qr codes, urls, big digits).
        - Returns {score:0..1, cues:{...}, provider:str, raw?:dict}

        NOTE: No network fetching; pass image bytes from Telegram.
        """
        cues: dict[str, Any] = {
            "qr": False,
            "urls_on_image": False,
            "huge_digits": False,
            "promo_words_on_image": False,
            "caption_links": bool(re.search(r"https?://|t\.me/", caption, re.I)),
        }

        text_score = (
            (await self.moderate_text(caption)).get("score", 0.0) if caption else 0.0
        )

        if not self._gemini_enabled or not images:
            # fall back to text-only
            score = min(1.0, 0.4 + 0.6 * text_score) if text_score > 0 else 0.0
            return {"score": score, "cues": cues, "provider": "heuristic(text-only)"}

        try:
            schema = {
                "type": "object",
                "properties": {
                    "has_qr": {"type": "boolean"},
                    "has_urls": {"type": "boolean"},
                    "has_huge_digits": {"type": "boolean"},
                    "has_promo_words": {"type": "boolean"},
                    "short_labels": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "has_qr",
                    "has_urls",
                    "has_huge_digits",
                    "has_promo_words",
                ],
            }
            prompt = (
                "Проанализируй изображение(я) на предмет спама в Telegram.\n"
                "Отметь:\n- есть ли QR-код,\n- есть ли URL/хэндлы/теги,\n- есть ли крупные цифры (цены/выплаты/проценты),\n"
                "- встречаются ли слова 'акция', 'бесплатно', 'инвестируй', 'доход', 'гарантия', 'x10', 'заработок' и т.п.\n"
                "Верни краткий JSON."
            )
            data = await self.analyze_image(
                prompt, images, response_json_schema=schema, temperature=0.0
            )
            if isinstance(data, dict):
                cues["qr"] = bool(data.get("has_qr", False))
                cues["urls_on_image"] = bool(data.get("has_urls", False))
                cues["huge_digits"] = bool(data.get("has_huge_digits", False))
                cues["promo_words_on_image"] = bool(data.get("has_promo_words", False))

            # conservative scoring
            base = 0.0
            base += 0.35 if cues["qr"] else 0.0
            base += 0.25 if cues["urls_on_image"] else 0.0
            base += 0.15 if cues["huge_digits"] else 0.0
            base += 0.20 if cues["promo_words_on_image"] else 0.0
            score = min(1.0, base + 0.3 * text_score)
            return {"score": score, "cues": cues, "provider": "gemini-vision"}
        except Exception as e:  # noqa: BLE001
            logger.warning("Vision scoring failed: %s", e, exc_info=True)
            score = min(1.0, 0.4 + 0.6 * text_score) if text_score > 0 else 0.0
            return {"score": score, "cues": cues, "provider": "heuristic(fallback)"}
