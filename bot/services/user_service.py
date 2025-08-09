# =================================================================================
# Файл: bot/services/user_service.py (ФИНАЛЬНАЯ ИНТЕГРИРОВАННАЯ ВЕРСИЯ, АВГУСТ 2025)
# Описание: Сервис для управления данными пользователей, полностью
# синхронизированный с единой моделью `User` и сохраняющий всю бизнес-логику.
# =================================================================================
import json
import logging
from typing import Optional, List, Tuple, Dict
from datetime import datetime, timedelta

from aiogram.types import User as TelegramUser
from redis.asyncio import Redis

# ИСПРАВЛЕНО: Импортируем единую, правильную модель User и роли
from bot.utils.models import User, UserRole
from bot.utils.keys import KeyFactory
from bot.config.settings import settings

logger = logging.getLogger(__name__)

class UserService:
    """Сервис для управления данными пользователей в Redis."""
    
    def __init__(self, redis: Redis):
        self.redis = redis
        self.keys = KeyFactory
        self.history_max_size = settings.ai.history_max_size

    async def get_user(self, user_id: int) -> Optional[User]:
        """
        Получает данные пользователя из Redis в виде JSON, валидирует их
        с помощью модели User и возвращает объект.
        """
        user_key = self.keys.user_profile(user_id)
        user_data_json = await self.redis.get(user_key)
        
        if not user_data_json:
            return None
            
        try:
            # Используем model_validate_json для максимальной производительности
            return User.model_validate_json(user_data_json)
        except Exception as e:
            logger.error(f"Ошибка при десериализации данных для пользователя {user_id}: {e}")
            return None

    async def save_user(self, user: User) -> None:
        """
        Сохраняет полную модель пользователя в Redis в виде одной JSON-строки.
        Это гарантирует атомарность и целостность данных.
        """
        user_key = self.keys.user_profile(user.id)
        # Используем model_dump_json для сериализации полной модели User
        await self.redis.set(user_key, user.model_dump_json())

    async def get_or_create_user(self, tg_user: TelegramUser) -> Tuple[User, bool]:
        """
        Получает пользователя из базы данных. Если его нет, создает нового
        на основе данных из Telegram и сохраняет его.
        Возвращает объект пользователя и флаг 'is_new'.
        """
        existing_user = await self.get_user(tg_user.id)
        if existing_user:
            return existing_user, False
        
        # Создаем нового пользователя с данными по умолчанию
        new_user = User(
            id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.full_name,
            language_code=tg_user.language_code,
            role=UserRole.USER # Роль по умолчанию
        )
        
        # Используем транзакцию для атомарного сохранения и добавления в общий список
        async with self.redis.pipeline(transaction=True) as pipe:
            user_key = self.keys.user_profile(new_user.id)
            pipe.set(user_key, new_user.model_dump_json())
            pipe.sadd(self.keys.all_users_set(), new_user.id)
            await pipe.execute()

        logger.info(f"Зарегистрирован новый пользователь {tg_user.id} (@{tg_user.username}).")
        return new_user, True

    async def get_all_user_ids(self) -> List[int]:
        """Получает ID всех зарегистрированных пользователей."""
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

    async def get_conversation_history(self, user_id: int, chat_id: int) -> List[Dict]:
        """Получает историю диалога пользователя с AI."""
        history_key = self.keys.conversation_history(user_id, chat_id)
        raw_history = await self.redis.lrange(history_key, 0, self.history_max_size * 2 - 1)
        history = [json.loads(msg) for msg in reversed(raw_history)]
        return history

    async def add_to_conversation_history(self, user_id: int, chat_id: int, user_text: str, ai_answer: str):
        """Добавляет сообщения пользователя и AI в историю диалога."""
        history_key = self.keys.conversation_history(user_id, chat_id)
        user_message = {"role": "user", "parts": [{"text": user_text}]}
        model_message = {"role": "model", "parts": [{"text": ai_answer}]}
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.lpush(history_key, json.dumps(model_message, ensure_ascii=False))
            pipe.lpush(history_key, json.dumps(user_message, ensure_ascii=False))
            pipe.ltrim(history_key, 0, self.history_max_size * 2 - 1)
            await pipe.execute()

    async def get_user_profiles_bulk(self, user_ids: List[int]) -> Dict[int, User]:
        """Массово получает профили пользователей одним MGET запросом для производительности."""
        if not user_ids:
            return {}
        
        keys = [self.keys.user_profile(user_id) for user_id in user_ids]
        results = await self.redis.mget(keys)
        
        profiles = {}
        for user_id, user_data_json in zip(user_ids, results):
            if user_data_json:
                try:
                    profiles[user_id] = User.model_validate_json(user_data_json)
                except Exception as e:
                    logger.error(f"Не удалось десериализовать профиль для пользователя {user_id} при массовой загрузке: {e}")
        return profiles

    async def find_user(self, query: str) -> Optional[User]:
        """
        Находит пользователя по ID или username.
        """
        query = query.strip().replace('@', '')
        if query.isdigit():
            return await self.get_user(int(query))
        
        # ИНДЕКСАЦИЯ И ПОИСК ПО USERNAME
        # Создаем ключ для обратного индекса: username -> user_id
        username_index_key = self.keys.username_to_id_index()
        user_id = await self.redis.hget(username_index_key, query.lower())
        
        if user_id:
            return await self.get_user(int(user_id))

        logger.warning(f"Пользователь с username '{query}' не найден в индексе.")
        return None

    async def update_username_index(self, user: User):
        """
        Обновляет индекс username -> user_id при регистрации или обновлении профиля.
        """
        if user.username:
            username_index_key = self.keys.username_to_id_index()
            await self.redis.hset(username_index_key, user.username.lower(), user.id)

