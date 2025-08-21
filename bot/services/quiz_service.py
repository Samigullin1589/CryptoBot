# bot/services/quiz_service.py
# Дата обновления: 20.08.2025
# Версия: 2.0.0
# Описание: Сервис для генерации вопросов для крипто-викторины с использованием
# AI и отказоустойчивым механизмом резервных вопросов.

import json
import random
from pathlib import Path
from typing import List, Optional

from loguru import logger
from pydantic import ValidationError

from bot.config.settings import settings
from bot.services.ai_content_service import AIContentService
from bot.texts.ai_prompts import get_quiz_question_prompt
from bot.utils.models import QuizQuestion


class QuizService:
    """
    Управляет созданием и предоставлением вопросов для викторины.
    Использует AI для генерации уникальных вопросов и имеет локальный
    список вопросов в качестве резервного источника.
    """

    def __init__(self, ai_content_service: AIContentService):
        """
        Инициализирует сервис.

        :param ai_content_service: Сервис для взаимодействия с AI-моделями.
        """
        self.ai_service = ai_content_service
        self.config = settings.QUIZ
        self.fallback_questions: List[QuizQuestion] = self._load_fallback_questions()
        logger.info("Сервис QuizService инициализирован.")

    def _load_fallback_questions(self) -> List[QuizQuestion]:
        """
        Загружает и валидирует резервные вопросы из локального JSON-файла.
        Невалидные вопросы отбраковываются с записью предупреждения в лог.
        """
        fallback_path = Path(__file__).parent.parent.parent / self.config.FALLBACK_QUESTIONS_PATH
        if not fallback_path.exists():
            logger.error(f"Файл с резервными вопросами не найден: {fallback_path}")
            return []

        try:
            with open(fallback_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            questions_data = data.get("questions", [])
            if not isinstance(questions_data, list):
                logger.error("Ключ 'questions' в файле резервных вопросов должен быть списком.")
                return []

            valid_questions = []
            for item in questions_data:
                try:
                    valid_questions.append(QuizQuestion.model_validate(item))
                except ValidationError as e:
                    logger.warning(f"Пропущен некорректный резервный вопрос: {item}. Ошибка: {e}")
            
            logger.info(f"Успешно загружено {len(valid_questions)} валидных резервных вопросов из {fallback_path}.")
            return valid_questions
        except (json.JSONDecodeError, OSError) as e:
            logger.exception(f"Не удалось загрузить или обработать файл резервных вопросов: {e}")
            return []

    async def get_random_question(self) -> Optional[QuizQuestion]:
        """
        Возвращает случайный вопрос для викторины.
        Приоритет отдается генерации через AI. В случае неудачи используется
        резервный список вопросов из файла.
        """
        logger.info("Попытка сгенерировать вопрос для викторины через AI...")
        
        prompt = get_quiz_question_prompt()
        json_schema = QuizQuestion.model_json_schema()
        
        # Пытаемся получить структурированный ответ от AI
        ai_result = await self.ai_service.get_structured_response(prompt, json_schema)
        
        if isinstance(ai_result, dict):
            try:
                # Валидируем ответ от AI
                question = QuizQuestion.model_validate(ai_result)
                logger.success("Успешно сгенерирован и валидирован вопрос для викторины через AI.")
                return question
            except ValidationError as e:
                logger.warning(f"AI вернул данные, но они не прошли валидацию: {e}. Данные: {ai_result}")

        # Если AI не справился, используем резервный вариант
        logger.warning("AI не смог сгенерировать валидный вопрос. Используется резервный вариант.")
        
        if not self.fallback_questions:
            logger.critical("AI не справился, и резервные вопросы недоступны или не загружены.")
            return None
            
        return random.choice(self.fallback_questions)