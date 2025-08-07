# =================================================================================
# Файл: bot/services/user_service.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ)
# Описание: Сервис для управления профилями и историей диалогов.
# ИСПРАВЛЕНИЕ: Логика создания пользователя полностью переработана для
# обеспечения целостности данных и устранения ValidationError.
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
        """Получает профиль пользователя из Redis по его ID."""
        profile_key = self.keys.user_profile(user_id)
        user_data = await self.redis.hgetall(profile_key)
        if not user_data:
            return None
        return UserProfile(**user_data)

    async def get_or_create_user(self, user: User) -> Tuple[UserProfile, bool]:
        """
        Получает профиль пользователя. Если его нет, создает.
        Всегда гарантирует, что профиль содержит актуальные данные.
        Возвращает профиль и флаг 'is_new'.
        """
        profile_key = self.keys.user_profile(user.id)
        is_new = False
        
        # Проверяем, существует ли пользователь в глобальном сете
        if not await self.redis.sismember(self.keys.all_users_set(), user.id):
            is_new = True
        
        # Всегда обновляем данные, так как пользователь мог сменить имя или username
        user_data_to_save = {
            "user_id": user.id,
            "username": user.username or "N/A",
            "full_name": user.full_name,
            "language_code": user.language_code or "N/A",
        }
        
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.hset(profile_key, mapping=user_data_to_save)
            pipe.sadd(self.keys.all_users_set(), user.id)
            await pipe.execute()
        
        if is_new:
            logger.info(f"Зарегистрирован новый пользователь {user.id} ({user.full_name}).")
        
        return UserProfile(**user_data_to_save), is_new

    async def get_all_user_ids(self) -> List[int]:
        """Возвращает список ID всех пользователей, которые когда-либо взаимодействовали с ботом."""
        user_ids_raw = await self.redis.smembers(self.keys.all_users_set())
        return [int(user_id) for user_id in user_ids_raw]

    async def update_user_activity(self, user_id: int, chat_id: int):
        """Обновляет временные метки активности пользователя."""
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
        """Обрабатывает реферальную ссылку."""
        logger.info(f"Пользователь {new_user_id} пришел по ссылке от {referrer_id}")
        # Пример: await self.redis.hincrbyfloat(self.keys.user_game_profile(referrer_id), "balance", 50.0)
        return True

    # --- РЕАЛИЗАЦИЯ ИСТОРИИ ДИАЛОГОВ ---
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
