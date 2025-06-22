import logging
import json
from typing import Optional
from openai import AsyncOpenAI, OpenAIError

from bot.utils.models import QuizQuestion

logger = logging.getLogger(__name__)

class QuizService:
    def __init__(self, openai_client: Optional[AsyncOpenAI]):
        self.client = openai_client

    async def get_quiz_question(self) -> Optional[QuizQuestion]:
        """Генерирует вопрос для викторины с помощью OpenAI."""
        if not self.client:
            logger.warning("Клиент OpenAI не инициализирован. Викторина недоступна.")
            return None

        logger.info("Запрос нового вопроса для викторины к OpenAI...")
        prompt = (
            "Создай один вопрос для викторины на тему криптовалют. "
            "Вопрос должен быть интересным и не слишком сложным. "
            "Предоставь 4 варианта ответа. "
            "Ответ должен быть в формате JSON: "
            '{"question": "Текст вопроса", "options": ["Вариант А", "Вариант Б", "Вариант В", "Вариант Г"], "correct_option_index": N}, '
            "где N - это индекс правильного ответа (от 0 до 3)."
        )
        try:
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            if not content:
                logger.error("OpenAI вернул пустой ответ.")
                return None

            data = json.loads(content)
            logger.info("Вопрос для викторины успешно сгенерирован.")
            return QuizQuestion(**data)
        except OpenAIError as e:
            logger.error(f"Ошибка при обращении к OpenAI: {e}")
            return None
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Не удалось распарсить JSON от OpenAI: {e}")
            return None