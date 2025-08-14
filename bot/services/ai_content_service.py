import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import backoff
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from google.api_core import exceptions as google_exceptions

from bot.config.settings import AIConfig

logger = logging.getLogger(__name__)


class AIContentService:
    """
    Безопасная обертка над google-generativeai.
    Важно: tools не передаются в конструктор модели. Grounding (Google Search) подключается на уровне запроса.
    """

    def __init__(self, api_key: str, config: AIConfig) -> None:
        self.config = config
        self.api_key = api_key
        self.pro_client = None
        self.flash_client = None

        if not api_key:
            logger.critical("AIContentService: API ключ не задан, сервис будет отключен.")
            return

        try:
            genai.configure(api_key=api_key)
            self.pro_client = genai.GenerativeModel(self.config.model_name)
            self.flash_client = genai.GenerativeModel(
                getattr(self.config, "flash_model_name", self.config.model_name)
            )
            logger.info("AIContentService: клиенты Gemini успешно инициализированы.")
        except Exception as e:
            logger.critical(
                "Не удалось инициализировать клиентов Gemini: %s. AI-функции отключены.", e, exc_info=True
            )
            self.pro_client = None
            self.flash_client = None

    @staticmethod
    def _extract_text(resp: Any) -> str:
        return (getattr(resp, "text", None) or "").strip()

    @backoff.on_exception(backoff.expo, (google_exceptions.GoogleAPIError, google_exceptions.RetryError), max_tries=3)
    async def _make_request(
        self,
        model: Any,
        *,
        contents: Any,
        generation_config: Optional[GenerationConfig] = None,
        use_search: bool = False,
    ) -> Any:
        if model is None:
            raise RuntimeError("AIContentService: модель не инициализирована")

        tools = None
        if use_search:
            try:
                Tool = genai.protos.Tool
                GoogleSearch = genai.protos.GoogleSearch
                tools = [Tool(google_search=GoogleSearch())]
            except Exception as e:
                logger.warning("Не удалось сконструировать Tool(google_search): %s — выполняем без grounding.", e)
                tools = None

        if hasattr(model, "generate_content_async"):
            return await model.generate_content_async(contents=contents, tools=tools, generation_config=generation_config)
        else:
            return await asyncio.to_thread(model.generate_content, contents=contents, tools=tools, generation_config=generation_config)

    async def generate_summary(self, text_to_summarize: str) -> str:
        model = self.flash_client or self.pro_client
        if not model:
            return ""
        prompt = f"Суммируй кратко и по-русски следующий текст в 3-4 пунктах:\n\n{text_to_summarize}"
        try:
            resp = await self._make_request(model, contents=prompt)
            return self._extract_text(resp) or ""
        except Exception as e:
            logger.error("Ошибка generate_summary: %s", e, exc_info=True)
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
        Запрашивает у модели строго валидный JSON согласно схеме json_schema.
        Совместимо с вызовами вида get_structured_response(..., system_prompt="...").
        Неиспользуемые **kwargs игнорируются.
        """
        model = self.flash_client or self.pro_client
        if not model:
            return None

        # Если задан system_prompt, добавим его перед пользовательским запросом.
        sys_txt = (system_prompt or "").strip()
        full_prompt = f"{sys_txt}\n\n{prompt}" if sys_txt else prompt

        gen_cfg = GenerationConfig(response_mime_type="application/json")
        try:
            full_prompt += (
                "\n\nОтветь ТОЛЬКО корректным JSON без комментариев и форматирования Markdown.\n"
                f"Схема JSON (пример): {json.dumps(json_schema, ensure_ascii=False)}"
            )
            resp = await self._make_request(
                model,
                contents=full_prompt,
                generation_config=gen_cfg,
                use_search=use_grounding,
            )
            text = self._extract_text(resp)
            if not text:
                return None
            # Пытаемся распарсить JSON; если модель добавила лишний текст — очищаем
            text_stripped = text.strip()
            start = text_stripped.find("{")
            end = text_stripped.rfind("}")
            if start != -1 and end != -1 and end >= start:
                text_stripped = text_stripped[start : end + 1]
            return json.loads(text_stripped)
        except Exception as e:
            logger.error("Ошибка get_structured_response: %s", e, exc_info=True)
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

    # ===================== НОВОЕ: консультативный ответ =====================

    @staticmethod
    def _format_history(history: Optional[List[Any]]) -> str:
        """
        Преобразует историю диалога в текст.
        Поддерживаются форматы:
          - список строк
          - список словарей {'role': 'user'|'assistant'|'system', 'content': '...'}
        """
        if not history:
            return ""
        lines: List[str] = []
        for h in history:
            if isinstance(h, str):
                lines.append(h.strip())
            elif isinstance(h, dict):
                role = str(h.get("role", "user")).strip()
                content = str(h.get("content", "")).strip()
                if content:
                    lines.append(f"{role}: {content}")
            else:
                # неизвестный тип — приводим к строке
                lines.append(str(h).strip())
        return "\n".join(lines[:20])  # ограничим контекст разумно

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
        Возвращает развернутый ответ ассистента для пользовательского текста.
        Совместимо с вызовом из common_handler: get_consultant_answer(user_text, history)
        """
        model = self.flash_client or self.pro_client
        if not model:
            return ""

        sys_preamble = (
            system_prompt
            or "Ты — помощник по криптовалютам и майнингу. Отвечай лаконично, по делу и по-русски."
        )
        history_block = self._format_history(history)
        prompt_parts = [sys_preamble]
        if history_block:
            prompt_parts.append("Контекст диалога:\n" + history_block)
        prompt_parts.append("Вопрос пользователя:\n" + (user_text or "").strip())
        full_prompt = "\n\n".join(p for p in prompt_parts if p)

        try:
            gen_cfg = GenerationConfig(
                temperature=temperature if temperature is not None else 0.6
            )
            resp = await self._make_request(
                model,
                contents=full_prompt,
                generation_config=gen_cfg,
                use_search=use_grounding,
            )
            return self._extract_text(resp)
        except Exception as e:
            logger.error("Ошибка get_consultant_answer: %s", e, exc_info=True)
            return ""
