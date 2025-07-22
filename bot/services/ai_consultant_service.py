import logging
from typing import List, Dict

import aiohttp

logger = logging.getLogger(__name__)

class AIConsultantService:
    """
    Сервис для получения экспертных ответов от Gemini API на вопросы пользователей.
    Сфокусирован исключительно на предоставлении качественных консультаций.
    """
    def __init__(self, gemini_api_key: str, http_session: aiohttp.ClientSession):
        """
        Инициализирует сервис.
        
        :param gemini_api_key: API-ключ для доступа к Google Gemini.
        :param http_session: Общий экземпляр aiohttp.ClientSession для переиспользования соединений.
        """
        if not gemini_api_key:
            raise ValueError("Необходимо передать API-ключ Gemini.")
        self.api_key = gemini_api_key
        self.session = http_session
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.api_key}"

    def _create_system_prompt(self) -> str:
        """
        Создает и возвращает системный промпт, определяющий роль и поведение AI-консультанта.
        """
        return (
            "You are 'CryptoBot Co-Pilot', a world-class expert engineer in cryptocurrency and ASIC mining. Your tone is professional, helpful, and precise. "
            "Your primary goal is to provide accurate, well-structured, and safe information. "
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

        contents = []
        for message in history:
            role = message.get("role")
            # --- Улучшение: Проверяем, что parts - это список словарей ---
            parts = message.get("parts")
            if role and isinstance(parts, list) and parts and "text" in parts[0]:
                contents.append({"role": role, "parts": parts})
        
        contents.append({"role": "user", "parts": [{"text": user_question}]})

        return {
            "contents": contents,
            "systemInstruction": { "role": "system", "parts": [{"text": system_prompt}] },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            ]
        }

    # --- ГЛАВНОЕ ИСПРАВЛЕНИЕ: Убран декоратор @alru_cache ---
    async def get_ai_answer(self, user_question: str, history: List[Dict[str, str]]) -> str:
        """
        Получает экспертный ответ от Gemini API, учитывая предыдущую историю диалога.
        """
        payload = self._prepare_request_payload(user_question, history)

        try:
            async with self.session.post(self.api_url, json=payload, timeout=30) as response:
                if response.status != 200:
                    response_text = await response.text()
                    logger.error(f"Gemini API вернул статус {response.status}: {response_text}")
                    return "Произошла ошибка при обращении к AI. Пожалуйста, попробуйте позже."
                
                result = await response.json()
                
                if not result.get('candidates'):
                    finish_reason = result.get('promptFeedback', {}).get('blockReason')
                    if finish_reason:
                        logger.warning(f"Gemini API не вернул кандидатов из-за настроек безопасности. Причина: {finish_reason}. Вопрос: '{user_question}'")
                        return "AI не смог сформировать ответ из-за внутренних ограничений безопасности. Попробуйте переформулировать вопрос."
                    else:
                        logger.error(f"Gemini API не вернул кандидатов. Полный ответ: {result}")
                        return "AI не смог сформировать ответ. Попробуйте переформулировать вопрос."

                answer = result['candidates'][0].get('content', {}).get('parts', [{}])[0].get('text', '')
                
                if not answer:
                    logger.warning(f"Gemini API вернул пустой ответ на вопрос: '{user_question}'")
                    return "AI не смог сформировать содержательный ответ. Попробуйте задать вопрос иначе."
                    
                logger.info(f"Сгенерирован AI-ответ на вопрос: '{user_question}'")
                return answer.strip()

        except aiohttp.ClientError as e:
            logger.error(f"Сетевая ошибка при запросе к AI-Консультанту: {e}")
            return "Ошибка сети при обращении к AI. Проверьте соединение и попробуйте позже."
        except Exception as e:
            logger.error(f"Непредвиденная ошибка в AI-Консультанте: {e}", exc_info=True)
            return "Произошла непредвиденная ошибка. Пожалуйста, попробуйте позже."
