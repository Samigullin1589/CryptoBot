import asyncio
import json
import logging
from typing import Optional, Dict, List
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, conint, ValidationError, field_validator

logger = logging.getLogger(__name__)

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

class QuizService:
    def __init__(self, openai_client: Optional[AsyncOpenAI]):
        self.openai_client = openai_client

    async def generate_quiz_question(self) -> Optional[Dict]:
        if not self.openai_client:
            logger.warning("OpenAI client is not configured. Quiz feature disabled.")
            return None
            
        for attempt in range(3):
            logger.info(f"Generating quiz question with OpenAI... Attempt {attempt + 1}")
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
                logger.info("Successfully generated and validated a quiz question.")
                return validated_data.model_dump()
            except (ValidationError, json.JSONDecodeError) as e:
                logger.error(f"Invalid data structure or content from OpenAI on attempt {attempt + 1}: {e}")
                await asyncio.sleep(1)
            except Exception as e:
                logger.exception(f"Failed to generate quiz from OpenAI: {e}")
                return None
        
        logger.error("Failed to generate a valid quiz question after multiple attempts.")
        return None