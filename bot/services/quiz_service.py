# ===============================================================
# Файл: bot/services/quiz_service.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: "Тонкий" сервис-оркестратор для управления викториной.
# Делегирует генерацию вопросов AIContentService и использует
# локальный файл как резервный источник.
# ===============================================================
import json
import logging
import random
from pathlib import Path
from typing import Optional, Tuple

from bot.services.ai_content_service import AIContentService
from bot.utils.models import QuizQuestion

logger = logging.getLogger(__name__)

class QuizService:
    """
    Сервис для управления логикой крипто-викторины.
    """
    def __init__(self, ai_content_service: AIContentService):
        """
        Инициализирует сервис.

        :param ai_content_service: Сервис для генерации контента с помощью AI.
        """
        self.ai_content_service = ai_content_service
        self.fallback_questions = self._load_fallback_questions()
        logger.info("QuizService инициализирован.")

    def _load_fallback_questions(self) -> list[QuizQuestion]:
        """Загружает резервные вопросы из локального JSON файла."""
        try:
            # Этот путь будет работать независимо от того, откуда запускается бот.
            # bot/services/quiz_service.py -> bot/services -> bot -> корень -> data
            file_path = Path(__file__).parent.parent.parent / "data" / "fallback_quiz.json"
            
            with open(file_path, "r", encoding="utf-8") as f:
                questions_data = json.load(f)
                
            validated_questions = [QuizQuestion.model_validate(q) for q in questions_data]
            logger.info(f"Успешно загружено {len(validated_questions)} резервных вопросов для викторины.")
            return validated_questions
            
        except (FileNotFoundError, json.JSONDecodeError, TypeError) as e:
            logger.error(f"Не удалось загрузить резервные вопросы для викторины: {e}")
            return []

    async def get_random_question(self) -> Tuple[str, list[str], int, Optional[str]]:
        """
        Главный метод. Пытается получить вопрос от AI, а в случае неудачи — из файла.
        """
        # Попытка №1: Сгенерировать через AI
        logger.info("Попытка сгенерировать вопрос для викторины через AIContentService...")
        ai_quiz = await self.ai_content_service.generate_quiz_question()
        if ai_quiz:
            logger.info("Вопрос для викторины успешно сгенерирован AI.")
            return (
                ai_quiz.question,
                ai_quiz.options,
                ai_quiz.correct_option_index,
                ai_quiz.explanation
            )

        # Попытка №2: Использовать резервный вопрос из файла
        logger.warning("AI не смог сгенерировать вопрос, используется резервный из файла.")
        if self.fallback_questions:
            fallback_quiz = random.choice(self.fallback_questions)
            return (
                fallback_quiz.question,
                fallback_quiz.options,
                fallback_quiz.correct_option_index,
                fallback_quiz.explanation
            )
            
        # Если ничего не сработало
        logger.error("Нет доступных вопросов для викторины ни от AI, ни из резервного файла.")
        return ("Викторина временно недоступна.", ["Попробуйте позже"], 0, None)
