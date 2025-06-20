import json
import logging
from typing import Optional, Dict, List

from openai import AsyncOpenAI
from pydantic import BaseModel, Field, conint, ValidationError

logger = logging.getLogger(__name__)

class QuizResponse(BaseModel):
    question: str
    options: List[str] = Field(..., min_length=4, max_length=4)
    correct_option_index: conint(ge=0, lt=4)

class QuizService:
    def __init__(self, openai_client: Optional[AsyncOpenAI]):
        self.openai_client = openai_client

    async def generate_quiz_question(self) -> Optional[Dict]:
        if not self.openai_client:
            logger.warning("OpenAI client is not configured.")
            return None

        logger.info("Generating quiz question with OpenAI...")
        # ... (ваш промпт остается здесь без изменений) ...
        prompt_messages = [
            # ...
        ]
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=prompt_messages,
                response_format={"type": "json_object"},
                temperature=0.9
            )
            raw_data = json.loads(response.choices[0].message.content)
            validated_data = QuizResponse.model_validate(raw_data)
            return validated_data.model_dump()
        except (ValidationError, json.JSONDecodeError) as e:
            logger.error("Invalid JSON from OpenAI", extra={'data': raw_data, 'error': str(e)})
        except Exception as e:
            logger.exception("Failed to get quiz from OpenAI")
        return None