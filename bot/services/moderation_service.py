# bot/services/moderation_service.py
# Дата обновления: 20.08.2025
# Версия: 2.0.0
# Описание: Сервис для управления действиями модерации, такими как бан и мут,
# с сохранением состояния в Redis и применением наказаний через Telegram API.

import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from loguru import logger
from pydantic import ValidationError
from redis.asyncio import Redis

from bot.utils.dependencies import get_bot_instance, get_redis_client
from bot.utils.keys import KeyFactory
from bot.utils.models import BanRecord, MuteRecord


class ModerationService:
    """
    Управляет логикой банов и мутов. Сохраняет записи о наказаниях в Redis
    и выполняет соответствующие действия через Telegram Bot API.
    """

    def __init__(self):
        """Инициализирует сервис, получая зависимости из централизованного источника."""
        self.redis: Redis = get_redis_client()
        self.bot: Bot = get_bot_instance()
        self.keys = KeyFactory
        logger.info("Сервис ModerationService инициализирован.")

    # --- Управление банами ---

    async def create_ban_record(
        self, user_id: int, by_admin_id: int, reason: Optional[str] = None, duration: Optional[timedelta] = None
    ) -> BanRecord:
        """
        Создает и сохраняет запись о бане в Redis.

        :param user_id: ID пользователя, которого банят.
        :param by_admin_id: ID администратора, который выполнил действие.
        :param reason: Причина бана.
        :param duration: Длительность бана. None означает перманентный бан.
        :return: Pydantic-модель с информацией о бане.
        """
        created_at = datetime.now(timezone.utc)
        until = (created_at + duration) if duration else None

        record = BanRecord(
            user_id=user_id,
            by_admin_id=by_admin_id,
            reason=reason,
            created_at=created_at,
            until=until,
        )

        key = self.keys.ban_record(user_id)
        data = record.model_dump_json()
        ttl = int(duration.total_seconds()) if duration else None

        await self.redis.set(key, data, ex=ttl)
        logger.info(f"Создана запись о бане для user_id={user_id} администратором {by_admin_id}. Длительность: {duration}.")
        return record

    async def apply_ban_in_chat(self, chat_id: int, user_id: int, reason: str) -> bool:
        """Применяет бан к пользователю в указанном чате."""
        try:
            await self.bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
            logger.success(f"Пользователь {user_id} успешно забанен в чате {chat_id}. Причина: {reason}.")
            return True
        except TelegramBadRequest as e:
            logger.error(f"Не удалось забанить пользователя {user_id} в чате {chat_id}: {e.message}")
        except Exception as e:
            logger.exception(f"Непредвиденная ошибка при бане пользователя {user_id} в чате {chat_id}: {e}")
        return False

    async def unban(self, user_id: int) -> bool:
        """Удаляет запись о бане из Redis."""
        deleted_count = await self.redis.delete(self.keys.ban_record(user_id))
        if deleted_count > 0:
            logger.info(f"Запись о бане для user_id={user_id} удалена.")
        return deleted_count > 0

    async def get_ban_record(self, user_id: int) -> Optional[BanRecord]:
        """Получает информацию о бане пользователя из Redis."""
        raw_data = await self.redis.get(self.keys.ban_record(user_id))
        if not raw_data:
            return None
        try:
            return BanRecord.model_validate_json(raw_data)
        except (ValidationError, json.JSONDecodeError):
            logger.warning(f"Поврежденная запись о бане для user_id={user_id}. Запись будет удалена.")
            await self.redis.delete(self.keys.ban_record(user_id))
            return None

    # --- Управление мутами ---

    async def create_mute_record(
        self, user_id: int, by_admin_id: int, duration: timedelta, reason: Optional[str] = None
    ) -> MuteRecord:
        """
        Создает и сохраняет запись о муте (временном ограничении) в Redis.

        :param user_id: ID пользователя.
        :param by_admin_id: ID администратора.
        :param duration: Длительность мута.
        :param reason: Причина мута.
        :return: Pydantic-модель с информацией о муте.
        """
        created_at = datetime.now(timezone.utc)
        until = created_at + duration

        record = MuteRecord(
            user_id=user_id,
            by_admin_id=by_admin_id,
            reason=reason,
            created_at=created_at,
            until=until,
        )

        key = self.keys.mute_record(user_id)
        data = record.model_dump_json()
        ttl = int(duration.total_seconds())

        await self.redis.set(key, data, ex=max(ttl, 1))
        logger.info(f"Создана запись о муте для user_id={user_id} администратором {by_admin_id} на {duration}.")
        return record

    async def apply_mute_in_chat(self, chat_id: int, user_id: int, duration: timedelta) -> bool:
        """Применяет мут к пользователю в указанном чате."""
        try:
            until_date = datetime.now(timezone.utc) + duration
            await self.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions={"can_send_messages": False},
                until_date=until_date
            )
            logger.success(f"Пользователь {user_id} успешно заглушен в чате {chat_id} на {duration}.")
            return True
        except TelegramBadRequest as e:
            logger.error(f"Не удалось заглушить пользователя {user_id} в чате {chat_id}: {e.message}")
        except Exception as e:
            logger.exception(f"Непредвиденная ошибка при муте пользователя {user_id} в чате {chat_id}: {e}")
        return False

    async def unmute(self, user_id: int) -> bool:
        """Удаляет запись о муте из Redis."""
        deleted_count = await self.redis.delete(self.keys.mute_record(user_id))
        if deleted_count > 0:
            logger.info(f"Запись о муте для user_id={user_id} удалена.")
        return deleted_count > 0

    async def get_mute_record(self, user_id: int) -> Optional[MuteRecord]:
        """Получает информацию о муте пользователя из Redis."""
        raw_data = await self.redis.get(self.keys.mute_record(user_id))
        if not raw_data:
            return None
        try:
            return MuteRecord.model_validate_json(raw_data)
        except (ValidationError, json.JSONDecodeError):
            logger.warning(f"Поврежденная запись о муте для user_id={user_id}. Запись будет удалена.")
            await self.redis.delete(self.keys.mute_record(user_id))
            return None