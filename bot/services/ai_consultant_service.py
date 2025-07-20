import logging
import aiohttp
from async_lru import alru_cache
from bot.config.settings import settings

logger = logging.getLogger(__name__)

class AIConsultantService:
    """
    Сервис для получения экспертных ответов от Gemini API на вопросы пользователей.
    """
    @alru_cache(maxsize=128, ttl=3600)  # Кэшируем ответы на 1 час
    async def get_ai_answer(self, user_question: str) -> str:
        """
        Получает экспертный ответ от Gemini API на вопрос пользователя.
        """
        if not settings.gemini_api_key:
            logger.warning("GEMINI_API_KEY is not set. AI Consultant is disabled.")
            return "К сожалению, функция AI-Консультанта сейчас недоступна."

        prompt = (
            "Act as an experienced and helpful crypto mining engineer and cryptocurrency expert. "
            "Provide a clear, accurate, and detailed answer in Russian to the following user question. "
            "If the question is unrelated to cryptocurrencies, mining, or blockchain, politely decline to answer. "
            "User question:\n\n"
            f"'{user_question}'"
        )

        try:
            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={settings.gemini_api_key}"
            payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=payload, timeout=30) as response:
                    if response.status != 200:
                        logger.error(f"Gemini API returned status {response.status}: {await response.text()}")
                        return "Произошла ошибка при обращении к AI. Попробуйте позже."
                    
                    result = await response.json()
                    answer = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
                    
                    if not answer:
                        return "AI не смог сформировать ответ. Попробуйте переформулировать вопрос."
                        
                    logger.info(f"Generated AI answer for question: '{user_question}'")
                    return answer.strip()

        except Exception as e:
            logger.error(f"An error occurred during AI Consultant request: {e}")
            return "Произошла непредвиденная ошибка. Пожалуйста, попробуйте позже."
