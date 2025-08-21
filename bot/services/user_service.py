# bot/services/user_service.py
# Дата обновления: 21.08.25
# Версия: 2.0.0
# Описание: Центральный сервис для управления данными пользователей, включая профили,
# балансы, историю сообщений и отслеживание активности. Обеспечивает
# атомарность операций и целостность данных.

import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from aiogram.types import User as TelegramUser
from loguru import logger
from pydantic import ValidationError
from redis.asyncio import Redis

from bot.config.settings import settings
from bot.utils.dependencies import get_redis_client
from bot.utils.keys import KeyFactory
from bot.utils.models import User, UserRole


class UserService:
    """
    Сервис для управления данными пользователей в Redis.
    Является единственным источником правды для профилей и балансов.
    """

    def __init__(self):
        """Инициализирует сервис, получая зависимости из централизованного источника."""
        self.redis: Redis = get_redis_client()
        self.keys = KeyFactory
        self.config = settings.AI
        logger.info("Сервис UserService инициализирован.")

    async def get_user(self, user_id: int) -> Optional[User]:
        """
        Получает данные пользователя из Redis и валидирует их с помощью Pydantic.
        
        :param user_id: ID пользователя Telegram.
        :return: Объект User или None, если пользователь не найден или данные повреждены.
        """
        user_key = self.keys.user_profile(user_id)
        user_data_dict = await self.redis.hgetall(user_key)
        
        if not user_data_dict:
            return None
        
        try:
            # Pydantic автоматически преобразует типы (например, строки в int/float)
            return User.model_validate(user_data_dict)
        except ValidationError as e:
            logger.error(f"Ошибка валидации данных для пользователя {user_id}: {e}. Данные: {user_data_dict}")
            # В случае поврежденных данных, лучше вернуть None, чем работать с некорректным объектом
            return None

    async def save_user(self, user: User, old_username: Optional[str] = None):
        """
        Атомарно сохраняет модель пользователя в Redis HASH и обновляет индекс username -> user_id.
        
        :param user: Объект пользователя для сохранения.
        :param old_username: Предыдущее имя пользователя для корректного удаления старого индекса.
        """
        user_key = self.keys.user_profile(user.id)
        # model_dump преобразует модель в словарь, готовый для сохранения
        user_data_to_save = user.model_dump(mode='json')

        async with self.redis.pipeline(transaction=True) as pipe:
            # Очищаем старые данные и записываем новые
            pipe.delete(user_key)
            pipe.hset(user_key, mapping=user_data_to_save)
            
            current_username = user.username.lower() if user.username else None
            old_username_lower = old_username.lower() if old_username else None

            # Атомарно обновляем индекс username -> user_id
            if current_username != old_username_lower and old_username_lower:
                pipe.hdel(self.keys.username_to_id_map(), old_username_lower)
            
            if current_username:
                pipe.hset(self.keys.username_to_id_map(), current_username, user.id)
            
            await pipe.execute()
        logger.info(f"Данные для пользователя {user.id} (@{user.username}) сохранены.")

    async def get_or_create_user(self, tg_user: TelegramUser) -> Tuple[User, bool]:
        """
        Получает пользователя из базы. Если его нет - создает.
        Если данные (имя, username) изменились - атомарно обновляет.

        :param tg_user: Объект пользователя из aiogram.
        :return: Кортеж (объект User, флаг is_created).
        """
        existing_user = await self.get_user(tg_user.id)
        
        if existing_user:
            # Проверяем, нужно ли обновить данные
            if (existing_user.username != tg_user.username or
                existing_user.first_name != tg_user.full_name):
                
                old_username = existing_user.username
                existing_user.username = tg_user.username
                existing_user.first_name = tg_user.full_name
                
                await self.save_user(existing_user, old_username=old_username)
                logger.info(f"Обновлены данные для пользователя {tg_user.id} (@{tg_user.username}).")
            return existing_user, False
        
        # Создаем нового пользователя
        new_user = User(
            id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.full_name,
            language_code=tg_user.language_code,
            role=UserRole.USER
        )
        
        await self.save_user(new_user)
        await self.redis.sadd(self.keys.all_users_set(), new_user.id)
        logger.success(f"Зарегистрирован новый пользователь {tg_user.id} (@{tg_user.username}).")
        return new_user, True

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Находит пользователя по его @username через индекс в Redis."""
        username_lower = username.lower().lstrip('@')
        user_id = await self.redis.hget(self.keys.username_to_id_map(), username_lower)
        if user_id:
            return await self.get_user(int(user_id))
        return None

    async def credit_balance(self, user_id: int, amount: float, reason: str) -> Tuple[bool, float]:
        """
        Атомарно пополняет баланс пользователя.

        :param user_id: ID пользователя.
        :param amount: Сумма пополнения (должна быть положительной).
        :param reason: Причина операции для логирования.
        :return: Кортеж (успех, новый_баланс).
        """
        if amount <= 0:
            return False, 0.0
        
        user_key = self.keys.user_profile(user_id)
        new_balance = await self.redis.hincrbyfloat(user_key, "balance", amount)
        logger.info(f"Баланс user_id={user_id} пополнен на {amount}. Причина: {reason}. Новый баланс: {new_balance}")
        return True, new_balance

    async def debit_balance(self, user_id: int, amount: float, reason: str) -> Tuple[bool, float]:
        """
        Атомарно списывает средства с баланса пользователя с проверкой на достаточность.

        :param user_id: ID пользователя.
        :param amount: Сумма списания (должна быть положительной).
        :param reason: Причина операции для логирования.
        :return: Кортеж (успех, новый_баланс).
        """
        if amount <= 0:
            return False, 0.0

        user_key = self.keys.user_profile(user_id)
        
        # Используем WATCH для обеспечения атомарности операции "проверить и списать"
        async with self.redis.pipeline(transaction=True) as pipe:
            try:
                await pipe.watch(user_key)
                current_balance_raw = await pipe.hget(user_key, "balance")
                current_balance = float(current_balance_raw or 0.0)

                if current_balance < amount:
                    logger.warning(f"Недостаточно средств для списания у user_id={user_id}. Требуется: {amount}, в наличии: {current_balance}.")
                    return False, current_balance

                pipe.multi()
                pipe.hincrbyfloat(user_key, "balance", -amount)
                result = await pipe.execute()
                new_balance = result[0]
                
                logger.info(f"Списано {amount} с баланса user_id={user_id}. Причина: {reason}. Новый баланс: {new_balance}")
                return True, new_balance
            except redis.WatchError:
                logger.warning(f"Конфликт транзакции при списании баланса для user_id={user_id}. Повторная попытка не выполняется.")
                return False, 0.0

    async def get_all_user_ids(self) -> List[int]:
        """Возвращает список ID всех зарегистрированных пользователей."""
        user_ids_raw = await self.redis.smembers(self.keys.all_users_set())
        return [int(user_id) for user_id in user_ids_raw]

    async def update_user_activity(self, user_id: int):
        """Отмечает активность пользователя за текущий день и неделю."""
        now = datetime.now(timezone.utc)
        today_str = now.strftime('%Y-%m-%d')
        week_str = now.strftime('%Y-%U')
        
        day_key = f"stats:active_users:day:{today_str}"
        week_key = f"stats:active_users:week:{week_str}"

        async with self.redis.pipeline(transaction=False) as pipe:
            pipe.sadd(day_key, user_id)
            pipe.sadd(week_key, user_id)
            # Устанавливаем TTL с запасом
            pipe.expire(day_key, timedelta(days=2))
            pipe.expire(week_key, timedelta(weeks=2))
            await pipe.execute()

    async def get_conversation_history(self, user_id: int, chat_id: int) -> List[Dict]:
        """Получает историю переписки с AI для указанного пользователя и чата."""
        history_key = self.keys.conversation_history(user_id, chat_id)
        raw_history = await self.redis.lrange(history_key, 0, self.config.HISTORY_MAX_SIZE * 2)
        return [json.loads(msg) for msg in reversed(raw_history)]

    async def add_to_conversation_history(self, user_id: int, chat_id: int, user_text: str, ai_answer: str):
        """Добавляет пару сообщений (пользователь и AI) в историю диалога."""
        history_key = self.keys.conversation_history(user_id, chat_id)
        user_message = {"role": "user", "parts": [{"text": user_text}]}
        model_message = {"role": "model", "parts": [{"text": ai_answer}]}
        
        async with self.redis.pipeline(transaction=False) as pipe:
            # Добавляем сообщения в начало списка
            pipe.lpush(history_key, json.dumps(model_message, ensure_ascii=False))
            pipe.lpush(history_key, json.dumps(user_message, ensure_ascii=False))
            # Обрезаем список до максимального размера
            pipe.ltrim(history_key, 0, self.config.HISTORY_MAX_SIZE * 2 - 1)
            await pipe.execute()