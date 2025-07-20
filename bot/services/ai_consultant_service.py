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

        # --- НОВЫЙ, УЛУЧШЕННЫЙ ПРОМПТ ---
        # Этот промпт направляет AI на предоставление анализа, а не прямого финансового совета.
        prompt = (
            "Act as an experienced and helpful crypto mining engineer and cryptocurrency expert. "
            "Provide a clear, accurate, and detailed answer in Russian to the following user question. "
            "IMPORTANT: If the user asks 'what is the most profitable' or for direct financial advice, "
            "DO NOT give a single answer. Instead, provide a market analysis. "
            "For example, list 2-3 popular models for different categories (e.g., home, industrial), "
            "describe their pros and cons, and explain that profitability depends on factors like "
            "electricity cost, coin price, and network difficulty, which the user must calculate themselves. "
            "Frame your response as educational analysis, not a direct recommendation. "
            "If the question is unrelated to cryptocurrencies, mining, or blockchain, politely decline to answer. "
            "User question:\n\n"
            f"'{user_question}'"
        )
        # --- КОНЕЦ НОВОГО ПРОМПТА ---

        try:
            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={settings.gemini_api_key}"
            payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=payload, timeout=30) as response:
                    if response.status != 200:
                        logger.error(f"Gemini API returned status {response.status}: {await response.text()}")
                        return "Произошла ошибка при обращении к AI. Попробуйте позже."
                    
                    result = await response.json()
                    # Добавлена проверка на случай, если candidates пустой
                    if not result.get('candidates'):
                        logger.error(f"Gemini API returned no candidates. Full response: {result}")
                        return "AI не смог сформировать ответ из-за внутренних ограничений. Попробуйте переформулировать вопрос."

                    answer = result['candidates'][0].get('content', {}).get('parts', [{}])[0].get('text', '')
                    
                    if not answer:
                        return "AI не смог сформировать ответ. Попробуйте переформулировать вопрос."
                        
                    logger.info(f"Generated AI answer for question: '{user_question}'")
                    return answer.strip()

        except Exception as e:
            logger.error(f"An error occurred during AI Consultant request: {e}")
            return "Произошла непредвиденная ошибка. Пожалуйста, попробуйте позже."
