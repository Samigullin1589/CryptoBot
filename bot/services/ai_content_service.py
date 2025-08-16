import asyncio
import base64
import io
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import backoff
from PIL import Image

# --- OpenAI (основной провайдер) ---
try:
    from openai import OpenAI  # SDK v1+
    from openai import APIConnectionError, RateLimitError, APIStatusError
except Exception:  # если SDK не установлен — работаем только с Gemini
    OpenAI = None  # type: ignore
    APIConnectionError = RateLimitError = APIStatusError = Exception  # type: ignore

# --- Google Gemini (резерв) ---
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from google.generativeai.types import GenerationConfig

from bot.config.settings import AIConfig

logger = logging.getLogger(__name__)


class AIContentService:
    """
    Унифицированная обёртка над OpenAI (GPT) и Google Gemini.

    ПРИОРИТЕТ ПОСТРОЕН ТАК:
    1) OpenAI (GPT) — ОСНОВНОЙ провайдер (если доступен OPENAI_API_KEY).
    2) Google Gemini — РЕЗЕРВ (если GPT недоступен/не сконфигурирован или вернул ошибку/лимит).

    Момент переключения на резерв ОТМЕЧЕН в коде комментариями:  # FALLBACK → Gemini
    Обратное переключение (с Gemini на GPT) не выполняем в рамках одного вызова.
    """

    def __init__(self, api_key: str, config: AIConfig) -> None:
        # Google API key приходит первым параметром (как в проекте)
        self.config = config

        # ---------- OpenAI (primary) ----------
        self.oai_client = None
        self.oai_model = os.getenv("OPENAI_MODEL") or getattr(config, "openai_model", None) or "gpt-4o-mini"
        oai_key = os.getenv("OPENAI_API_KEY")
        if OpenAI and oai_key:
            try:
                self.oai_client = OpenAI(api_key=oai_key)
                logger.info("AIContentService: OpenAI клиент инициализирован (модель: %s).", self.oai_model)
            except Exception as e:
                logger.warning("AIContentService: не удалось инициализировать OpenAI: %s", e, exc_info=True)
                self.oai_client = None
        else:
            if not OpenAI:
                logger.info("AIContentService: пакет openai не установлен — используем только Gemini как резерв.")
            else:
                logger.info("AIContentService: OPENAI_API_KEY не задан — используем только Gemini как резерв.")

        # ---------- Google Gemini (fallback) ----------
        self.gemini_pro = None
        self.gemini_flash = None
        self.gemini_model_name = getattr(config, "model_name", "gemini-1.5-pro")
        self.gemini_flash_name = getattr(config, "flash_model_name", "gemini-1.5-flash")
        self._gemini_enabled = False
        if api_key:
            try:
                genai.configure(api_key=api_key)
                # НЕ передаём tools в конструктор — это вызовет ошибку неизвестного поля.
                self.gemini_pro = genai.GenerativeModel(self.gemini_model_name)
                self.gemini_flash = genai.GenerativeModel(self.gemini_flash_name)
                self._gemini_enabled = True
                logger.info(
                    "AIContentService: Gemini клиенты инициализированы (pro=%s, flash=%s).",
                    self.gemini_model_name,
                    self.gemini_flash_name,
                )
            except Exception as e:
                logger.critical(
                    "AIContentService: не удалось инициализировать Gemini: %s — резерв отключён.",
                    e,
                    exc_info=True,
                )
                self._gemini_enabled = False
        else:
            logger.info("AIContentService: GOOGLE_API_KEY не задан — резервный Gemini недоступен.")

    # -------------------------- Вспомогательные --------------------------

    @staticmethod
    def _extract_text(resp: Any) -> str:
        return (getattr(resp, "text", None) or "").strip()

    @staticmethod
    def _format_history(history: Optional[List[Any]]) -> List[Dict[str, str]]:
        """
        Историю приводим к OpenAI-совместимому формату messages: [{role, content}, ...]
        Поддерживает:
          - список строк
          - список диктов вида {'role': 'user'|'assistant'|'system', 'content': '...'}
        """
        if not history:
            return []
        msgs: List[Dict[str, str]] = []
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
        # ограничим контекст
        return msgs[-20:]

    @staticmethod
    def _strip_json_from_text(s: str) -> Optional[Dict[str, Any]]:
        """
        Забираем JSON-объект из ответа модели (вырезаем по первому/последнему фигурным скобкам).
        """
        try:
            s = (s or "").strip()
            i, j = s.find("{"), s.rfind("}")
            if i != -1 and j != -1 and j >= i:
                return json.loads(s[i : j + 1])
        except Exception:
            return None
        return None

    @staticmethod
    def _pil_to_data_url(img: Image.Image) -> str:
        """
        Конвертирует PIL.Image -> data URL для OpenAI image_url.
        """
        buf = io.BytesIO()
        # Безопасный формат PNG (меньше артефактов)
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/png;base64,{b64}"

    # -------------------------- OpenAI helpers --------------------------

    async def _oai_chat(
        self,
        *,
        system_prompt: Optional[str],
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
    ) -> str:
        if not self.oai_client:
            raise RuntimeError("OpenAI client is not initialized")
        oai_messages: List[Dict[str, str]] = []
        if system_prompt:
            oai_messages.append({"role": "system", "content": system_prompt})
        oai_messages.extend(messages)

        # совместимость с SDK v1: client.chat.completions.create(...)
        def _call():
            return self.oai_client.chat.completions.create(
                model=self.oai_model,
                messages=oai_messages,
                temperature=temperature if temperature is not None else 0.6,
            )

        resp = await asyncio.to_thread(_call)
        try:
            return (resp.choices[0].message.content or "").strip()
        except Exception:
            return ""

    async def _oai_json(self, *, system_prompt: Optional[str], user_prompt: str) -> Optional[Dict[str, Any]]:
        if not self.oai_client:
            raise RuntimeError("OpenAI client is not initialized")
        messages: List[Dict[str, str]] = []
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
        except Exception:
            # попробуем выдрать JSON из строки на всякий случай
            try:
                s = raw.strip()
                i, j = s.find("{"), s.rfind("}")
                if i != -1 and j != -1 and j >= i:
                    return json.loads(s[i : j + 1])
            except Exception:
                pass
            return None

    async def _oai_vision_json(self, *, image: Image.Image, system_prompt: str) -> Optional[Dict[str, Any]]:
        """
        Вызов OpenAI Vision (через chat.completions) с возвратом JSON.
        Используем image_url (data URL) + response_format=json_object.
        """
        if not self.oai_client:
            raise RuntimeError("OpenAI client is not initialized")

        data_url = self._pil_to_data_url(image)
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Проанализируй изображение и верни JSON."},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ]

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
        except Exception:
            return self._strip_json_from_text(raw)

    # -------------------------- Gemini helpers --------------------------

    @backoff.on_exception(
        backoff.expo,
        (google_exceptions.GoogleAPIError, google_exceptions.RetryError, google_exceptions.ResourceExhausted),
        max_tries=3,
    )
    async def _gemini_request(
        self,
        model: Any,
        *,
        contents: Any,
        generation_config: Optional[GenerationConfig] = None,
        use_search: bool = False,
    ) -> Any:
        if model is None:
            raise RuntimeError("Gemini model is not initialized")

        tools = None
        if use_search:
            # Инкапсулированная безопасная сборка Tool(google_search)
            try:
                Tool = genai.protos.Tool
                GoogleSearch = genai.protos.GoogleSearch
                tools = [Tool(google_search=GoogleSearch())]
            except Exception as e:
                logger.warning("Gemini: не удалось сконструировать google_search tool: %s — продолжаем без grounding.", e)
                tools = None

        if hasattr(model, "generate_content_async"):
            return await model.generate_content_async(contents=contents, tools=tools, generation_config=generation_config)
        return await asyncio.to_thread(model.generate_content, contents=contents, tools=tools, generation_config=generation_config)

    # -------------------------- Публичные ТЕКСТОВЫЕ методы --------------------------

    async def generate_summary(self, text_to_summarize: str) -> str:
        """
        Краткое резюме текста. Пытается GPT → (FALLBACK) Gemini.
        """
        system_prompt = "Суммируй кратко и по-русски следующий текст в 3–4 пунктах."
        # 1) OpenAI (primary)
        if self.oai_client:
            try:
                return await self._oai_chat(
                    system_prompt=system_prompt,
                    messages=[{"role": "user", "content": text_to_summarize}],
                    temperature=0.3,
                )
            except (APIConnectionError, RateLimitError, APIStatusError, Exception) as e:  # noqa: BLE001
                logger.warning("OpenAI summary failed (%s). FALLBACK → Gemini.", e, exc_info=True)  # FALLBACK → Gemini

        # 2) Gemini (fallback)
        if self._gemini_enabled:
            try:
                model = self.gemini_flash or self.gemini_pro
                resp = await self._gemini_request(model, contents=f"{system_prompt}\n\n{text_to_summarize}")
                return self._extract_text(resp) or ""
            except Exception as e:  # noqa: BLE001
                logger.error("Gemini summary failed: %s", e, exc_info=True)
        return ""

    async def get_structured_response(
        self,
        prompt: str,
        json_schema: Dict[str, Any],
        *,
        use_grounding: bool = False,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> Optional[Dict[str, Any]]:
        """
        Возвращает строго JSON по заданной схеме.
        Сначала пробуем OpenAI JSON Mode → (FALLBACK) Gemini JSON (response_mime_type).
        Параметр system_prompt поддерживается.
        Прочие **kwargs игнорируются для совместимости со старыми вызовами.
        """
        # 1) OpenAI (primary)
        if self.oai_client:
            try:
                # Подскажем схему через инструкцию (JSON Mode всё равно заставит вернуть объект).
                oai_system = (system_prompt or "").strip()
                oai_prompt = (
                    "Сформируй JSON строго по следующей схеме (без комментариев и Markdown).\n"
                    f"Схема-подсказка: {json.dumps(json_schema, ensure_ascii=False)}\n\n"
                    f"Задание:\n{prompt}"
                )
                data = await self._oai_json(system_prompt=oai_system or "Ты генерируешь только валидный JSON.", user_prompt=oai_prompt)
                if data is not None:
                    return data
            except (APIConnectionError, RateLimitError, APIStatusError, Exception) as e:  # noqa: BLE001
                logger.warning("OpenAI structured failed (%s). FALLBACK → Gemini.", e, exc_info=True)  # FALLBACK → Gemini

        # 2) Gemini (fallback)
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
                resp = await self._gemini_request(model, contents=full_prompt, generation_config=gen_cfg, use_search=use_grounding)
                text = self._extract_text(resp)
                if not text:
                    return None
                data = self._strip_json_from_text(text)
                return data if isinstance(data, dict) else None
            except Exception as e:  # noqa: BLE001
                logger.error("Gemini structured failed: %s", e, exc_info=True)
        return None

    async def generate_structured_content(
        self,
        prompt: str,
        json_schema: Dict[str, Any],
        *,
        system_prompt: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        return await self.get_structured_response(
            prompt,
            json_schema,
            use_grounding=False,
            system_prompt=system_prompt,
        )

    async def get_consultant_answer(
        self,
        user_text: str,
        history: Optional[List[Any]] = None,
        *,
        system_prompt: Optional[str] = None,
        use_grounding: bool = False,
        temperature: Optional[float] = None,
    ) -> str:
        """
        Развёрнутый ответ консультанта. Порядок провайдеров:
        GPT (OpenAI) → (FALLBACK) Gemini.
        """
        # Историю приводим к messages
        messages = self._format_history(history)
        messages.append({"role": "user", "content": (user_text or "").strip()})

        # 1) OpenAI (primary)
        if self.oai_client:
            try:
                return await self._oai_chat(
                    system_prompt=system_prompt
                    or "Ты — помощник по криптовалютам и майнингу. Отвечай лаконично и по-русски.",
                    messages=messages,
                    temperature=temperature if temperature is not None else 0.6,
                )
            except (APIConnectionError, RateLimitError, APIStatusError, Exception) as e:  # noqa: BLE001
                logger.warning("OpenAI consultant failed (%s). FALLBACK → Gemini.", e, exc_info=True)  # FALLBACK → Gemini

        # 2) Gemini (fallback)
        if self._gemini_enabled:
            try:
                model = self.gemini_flash or self.gemini_pro
                sys_preamble = system_prompt or "Ты — помощник по криптовалютам и майнингу. Отвечай лаконично и по-русски."
                history_block = "\n".join(f"{m['role']}: {m['content']}" for m in messages[:-1]) if messages[:-1] else ""
                prompt_parts = [sys_preamble]
                if history_block:
                    prompt_parts.append("Контекст диалога:\n" + history_block)
                prompt_parts.append("Вопрос пользователя:\n" + (user_text or "").strip())
                full_prompt = "\n\n".join(p for p in prompt_parts if p)

                gen_cfg = GenerationConfig(temperature=temperature if temperature is not None else 0.6)
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

    # -------------------------- Публичные ВИЖН-методы --------------------------

    async def analyze_image_for_spam(self, image: Image.Image) -> Tuple[bool, str, str]:
        """
        Анализ изображения на рекламу/спам-баннеры/скам.
        Возвращает кортеж: (is_spam: bool, explanation: str, extracted_text: str)

        Приоритет: OpenAI-Vision → (FALLBACK) Gemini-Vision.
        Если ни один провайдер недоступен или оба упали — вернёт (False, "", "").
        """
        system = (
            "You are a strict content-moderation assistant.\n"
            "Classify if the image is likely to be an advertising spam banner for social/chat groups, "
            "casinos, betting, crypto giveaways, referral links, pump signals, or any deceptive promotion. "
            "Extract any visible text (OCR-like). "
            "Answer ONLY JSON with fields: "
            '{"is_spam": true|false, "explanation": "short reason in Russian", "extracted_text": "string"}'
        )

        # --- 1) OpenAI Vision (primary) ---
        if self.oai_client:
            try:
                data = await self._oai_vision_json(image=image, system_prompt=system)
                if isinstance(data, dict):
                    is_spam = bool(data.get("is_spam", False))
                    explanation = str(data.get("explanation", "")).strip()
                    extracted_text = str(data.get("extracted_text", "")).strip()
                    return is_spam, explanation, extracted_text
            except (APIConnectionError, RateLimitError, APIStatusError, Exception) as e:  # noqa: BLE001
                logger.warning("OpenAI vision failed (%s). FALLBACK → Gemini.", e, exc_info=True)

        # --- 2) Gemini Vision (fallback) ---
        if self._gemini_enabled:
            try:
                model = self.gemini_pro or self.gemini_flash  # vision лучше на pro
                resp = await self._gemini_request(model, contents=[system, image], generation_config=GenerationConfig(temperature=0))
                text = self._extract_text(resp)
                data = self._strip_json_from_text(text) if text else None
                if isinstance(data, dict):
                    is_spam = bool(data.get("is_spam", False))
                    explanation = str(data.get("explanation", "")).strip()
                    extracted_text = str(data.get("extracted_text", "")).strip()
                    return is_spam, explanation, extracted_text
                # эвристика, если JSON не распарсился
                lowered = (text or "").lower()
                is_spam = any(k in lowered for k in ("spam", "advert", "promotion", "casino", "bet", "referral", "scam", "реклама", "казино", "бет", "реферал"))
                return is_spam, (text or "")[:2000], ""
            except Exception as e:  # noqa: BLE001
                logger.error("Gemini vision failed: %s", e, exc_info=True)

        # --- 3) Нет провайдера / обе ветки сломались ---
        return False, "", ""