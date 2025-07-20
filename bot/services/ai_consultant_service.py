import logging
import aiohttp
from typing import List, Dict
from async_lru import alru_cache
from bot.config.settings import settings

logger = logging.getLogger(__name__)

class AIConsultantService:
    """
    Сервис для получения экспертных ответов от Gemini API на вопросы пользователей,
    с поддержкой контекста диалога и функцией определения релевантности вопроса.
    """

    @alru_cache(maxsize=512, ttl=600) # Кэшируем быстрые проверки на 10 минут
    async def is_question_for_ai(self, text: str) -> bool:
        """
        Использует AI для быстрой проверки, является ли текст вопросом по теме крипты/майнинга.
        """
        # Игнорируем слишком короткие сообщения, чтобы не тратить ресурсы API
        if len(text.split()) < 3:
            return False

        if not settings.gemini_api_key:
            logger.warning("GEMINI_API_KEY is not set. AI question check is disabled.")
            return False

        # Улучшенный промпт с примерами для более точного определения
        prompt = (
            "You are a triage bot. Your task is to determine if the following message from a group chat is a specific question about cryptocurrencies, blockchain technology, or crypto mining that requires an expert answer. "
            "General greetings, simple statements, or thanks are NOT questions. Answer ONLY with 'Yes' or 'No'.\n\n"
            "Examples of questions to answer 'Yes':\n"
            "- 'Кто знает М64 гидро 1 фазные?'\n"
            "- 'температура для плат 73-74 для асика whatsminer m50s - это нормально?'\n"
            "- 'какой сейчас самый выгодный асик для дома?'\n\n"
            "Examples of messages to answer 'No':\n"
            "- 'привет всем'\n"
            "- 'спасибо за ответ'\n"
            "- 'btc летит на луну'\n\n"
            f"Message to analyze: '{text}'"
        )
        
        try:
            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={settings.gemini_api_key}"
            payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=payload, timeout=5) as response:
                    if response.status != 200:
                        logger.error(f"Gemini quick check API returned status {response.status}")
                        return False
                    
                    result = await response.json()
                    answer = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', 'No')
                    
                    is_question = "yes" in answer.lower()
                    logger.info(f"AI Triage for '{text[:30]}...': Is it a question? -> {is_question}")
                    return is_question

        except Exception as e:
            logger.error(f"An error occurred during AI question check: {e}")
            return False


    @alru_cache(maxsize=128, ttl=3600)
    async def get_ai_answer(self, user_question: str, history: List[Dict[str, str]]) -> str:
        """
        Получает экспертный ответ от Gemini API, учитывая предыдущую историю диалога.
        """
        if not settings.gemini_api_key:
            return "К сожалению, функция AI-Консультанта сейчас недоступна."

        # Улучшенный промпт с определением роли и структуры ответа
        prompt = (
            "You are 'CryptoBot Co-Pilot', a world-class expert engineer in cryptocurrency and ASIC mining. Your tone is professional, helpful, and precise. "
            "Provide a comprehensive and well-structured answer in Russian to the user's latest question, using the provided conversation history for context. "
            "Structure your answer with clear headings (using bold text), bullet points, and `code` blocks for technical specifications. "
            "Start the answer by directly addressing the user's question. "
            "Conclude your answer with a '<b>Вывод:</b>' (Conclusion) section that summarizes the key takeaway. "
            "If the question is a request for a recommendation (e.g., 'what is the most profitable'), provide an analytical comparison of 2-3 relevant options and explain the trade-offs, rather than giving a single answer. "
            "Always state that profitability depends on variables the user must check themselves. "
            "If the question is unrelated to crypto, politely decline."
        )

        contents = []
        for message in history:
            role = message.get("role")
            text = message.get("text")
            if role and text:
                contents.append({"role": role, "parts": [{"text": text}]})
        
        contents.append({"role": "user", "parts": [{"text": user_question}]})

        try:
            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={settings.gemini_api_key}"
            payload = {
                "contents": contents,
                "systemInstruction": { "role": "system", "parts": [{"text": prompt}] }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=payload, timeout=30) as response:
                    if response.status != 200:
                        logger.error(f"Gemini API returned status {response.status}: {await response.text()}")
                        return "Произошла ошибка при обращении к AI. Попробуйте позже."
                    
                    result = await response.json()
                    
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
