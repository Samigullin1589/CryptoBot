# ===============================================================
# Файл: bot/services/quiz_service.py (Path FIX v2)
# Описание: Исправлен путь к fallback_quiz.json для
# соответствия твоей структуре проекта (папка data в корне).
# ===============================================================
import asyncio
import json
import logging
import random
from pathlib import Path # <-- Импорт для работы с путями
from typing import Optional, Dict, List, Tuple

from openai import AsyncOpenAI
from pydantic import BaseModel, Field, conint, ValidationError, field_validator

from bot.services.ai_service import AIService

logger = logging.getLogger(__name__)

# --- Модели для валидации данных ---
class QuizResponse(BaseModel):
    question: str = Field(..., max_length=300)
    options: List[str] = Field(..., min_length=4, max_length=4)
    correct_option_index: conint(ge=0, lt=4)

    @field_validator('options')
    def check_options_length(cls, options: List[str]) -> List[str]:
        for option in options:
            if len(option) > 100:
                raise ValueError("Option length must not exceed 100 characters")
        return options

# --- Сервис ---
class QuizService:
    def __init__(self, ai_service: AIService, openai_client: Optional[AsyncOpenAI]):
        self.ai_service = ai_service
        self.openai_client = openai_client
        self.fallback_questions = self._load_fallback_questions()

    def _load_fallback_questions(self) -> List[Dict]:
        """Загружает резервные вопросы из локального JSON файла."""
        file_path = None
        try:
            # --- ИСПРАВЛЕНО: Используем pathlib для построения правильного пути ---
            # Этот путь будет работать независимо от того, откуда запускается бот.
            # bot/services/quiz_service.py -> bot/services -> bot -> корень проекта -> data
            file_path = Path(__file__).parent.parent.parent / "data" / "fallback_quiz.json"
            # --- КОНЕЦ ИСПРАВЛЕНИЯ ---
            
            with open(file_path, "r", encoding="utf-8") as f:
                questions = json.load(f)
                logger.info(f"Successfully loaded {len(questions)} fallback quiz questions.")
                return questions
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Could not load fallback quiz questions from '{file_path}': {e}")
            return []

    async def get_random_question(self) -> Tuple[str, List[str], int]:
        """
        Главный метод. Пытается получить вопрос по цепочке: OpenAI -> Gemini -> Файл.
        """
        # Попытка №1: Сгенерировать через OpenAI
        if self.openai_client:
            logger.info("Attempting to get a quiz question via OpenAI...")
            openai_quiz = await self._generate_quiz_with_openai()
            if openai_quiz:
                return (
                    openai_quiz['question'],
                    openai_quiz['options'],
                    openai_quiz['correct_option_index']
                )

        # Попытка №2: Сгенерировать через Gemini
        logger.warning("OpenAI failed or not configured, falling back to Gemini.")
        gemini_quiz = await self._generate_quiz_with_gemini()
        if gemini_quiz:
            return (
                gemini_quiz['question'],
                gemini_quiz['options'],
                gemini_quiz['correct_option_index']
            )

        # Попытка №3: Использовать резервный вопрос из файла
        logger.warning("All AI providers failed, falling back to local quiz questions.")
        fallback_quiz = self._get_fallback_question()
        if fallback_quiz:
            return (
                fallback_quiz['question'],
                fallback_quiz['options'],
                fallback_quiz['correct_option_index']
            )
            
        # Если ничего не сработало
        logger.error("No quiz questions available from any source.")
        return ("Викторина временно недоступна.", ["Попробуйте позже"], 0)

    def _get_fallback_question(self) -> Optional[Dict]:
        """Возвращает случайный вопрос из резервного списка."""
        if not self.fallback_questions:
            return None
        return random.choice(self.fallback_questions)

    async def _generate_quiz_with_openai(self) -> Optional[Dict]:
        """Генерирует вопрос с помощью OpenAI."""
        prompt_messages = [
            {"role": "system", "content": "You are an assistant that creates fun and engaging multiple-choice questions about cryptocurrency for a Russian-speaking audience. Provide the response IN RUSSIAN as a JSON object with keys: 'question' (max 300 chars), 'options' (a list of 4 strings, each max 100 chars), and 'correct_option_index' (an integer from 0 to 3)."},
            {"role": "user", "content": "Сгенерируй новый интересный вопрос для крипто-викторины на русском языке."}
        ]
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=prompt_messages,
                response_format={"type": "json_object"},
                temperature=1.1
            )
            raw_data = json.loads(response.choices[0].message.content)
            validated_data = QuizResponse.model_validate(raw_data)
            logger.info("Successfully generated and validated a quiz question from OpenAI.")
            return validated_data.model_dump()
        except Exception as e:
            logger.exception(f"Failed to generate quiz from OpenAI: {e}")
            return None

    async def _generate_quiz_with_gemini(self) -> Optional[Dict]:
        """Генерирует вопрос с помощью Gemini, используя твой AIService."""
        system_prompt = (
            "You are an assistant that creates fun and engaging multiple-choice questions "
            "about cryptocurrency for a Russian-speaking audience. Provide the response IN RUSSIAN "
            "as a single, valid JSON object with keys: 'question' (max 300 chars), 'options' "
            "(a list of 4 strings, each max 100 chars), and 'correct_option_index' "
            "(an integer from 0 to 3). Do not add any extra text or markdown formatting."
        )
        user_prompt = "Сгенерируй новый интересный вопрос для крипто-викторины на русском языке."
        
        try:
            response_json_str = await self.ai_service.get_text_response(
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
            
            if response_json_str.startswith("```json"):
                response_json_str = response_json_str[7:-3].strip()

            raw_data = json.loads(response_json_str)
            validated_data = QuizResponse.model_validate(raw_data)
            logger.info("Successfully generated and validated a quiz question from Gemini.")
            return validated_data.model_dump()
        except Exception as e:
            logger.exception(f"Failed to generate quiz from Gemini: {e}")
            return None
