# =================================================================================
# Файл: bot/services/user_service.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ ПОЛНАЯ)
# Описание: Сервис для управления профилями и историей диалогов.
# ИСПРАВЛЕНИЕ: Восстановлены все методы и добавлен get_user_profiles_bulk.
# =================================================================================
import logging
import json
from typing import Optional, List, Tuple, Dict
from datetime import datetime, timedelta

import redis.asyncio as redis
from aiogram.types import User

from bot.utils.models import UserProfile
from bot.utils.keys import KeyFactory
from bot.config.settings import settings

logger = logging.getLogger(__name__)

class UserService:
    """Сервис для управления данными пользователей в Redis."""
    
    def __init__(self, redis: redis.Redis):
        self.redis = redis
        self.keys = KeyFactory
        self.history_max_size = settings.ai.history_max_size

    async def get_user_profile(self, user_id: int) -> Optional[UserProfile]:
        profile_key = self.keys.user_profile(user_id)
        user_data = await self.redis.hgetall(profile_key)
        if not user_data:
            return None
        return UserProfile(**user_data)

    async def register_user(self, user_id: int, full_name: str, username: Optional[str]) -> bool:
        """Регистрирует нового пользователя. Возвращает True, если пользователь новый."""
        profile_key = self.keys.user_profile(user_id)
        if await self.redis.hsetnx(profile_key, "user_id", user_id) == 0:
            await self.redis.hset(profile_key, mapping={
                "username": username or "N/A",
                "full_name": full_name,
            })
            return False
        
        user_data_to_save = {
            "username": username or "N/A",
            "full_name": full_name,
            "language_code": "N/A",
        }
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.hset(profile_key, mapping=user_data_to_save)
            pipe.sadd(self.keys.all_users_set(), user_id)
            await pipe.execute()
        
        logger.info(f"Зарегистрирован новый пользователь {user_id} ({full_name}).")
        return True

    async def get_or_create_user(self, user: User) -> Tuple[UserProfile, bool]:
        """Получает профиль, а если его нет - создает. Возвращает профиль и флаг 'is_new'."""
        is_new = await self.register_user(user.id, user.full_name, user.username)
        profile = await self.get_user_profile(user.id)
        return profile, is_new

    async def get_all_user_ids(self) -> List[int]:
        user_ids_raw = await self.redis.smembers(self.keys.all_users_set())
        return [int(user_id) for user_id in user_ids_raw]

    async def update_user_activity(self, user_id: int, chat_id: int):
        now = datetime.utcnow()
        today_str, week_str = now.strftime('%Y-%m-%d'), now.strftime('%Y-%U')
        day_key, week_key = f"users:active:day:{today_str}", f"users:active:week:{week_str}"

        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.sadd(day_key, user_id)
            pipe.sadd(week_key, user_id)
            pipe.expire(day_key, timedelta(days=2))
            pipe.expire(week_key, timedelta(weeks=2))
            await pipe.execute()

    async def process_referral(self, new_user_id: int, referrer_id: int) -> bool:
        logger.info(f"Пользователь {new_user_id} пришел по ссылке от {referrer_id}")
        return True

    async def get_conversation_history(self, user_id: int, chat_id: int) -> List[Dict]:
        history_key = self.keys.conversation_history(user_id, chat_id)
        raw_history = await self.redis.lrange(history_key, 0, self.history_max_size * 2 - 1)
        history = [json.loads(msg) for msg in reversed(raw_history)]
        return history

    async def add_to_conversation_history(self, user_id: int, chat_id: int, user_text: str, ai_answer: str):
        history_key = self.keys.conversation_history(user_id, chat_id)
        user_message = {"role": "user", "parts": [{"text": user_text}]}
        model_message = {"role": "model", "parts": [{"text": ai_answer}]}
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.lpush(history_key, json.dumps(model_message, ensure_ascii=False))
            pipe.lpush(history_key, json.dumps(user_message, ensure_ascii=False))
            pipe.ltrim(history_key, 0, self.history_max_size * 2 - 1)
            await pipe.execute()

    async def get_user_profiles_bulk(self, user_ids: List[int]) -> Dict[int, UserProfile]:
        """Массово получает профили пользователей одним запросом."""
        if not user_ids:
            return {}
        
        pipe = self.redis.pipeline()
        for user_id in user_ids:
            pipe.hgetall(self.keys.user_profile(user_id))
        
        results = await pipe.execute()
        
        profiles = {}
        for user_id, user_data in zip(user_ids, results):
            if user_data:
                profiles[user_id] = UserProfile(**user_data)
        return profiles
