# ===============================================================
# Файл: bot/services/quiz_service.py (ВЕРСИЯ "Distinguished Engineer")
# Описание: Сервис для генерации вопросов для крипто-викторины.
# ИСПРАВЛЕНИЕ: Изменен путь импорта 'settings' для соответствия новой архитектуре.
# ===============================================================
import logging
import random
import json
from typing import Any

# ИСПРАВЛЕНО: Импортируем 'settings' из нового единого источника
from bot.config.settings import settings
from bot.services.ai_content_service import AIContentService
from bot.texts.ai_prompts import get_quiz_question_prompt, get_quiz_json_schema

logger = logging.getLogger(__name__)


class QuizService:
    def __init__(self, ai_content_service: AIContentService):
        self.ai_service = ai_content_service
        self.config = settings.quiz
        self.fallback_questions = self._load_fallback_questions()

    def _load_fallback_questions(self) -> list[dict[str, Any]]:
        path = self.config.fallback_questions_path
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
                questions = data.get("questions", [])
                logger.info(
                    f"Успешно загружено {len(questions)} резервных вопросов из {path}"
                )
                return questions
        except Exception as e:
            logger.error(f"Не удалось загрузить резервные вопросы из {path}: {e}")
        return []

    async def get_random_question(self) -> tuple[str, list[str], int] | None:
        logger.info("Попытка сгенерировать вопрос для викторины через AI...")

        prompt = get_quiz_question_prompt()
        json_schema = get_quiz_json_schema()

        ai_result = await self.ai_service.generate_structured_content(
            prompt, json_schema
        )

        if ai_result and all(k in ai_result for k in json_schema["required"]):
            options = ai_result.get("options", [])
            correct_index = ai_result.get("correct_option_index", -1)
            if (
                isinstance(options, list)
                and len(options) == 4
                and 0 <= correct_index < 4
            ):
                logger.info("Успешно сгенерирован вопрос для викторины через AI.")
                return ai_result["question"], options, correct_index

        logger.warning(
            "AI не смог сгенерировать валидный вопрос. Используется резервный вариант."
        )

        if not self.fallback_questions:
            logger.error("AI не справился, и резервные вопросы недоступны.")
            return None

        question_data = random.choice(self.fallback_questions)
        return (
            question_data.get("question"),
            question_data.get("options"),
            question_data.get("correct_option_index"),
        )
