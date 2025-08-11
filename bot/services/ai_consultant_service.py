# ===============================================================
# Файл: bot/services/ai_consultant_service.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Усовершенствованный сервис для AI-консультанта.
# Использует Gemini 1.5 Pro, актуализированный промпт для 2025 года
# и механизм повторных запросов для максимальной надежности.
# ===============================================================

import asyncio
import logging
from typing import List, Dict, Any

import aiohttp
from bot.config.config import settings # <-- ИСПРАВЛЕН ИМПОРТ

logger = logging.getLogger(__name__)

class AIConsultantService:
    """
    Сервис для получения экспертных ответов от Gemini API на вопросы пользователей.
    """
    def __init__(self, http_session: aiohttp.ClientSession):
        """
        Инициализирует сервис.
        
        :param http_session: Общий экземпляр aiohttp.ClientSession.
        """
        self.gemini_api_key = settings.GEMINI_API_KEY.get_secret_value()
        self.model_name = settings.ai.model_name
        self.max_retries = settings.ai.max_retries
        
        if not self.gemini_api_key:
            raise ValueError("Необходимо предоставить API-ключ Gemini.")
        
        self.session = http_session
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"
        self.headers = {'Content-Type': 'application/json'}
        self.params = {'key': self.gemini_api_key}

    def _create_system_prompt(self) -> str:
        """
        Создает и возвращает системный промпт, определяющий роль и поведение AI-консультанта.
        """
        return (
            "You are 'CryptoBot Co-Pilot', a world-class expert engineer in cryptocurrency and ASIC mining. Your tone is professional, helpful, and precise. "
            "Your expertise reflects the market conditions of mid-2025. This includes the post-halving dynamics of Bitcoin, the maturity of Layer-2 solutions (like Arbitrum, Optimism), the emergence of Layer-3s, and the growing trend of Real-World Asset (RWA) tokenization. "
            "Provide a comprehensive and well-structured answer in Russian to the user's latest question, using the provided conversation history for context. "
            "Structure your answer with clear headings (using bold text), bullet points, and `code` blocks for technical specifications or commands. "
            "Start the answer by directly addressing the user's question. "
            "Conclude your answer with a '<b>Вывод:</b>' (Conclusion) section that summarizes the key takeaway. "
            "If the question is a request for a recommendation (e.g., 'what is the most profitable'), provide an analytical comparison of 2-3 relevant options and explain the trade-offs, rather than giving a single answer. "
            "Always state that profitability depends on many variables (electricity cost, network difficulty, market price) that the user must check themselves. "
            "NEVER give financial advice or guarantee any profit. "
            "If the question is unrelated to crypto, mining, blockchain, or related technologies, politely decline to answer, explaining that your expertise is limited to these topics. "
            "Do not answer questions about illegal activities."
        )

    def _prepare_request_payload(self, user_question: str, history: List[Dict[str, str]]) -> Dict:
        """
        Готовит тело запроса (payload) для Gemini API.
        """
        system_prompt = self._create_system_prompt()
        contents = [{"role": msg["role"], "parts": msg["parts"]} for msg in history if msg.get("role") and msg.get("parts")]
        contents.append({"role": "user", "parts": [{"text": user_question}]})

        return {
            "contents": contents,
            "systemInstruction": {"role": "system", "parts": [{"text": system_prompt}]},
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            ],
            "generationConfig": {
                "temperature": 0.7,
                "topK": 40,
                "topP": 0.95,
            }
        }

    async def _execute_request(self, payload: Dict[str, Any]) -> str:
        """Выполняет запрос к API с логикой повторных попыток."""
        retries = self.max_retries
        delay = 1.0

        for attempt in range(retries):
            try:
                timeout = aiohttp.ClientTimeout(total=45)
                async with self.session.post(
                    self.api_url,
                    headers=self.headers,
                    params=self.params,
                    json=payload,
                    timeout=timeout
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        if not result.get('candidates'):
                            feedback = result.get('promptFeedback', {})
                            if feedback.get('blockReason'):
                                logger.warning(f"Gemini API content blocked. Reason: {feedback.get('blockReason')}")
                                return "AI не смог сформировать ответ из-за внутренних ограничений безопасности. Попробуйте переформулировать вопрос."
                            else:
                                logger.error(f"Gemini API returned no candidates. Full response: {result}")
                                return "AI не смог сформировать ответ. Пожалуйста, попробуйте позже."
                        
                        answer = result['candidates'][0].get('content', {}).get('parts', [{}])[0].get('text', '')
                        return answer.strip() if answer else "AI вернул пустой ответ. Попробуйте задать вопрос иначе."

                    elif response.status in [500, 502, 503, 504]:
                        logger.warning(f"Gemini API returned server error {response.status}. Retrying in {delay}s... (Attempt {attempt + 1}/{retries})")
                        await asyncio.sleep(delay)
                        delay *= 2
                    else:
                        response_text = await response.text()
                        logger.error(f"Gemini API returned non-200 status {response.status}: {response_text}")
                        return "Произошла ошибка при обращении к AI. Пожалуйста, попробуйте позже."

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.warning(f"Network error during Gemini request: {e}. Retrying in {delay}s... (Attempt {attempt + 1}/{retries})")
                await asyncio.sleep(delay)
                delay *= 2
        
        logger.error(f"Failed to get response from Gemini API after {retries} retries.")
        return "Не удалось связаться с AI-сервисом после нескольких попыток. Проверьте ваше соединение или попробуйте значительно позже."

    async def get_ai_answer(self, user_question: str, history: List[Dict[str, str]]) -> str:
        """
        Получает экспертный ответ от Gemini API, учитывая историю диалога и применяя механизм повторных запросов.
        """
        if not user_question.strip():
            return "Пожалуйста, задайте ваш вопрос."

        payload = self._prepare_request_payload(user_question, history)
        
        try:
            answer = await self._execute_request(payload)
            logger.info(f"Successfully generated AI answer for question: '{user_question[:80]}...'")
            return answer
        except Exception as e:
            logger.error(f"Unexpected error in get_ai_answer: {e}", exc_info=True)
            return "Произошла непредвиденная внутренняя ошибка при обработке вашего запроса."