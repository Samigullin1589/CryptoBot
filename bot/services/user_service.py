# ===============================================================
# Файл: bot/services/user_service.py (ПРОДАКШН-ВЕРСИЯ 2025 - ОКОНЧАТЕЛЬНАЯ v2)
# Описание: Управляет данными пользователей с использованием атомарных
# операций, блокировок и эффективных структур данных в Redis.
# ===============================================================

import asyncio
import json
import logging
import time
from typing import List, Dict, Optional, Any, Set

import redis.asyncio as redis

from bot.config.settings import AppSettings
from bot.utils.models import UserProfile, UserRole
from bot.utils.keys import KeyFactory

logger = logging.getLogger(__name__)

class RedisLock:
    """Асинхронный контекстный менеджер для блокировки."""
    def __init__(self, redis_client: redis.Redis, lock_key: str, timeout: int = 10):
        self.redis = redis_client
        self.lock_key = lock_key
        self.timeout = timeout

    async def __aenter__(self):
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            if await self.redis.set(self.lock_key, "1", nx=True, ex=self.timeout):
                return self
            await asyncio.sleep(0.1)
        raise TimeoutError(f"Не удалось получить блокировку для ключа {self.lock_key} за {self.timeout}с")

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.redis.delete(self.lock_key)


class UserService:
    """Сервис для управления всеми аспектами данных пользователя."""
    def __init__(self, redis_client: redis.Redis, settings: AppSettings):
        self.redis = redis_client
        self.settings = settings
        self.keys = KeyFactory
        self.super_admins: Set[int] = set(self.settings.admin.super_admin_ids)
        self.admins: Set[int] = set(self.settings.admin.admin_ids)
        self.moderators: Set[int] = set(self.settings.admin.moderator_ids)

    async def get_user_role(self, user_id: int) -> UserRole:
        """Определяет роль пользователя на основе его ID."""
        if user_id in self.super_admins: return UserRole.SUPER_ADMIN
        if user_id in self.admins: return UserRole.ADMIN
        if user_id in self.moderators: return UserRole.MODERATOR
        return UserRole.USER

    async def get_or_create_user(self, user_id: int, full_name: str, username: Optional[str]) -> UserProfile:
        """Получает профиль пользователя из Redis Hash. Если нет, создает новый."""
        profile_key = self.keys.user_profile(user_id)
        
        # Используем hsetnx для атомарного создания поля, что сигнализирует о новом пользователе
        is_new = await self.redis.hsetnx(profile_key, 'user_id', user_id)

        if is_new:
            role = await self.get_user_role(user_id)
            profile_data = {
                "full_name": full_name,
                "username": username or "",
                "join_timestamp": time.time(),
                "last_activity_timestamp": time.time(),
                "trust_score": 100,
                "message_count": 0,
                "violations_count": 0,
                "electricity_cost": 0.05, # Значение по умолчанию
                "role": role.value # Сохраняем числовое значение роли
            }
            await self.redis.hmset(profile_key, profile_data)
            await self.redis.sadd(self.keys.known_users_set(), user_id)
            await self.redis.zadd(self.keys.user_first_seen_zset(), {str(user_id): int(time.time())})
            return UserProfile.model_validate(profile_data)
        
        # Если пользователь не новый, просто получаем его данные
        profile_data = await self.redis.hgetall(profile_key)
        return UserProfile.model_validate(profile_data)

    async def get_user_profile(self, user_id: int) -> Optional[UserProfile]:
        """Получает профиль пользователя, если он существует."""
        profile_data = await self.redis.hgetall(self.keys.user_profile(user_id))
        return UserProfile.model_validate(profile_data) if profile_data else None

    async def get_user_info(self, user_id: int) -> Dict[str, Any]:
        """Получает базовую информацию о пользователе (имя, юзернейм)."""
        data = await self.redis.hgetall(self.keys.user_profile(user_id))
        return {"full_name": data.get("full_name", ""), "username": data.get("username", "")}

    async def set_user_electricity_cost(self, user_id: int, cost: float):
        """Устанавливает персональную стоимость электроэнергии для пользователя."""
        await self.redis.hset(self.keys.user_profile(user_id), "electricity_cost", cost)

    async def process_referral(self, new_user_id: int, referrer_id: int) -> bool:
        """Обрабатывает реферальную логику. Возвращает True, если бонус начислен."""
        if new_user_id == referrer_id or await self.redis.sismember(self.keys.game_referred_users_set(), new_user_id):
            return False

        bonus = self.settings.game.referral_bonus_amount
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.hincrbyfloat(self.keys.game_profile(referrer_id), "balance", bonus)
            pipe.sadd(self.keys.game_referred_users_set(), new_user_id)
            await pipe.execute()
        logger.info(f"User {new_user_id} joined via referral from {referrer_id}. Referrer received {bonus} coins.")
        return True

    async def log_violation(self, user_id: int, reason: str, penalty: int):
        """Логирует нарушение, атомарно изменяя рейтинг и счетчик."""
        profile_key = self.keys.user_profile(user_id)
        async with RedisLock(self.redis, f"lock:{profile_key}", timeout=5):
            current_score = int(await self.redis.hget(profile_key, 'trust_score') or 100)
            new_score = max(0, current_score - penalty)
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.hset(profile_key, 'trust_score', new_score)
                pipe.hincrby(profile_key, 'violations_count', 1)
                await pipe.execute()
        logger.warning(f"VIOLATION: User {user_id}. Reason: {reason}. New score: {new_score}.")

    async def update_user_activity(self, user_id: int):
        """Атомарно обновляет активность пользователя и начисляет награду."""
        profile_key = self.keys.user_profile(user_id)
        now = int(time.time())
        
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.hset(profile_key, 'last_activity_timestamp', now)
            pipe.hincrby(profile_key, 'message_count', 1)
            pipe.zadd(self.keys.user_last_activity_zset(), {str(user_id): now})
            await pipe.execute()
