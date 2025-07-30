# ===============================================================
# Файл: bot/services/quiz_service.py (НОВЫЙ ФАЙЛ)
# Описание: Сервис для генерации вопросов для крипто-викторины.
# ===============================================================
import logging
import random
from typing import Tuple, List, Optional, Dict, Any

from bot.services.ai_content_service import AIContentService
from bot.texts.ai_prompts import get_quiz_question_prompt

logger = logging.getLogger(__name__)

class QuizService:
    """
    Генерирует вопросы для викторины, используя AI как основной
    источник и локальный JSON как резервный.
    """
    def __init__(self, ai_content_service: AIContentService, fallback_questions: List[Dict[str, Any]]):
        self.ai_service = ai_content_service
        self.fallback_questions = fallback_questions

    async def get_random_question(self) -> Optional[Tuple[str, List[str], int]]:
        """
        Возвращает вопрос, варианты ответа и ID правильного ответа.
        """
        logger.info("Attempting to generate a quiz question via AI...")
        
        # 1. Попытка сгенерировать вопрос через AI
        prompt = get_quiz_question_prompt()
        json_schema = {
            "type": "OBJECT",
            "properties": {
                "question": {"type": "STRING"},
                "options": {"type": "ARRAY", "items": {"type": "STRING"}},
                "correct_option_index": {"type": "INTEGER"}
            },
            "required": ["question", "options", "correct_option_index"]
        }
        
        ai_result = await self.ai_service.generate_structured_content(prompt, json_schema)
        
        if ai_result and all(k in ai_result for k in json_schema['required']):
            options = ai_result['options']
            correct_index = ai_result['correct_option_index']
            # Проверяем валидность ответа от AI
            if len(options) == 4 and 0 <= correct_index < 4:
                logger.info("Successfully generated quiz question via AI.")
                return ai_result['question'], options, correct_index

        logger.warning("AI failed to generate a valid quiz question. Using fallback.")
        
        # 2. Если AI не справился, используем резервный список
        if not self.fallback_questions:
            logger.error("AI failed and no fallback questions are available.")
            return None
            
        question_data = random.choice(self.fallback_questions)
        return (
            question_data.get("question"),
            question_data.get("options"),
            question_data.get("correct_option_index")
        )
