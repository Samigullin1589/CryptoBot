# bot/services/quiz_service.py
import json
import logging
from typing import Optional, Dict

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class QuizService:
    def __init__(self, openai_client: Optional[AsyncOpenAI]):
        """
        Сервис для генерации вопросов викторины с помощью OpenAI.
        """
        self.openai_client = openai_client

    async def generate_quiz_question(self) -> Optional[Dict]:
        """
        Генерирует вопрос для викторины, используя улучшенный промпт и JSON mode.
        """
        if not self.openai_client:
            logger.warning("OpenAI client is not configured. Skipping quiz question generation.")
            return None
            
        logger.info("Generating quiz question with OpenAI...")

        # Улучшенный, более надежный "few-shot" промпт, как рекомендовано в аудите
        prompt_messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant designed to create quiz questions about cryptocurrency. "
                    "You must respond only with a single, valid JSON object. "
                    "The JSON object must have three keys: 'question' (a string), "
                    "'options' (an array of 4 unique strings), and 'correct_option_index' "
                    "(an integer from 0 to 3)."
                )
            },
            {
                "role": "user",
                "content": "Give me an example of a quiz question about Bitcoin."
            },
            {
                "role": "assistant",
                "content": '''
{
  "question": "Как называется самый первый блок в блокчейне Bitcoin?",
  "options": [
    "Genesis Block",
    "Alpha Block",
    "Pioneer Block",
    "Root Block"
  ],
  "correct_option_index": 0
}'''
            },
            {
                "role": "user",
                "content": "Теперь создай новый, интересный вопрос о майнинге."
            }
        ]

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=prompt_messages,
                response_format={"type": "json_object"},  # Гарантирует валидный JSON
                temperature=0.9
            )
            quiz_data = json.loads(response.choices[0].message.content)
            
            # Дополнительная проверка структуры на всякий случай
            if all(k in quiz_data for k in ['question', 'options', 'correct_option_index']) and \
               isinstance(quiz_data.get('options'), list) and len(quiz_data['options']) == 4:
                return quiz_data
            else:
                logger.error("Generated JSON has incorrect structure.", extra={'data': quiz_data})
                return None

        except Exception as e:
            logger.exception("Failed to generate or parse quiz question", extra={'error': str(e)})
            return None
