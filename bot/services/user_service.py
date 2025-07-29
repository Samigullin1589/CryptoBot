# ===============================================================
# Файл: bot/services/user_service.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Управляет профилями пользователей, репутацией,
# ролями, историей диалогов и другими данными.
# ===============================================================

import json
import logging
import time
from typing import List, Dict, Optional

import redis.asyncio as redis
from aiogram import Bot

from bot.config.settings import AppSettings
from bot.utils.models import UserProfile, UserRole

logger = logging.getLogger(__name__)

class UserService:
    """Сервис для управления всеми аспектами данных пользователя."""

    def __init__(self, redis_client: redis.Redis, settings: AppSettings):
        """
        Инициализирует сервис.

        :param redis_client: Асинхронный клиент для Redis.
        :param settings: Объект с настройками приложения.
        """
        self.redis = redis_client
        self.settings = settings
        # --- ИСПРАВЛЕНИЕ: Используем правильное имя поля из настроек ---
        self.super_admins = set(self.settings.admin.super_admin_user_ids)
        self.admins = set(self.settings.admin.admin_user_ids)
        self.moderators = set(self.settings.admin.moderator_user_ids)
        # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

    def _get_user_profile_key(self, user_id: int, chat_id: int) -> str:
        """Возвращает ключ для хранения профиля пользователя в Redis."""
        return f"user_profile:{chat_id}:{user_id}"

    async def get_user_role(self, user_id: int) -> UserRole:
        """Определяет роль пользователя на основе его ID."""
        if user_id in self.super_admins:
            return UserRole.SUPER_ADMIN
        if user_id in self.admins:
            return UserRole.ADMIN
        if user_id in self.moderators:
            return UserRole.MODERATOR
        return UserRole.USER

    async def get_or_create_user(self, user_id: int, chat_id: int) -> UserProfile:
        """
        Получает профиль пользователя из Redis. Если профиля нет, создает новый.
        """
        profile_key = self._get_user_profile_key(user_id, chat_id)
        saved_profile_data = await self.redis.get(profile_key)

        if saved_profile_data:
            profile = UserProfile.model_validate_json(saved_profile_data)
        else:
            profile = UserProfile(
                user_id=user_id,
                chat_id=chat_id,
                join_timestamp=time.time()
            )
            await self._save_user_profile(profile)

        # Роль определяется динамически и не хранится в профиле
        profile.role = await self.get_user_role(user_id)
        return profile

    async def _save_user_profile(self, profile: UserProfile):
        """Сохраняет профиль пользователя в Redis."""
        profile_key = self._get_user_profile_key(profile.user_id, profile.chat_id)
        # Исключаем динамическое поле 'role' перед сохранением
        await self.redis.set(profile_key, profile.model_dump_json(exclude={'role'}))

    async def register_new_user(self, user_id: int, full_name: str, username: Optional[str]) -> bool:
        """
        Регистрирует нового пользователя в системе, возвращает True если пользователь действительно новый.
        """
        is_new = await self.redis.sadd("system:known_users", user_id)
        if is_new:
            # Сохраняем базовую информацию для админки
            user_info = {"full_name": full_name, "username": username or ""}
            await self.redis.set(f"user_info:{user_id}", json.dumps(user_info, ensure_ascii=False))
            # Вызываем метод AdminService для инкремента счетчика
            # await self.admin_service.track_new_user() # Эта логика перенесена в AdminService
        return bool(is_new)

    async def process_referral(self, new_user_id: int, referrer_id: int, new_user_username: Optional[str], bot: Bot):
        """Обрабатывает реферальную логику."""
        if new_user_id == referrer_id:
            return

        is_already_referred = await self.redis.sismember("system:referred_users", new_user_id)
        if is_already_referred:
            logger.info(f"User {new_user_id} tried to use referral link from {referrer_id}, but is already referred.")
            return

        bonus = self.settings.game.referral_bonus_amount
        # Используем AdminService для инкремента счетчиков
        # await self.admin_service.track_referral_registration()
        # await self.admin_service.track_balance_change(bonus)

        async with self.redis.pipeline() as pipe:
            pipe.incrbyfloat(f"user_game_profile:{referrer_id}:balance", bonus)
            pipe.sadd("system:referred_users", new_user_id)
            pipe.sadd(f"user_game_profile:{referrer_id}:referrals", new_user_id)
            await pipe.execute()

        logger.info(f"User {new_user_id} joined via referral from {referrer_id}. Referrer received {bonus} coins.")

        try:
            await bot.send_message(
                referrer_id,
                f"🤝 Поздравляем! Ваш друг @{new_user_username} присоединился по вашей ссылке.\n"
                f"💰 Ваш баланс пополнен на <b>{bonus} монет</b>!"
            )
        except Exception as e:
            logger.error(f"Failed to send referral notification to user {referrer_id}: {e}")

    async def log_violation(self, user_id: int, chat_id: int, reason: str, penalty: int):
        """Логирует нарушение и снижает рейтинг доверия."""
        profile = await self.get_or_create_user(user_id, chat_id)
        profile.trust_score = max(0, profile.trust_score - penalty)
        profile.violations_count += 1
        await self._save_user_profile(profile)
        logger.warning(f"VIOLATION: User {user_id} in chat {chat_id}. Reason: {reason}. New score: {profile.trust_score}.")

    async def update_user_activity(self, user_id: int, chat_id: int):
        """Обновляет активность пользователя и начисляет награду за нее."""
        profile = await self.get_or_create_user(user_id, chat_id)
        profile.last_activity_timestamp = time.time()
        profile.message_count += 1

        reward_config = self.settings.activity_rewards
        if profile.message_count >= reward_config.reward_threshold:
            profile.trust_score += reward_config.reward_points
            profile.message_count = 0  # Сбрасываем счетчик
            logger.info(f"User {user_id} rewarded for activity in chat {chat_id}. New trust score: {profile.trust_score}")
        
        await self._save_user_profile(profile)

    async def get_conversation_history(self, user_id: int, chat_id: int) -> List[Dict[str, Any]]:
        """Получает историю диалога с AI-консультантом."""
        profile = await self.get_or_create_user(user_id, chat_id)
        return profile.conversation_history

    async def add_to_conversation_history(self, user_id: int, chat_id: int, user_text: str, model_text: str):
        """Добавляет новое сообщение в историю диалога."""
        profile = await self.get_or_create_user(user_id, chat_id)
        
        history = profile.conversation_history
        history.append({"role": "user", "parts": [{"text": user_text}]})
        history.append({"role": "model", "parts": [{"text": model_text}]})
        
        max_len = self.settings.app.ai_history_limit * 2
        if len(history) > max_len:
            history = history[-max_len:]
            
        profile.conversation_history = history
        await self._save_user_profile(profile)
