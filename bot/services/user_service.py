# ===============================================================
# Файл: bot/services/user_service.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Централизованный сервис для управления профилями,
# ролями, репутацией и историей диалогов пользователей.
# ===============================================================

import time
import json
import logging
from typing import List, Dict, Optional

import redis.asyncio as redis
from aiogram import Bot
from aiogram.types import Message

from bot.config.settings import AppSettings
from bot.utils.models import UserProfile, UserRole

logger = logging.getLogger(__name__)

class UserService:
    """Сервис для управления всеми данными, связанными с пользователем."""

    def __init__(self, redis_client: redis.Redis, settings: AppSettings):
        self.redis = redis_client
        self.settings = settings
        # Создаем множества ID для быстрого поиска ролей
        self.super_admins = set(self.settings.admin.super_admin_ids)
        self.admins = set(self.settings.admin.admin_ids)
        self.moderators = set(self.settings.admin.moderator_ids)

    def _get_user_profile_key(self, user_id: int) -> str:
        """Генерирует ключ для хранения профиля пользователя в Redis."""
        return f"user_profile:{user_id}"

    async def get_or_create_user(self, user_id: int, full_name: str = "", username: str = "") -> UserProfile:
        """
        Получает профиль пользователя из Redis. Если его нет, создает новый.
        
        :param user_id: Уникальный ID пользователя Telegram.
        :param full_name: Полное имя пользователя.
        :param username: Юзернейм пользователя.
        :return: Экземпляр UserProfile.
        """
        profile_key = self._get_user_profile_key(user_id)
        saved_profile_data = await self.redis.get(profile_key)

        if saved_profile_data:
            try:
                profile = UserProfile.model_validate_json(saved_profile_data)
                # Динамически обновляем роль при каждом получении профиля
                profile.role = self._get_user_role(user_id)
                return profile
            except Exception as e:
                logger.error(f"Ошибка валидации профиля пользователя {user_id}: {e}. Создается новый профиль.")
        
        # Создание нового профиля, если он не найден или поврежден
        new_profile = UserProfile(
            user_id=user_id,
            full_name=full_name,
            username=username,
            join_timestamp=time.time(),
            role=self._get_user_role(user_id)
        )
        await self._save_user_profile(new_profile)
        logger.info(f"Создан новый профиль для пользователя {user_id}.")
        return new_profile

    def _get_user_role(self, user_id: int) -> UserRole:
        """Определяет роль пользователя на основе его ID."""
        if user_id in self.super_admins:
            return UserRole.SUPER_ADMIN
        if user_id in self.admins:
            return UserRole.ADMIN
        if user_id in self.moderators:
            return UserRole.MODERATOR
        return UserRole.USER

    async def _save_user_profile(self, profile: UserProfile):
        """Сохраняет профиль пользователя в Redis."""
        profile_key = self._get_user_profile_key(profile.user_id)
        # Сохраняем как JSON-строку
        await self.redis.set(profile_key, profile.model_dump_json())

    async def register_new_user(self, user_id: int):
        """Регистрирует нового уникального пользователя в системе."""
        is_new = await self.redis.sadd("system:known_users", user_id)
        if is_new:
            # Используем атомарный счетчик для общего числа пользователей
            await self.redis.incr("stats:total_users")
            # Добавляем в sorted set для отслеживания по дате регистрации
            await self.redis.zadd("stats:user_join_dates", {str(user_id): int(time.time())})

    async def process_referral(self, message: Message, referrer_id: int, bot: Bot):
        """Обрабатывает реферальную логику."""
        new_user_id = message.from_user.id
        
        # Проверяем, не был ли пользователь уже рефералом
        is_already_referred = await self.redis.sismember("system:referred_users", new_user_id)
        if is_already_referred:
            logger.info(f"Пользователь {new_user_id} уже является рефералом.")
            return

        bonus = self.settings.game.referral_bonus
        
        # Атомарно обновляем данные
        async with self.redis.pipeline() as pipe:
            pipe.incrbyfloat(f"user_profile:{referrer_id}:balance", bonus)
            pipe.incr(f"user_profile:{referrer_id}:referrals_count")
            pipe.sadd("system:referred_users", new_user_id)
            results = await pipe.execute()
        
        logger.info(f"Пользователь {new_user_id} присоединился по реферальной ссылке от {referrer_id}. Реферер получил {bonus} монет.")

        try:
            await bot.send_message(
                referrer_id,
                f"🤝 Поздравляем! Ваш друг @{message.from_user.username} присоединился по вашей ссылке.\n"
                f"💰 Ваш баланс пополнен на <b>{bonus} монет</b>!"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление о реферале пользователю {referrer_id}: {e}")

    async def log_violation(self, user_id: int, reason: str, penalty: int, details: Optional[dict] = None):
        """Логирует нарушение, понижает рейтинг доверия."""
        profile = await self.get_or_create_user(user_id)
        profile.trust_score = max(0, profile.trust_score - penalty)
        profile.violations_count += 1
        await self._save_user_profile(profile)
        logger.warning(f"НАРУШЕНИЕ: Пользователь {user_id}. Причина: {reason}. Новый рейтинг: {profile.trust_score}. Детали: {details}")

    async def update_user_activity(self, user_id: int):
        """Обновляет время последней активности и начисляет очки за нее."""
        profile = await self.get_or_create_user(user_id)
        profile.last_activity_timestamp = time.time()
        profile.message_count += 1

        reward_threshold = self.settings.user.activity_reward_threshold
        if profile.message_count >= reward_threshold:
            profile.trust_score += self.settings.user.activity_reward_points
            profile.message_count = 0  # Сбрасываем счетчик
            logger.info(f"Пользователь {user_id} награжден за активность. Новый рейтинг: {profile.trust_score}")
        
        await self._save_user_profile(profile)
        # Также обновляем в sorted set для быстрой выборки активных пользователей
        await self.redis.zadd("stats:user_activity_dates", {str(user_id): int(time.time())})

    async def get_conversation_history(self, user_id: int) -> List[Dict[str, any]]:
        """Получает историю диалога пользователя с AI."""
        profile = await self.get_or_create_user(user_id)
        try:
            return json.loads(profile.conversation_history_json)
        except json.JSONDecodeError:
            return []

    async def add_to_conversation_history(self, user_id: int, user_text: str, model_text: str):
        """Добавляет новое сообщение в историю диалога."""
        history = await self.get_conversation_history(user_id)
        
        history.append({"role": "user", "parts": [{"text": user_text}]})
        history.append({"role": "model", "parts": [{"text": model_text}]})
        
        max_len = self.settings.ai_consultant.max_history_length * 2
        if len(history) > max_len:
            history = history[-max_len:]
            
        profile = await self.get_or_create_user(user_id)
        profile.conversation_history_json = json.dumps(history, ensure_ascii=False)
        await self._save_user_profile(profile)
