# bot/services/mining_game_service.py
# Дата обновления: 23.08.2025
# Версия: 2.1.0
# Описание: Основной сервис, управляющий игровой логикой "виртуального майнинга".

import json
import time
from typing import Dict, List, Optional, Tuple

from aiogram.types import User as TelegramUser
from loguru import logger
from pydantic import ValidationError
from redis.asyncio import Redis

from bot.config.settings import settings
from bot.services.achievement_service import AchievementService
from bot.services.asic_service import AsicService
from bot.services.user_service import UserService
from bot.utils.keys import KeyFactory
from bot.utils.models import AsicMiner, ElectricityTariff, MiningSession, UserGameStats
from bot.utils.redis_lock import LockAcquisitionError, RedisLock
from bot.config.settings import MiningGameServiceConfig


class MiningGameService:
    """
    Управляет всей доменной логикой игры "виртуальный майнинг".
    Отвечает за старт/стоп сессий, покупку/выбор тарифов и ведение статистики.
    """

    def __init__(
        self,
        user_service: UserService,
        asic_service: AsicService,
        achievement_service: AchievementService,
        redis_client: Redis,
    ):
        """
        Инициализирует сервис с необходимыми зависимостями.
        """
        self.redis = redis_client
        self.user_service = user_service
        self.asic_service = asic_service
        self.achievement_service = achievement_service
        self.config: MiningGameServiceConfig = settings.game
        self.keys = KeyFactory
        logger.info("Сервис MiningGameService инициализирован.")

    async def get_active_session(self, user_id: int) -> Optional[MiningSession]:
        """Возвращает активную майнинг-сессию пользователя, если она есть."""
        session_data = await self.redis.hgetall(self.keys.active_session(user_id))
        if not session_data:
            return None
        try:
            return MiningSession.model_validate(session_data)
        except ValidationError as e:
            logger.error(f"Ошибка валидации данных сессии для user_id={user_id}: {e}. Данные: {session_data}")
            await self.redis.delete(self.keys.active_session(user_id))
            return None

    async def get_user_game_stats(self, user_id: int) -> UserGameStats:
        """Возвращает игровую статистику пользователя."""
        stats_data = await self.redis.hgetall(self.keys.user_game_stats(user_id))
        return UserGameStats.model_validate(stats_data or {})

    async def purchase_and_start_session(self, user_id: int, selected_asic: AsicMiner) -> Tuple[str, bool]:
        """
        Атомарно покупает и запускает майнинг-сессию.
        Возвращает кортеж (сообщение_для_пользователя, флаг_успеха).
        """
        lock_key = f"lock:session:{user_id}"
        try:
            async with RedisLock(self.redis, lock_key, timeout=5):
                return await self._atomic_start_session(user_id, selected_asic)
        except LockAcquisitionError:
            logger.warning(f"Пользователь {user_id} слишком часто пытается начать сессию.")
            return "⏳ Пожалуйста, подождите несколько секунд перед повторной попыткой.", False
        except Exception as e:
            logger.exception(f"Непредвиденная ошибка при старте сессии для user_id={user_id}: {e}")
            return "Произошла внутренняя ошибка. Попробуйте позже.", False

    async def _atomic_start_session(self, user_id: int, selected_asic: AsicMiner) -> Tuple[str, bool]:
        """Внутренняя логика запуска сессии, выполняется под блокировкой."""
        if await self.redis.exists(self.keys.active_session(user_id)):
            return "У вас уже есть активная сессия майнинга.", False

        price = selected_asic.price or 0.0
        if price < 0:
            return "Ошибка: цена оборудования не может быть отрицательной.", False

        if price > 0:
            debit_success, _ = await self.user_service.debit_balance(
                user_id, price, reason=f"Покупка ASIC: {selected_asic.name}"
            )
            if not debit_success:
                price_f = f"{price:,.2f}".replace(",", " ")
                return f"Недостаточно средств для покупки <b>{selected_asic.name}</b> (нужно {price_f} монет).", False

        now = time.time()
        current_tariff = await self._get_current_tariff_object(user_id)
        
        session = MiningSession(
            asic_json=selected_asic.model_dump_json(),
            started_at=now,
            ends_at=now + self.config.session_duration_minutes * 60,
            tariff_json=current_tariff.model_dump_json()
        )

        try:
            pipe = self.redis.pipeline()
            pipe.hset(self.keys.active_session(user_id), mapping=session.model_dump(mode="json"))
            pipe.expire(self.keys.active_session(user_id), self.config.session_duration_minutes * 60 + 10)
            pipe.hincrby(self.keys.user_game_stats(user_id), "sessions_total", 1)
            if price > 0:
                pipe.hincrbyfloat(self.keys.user_game_stats(user_id), "spent_total", price)
            await pipe.execute()

            await self.achievement_service.process_static_event(user_id, "mining_session_started")
            
            duration_min = self.config.session_duration_minutes
            msg = (
                f"🎉 Сессия запущена!\n\n"
                f"Оборудование: <b>{selected_asic.name}</b>\n"
                f"Длительность: <b>{duration_min} мин.</b>"
            )
            return msg, True
        except Exception as e:
            logger.exception(f"Ошибка при создании сессии в Redis для user_id={user_id}: {e}")
            await self.user_service.credit_balance(user_id, price, reason="Возврат средств после сбоя старта сессии")
            return "Не удалось запустить сессию из-за ошибки базы данных. Средства возвращены.", False

    async def get_electricity_tariffs(self) -> List[ElectricityTariff]:
        """Возвращает список всех доступных тарифов из конфигурации."""
        return [ElectricityTariff(name=name, **data.model_dump()) for name, data in self.config.electricity_tariffs.items()]

    async def get_user_tariffs_info(self, user_id: int) -> Tuple[List[str], str]:
        """Возвращает список купленных тарифов и название текущего."""
        owned_key = self.keys.owned_tariffs(user_id)
        profile_key = self.keys.user_profile(user_id)
        
        owned_raw, current_raw = await asyncio.gather(
            self.redis.smembers(owned_key),
            self.redis.hget(profile_key, "current_tariff")
        )
        
        owned = list(owned_raw or [])
        if self.config.default_electricity_tariff not in owned:
            owned.append(self.config.default_electricity_tariff)
            
        current = current_raw or self.config.default_electricity_tariff
        return sorted(owned), current

    async def _get_current_tariff_object(self, user_id: int) -> ElectricityTariff:
        """Возвращает Pydantic-объект текущего тарифа пользователя."""
        _, current_tariff_name = await self.get_user_tariffs_info(user_id)
        tariff_data = self.config.electricity_tariffs.get(current_tariff_name)
        
        if not tariff_data:
            default_name = self.config.default_electricity_tariff
            tariff_data = self.config.electricity_tariffs[default_name]
            return ElectricityTariff(name=default_name, **tariff_data.model_dump())
            
        return ElectricityTariff(name=current_tariff_name, **tariff_data.model_dump())

    async def select_tariff(self, user_id: int, tariff_name: str) -> str:
        """Выбирает тариф в качестве текущего, если он куплен."""
        all_tariffs = self.config.electricity_tariffs.keys()
        if tariff_name not in all_tariffs:
            return "Такой тариф не существует."

        owned, _ = await self.get_user_tariffs_info(user_id)
        if tariff_name not in owned:
            return "Сначала необходимо приобрести этот тариф."

        await self.redis.hset(self.keys.user_profile(user_id), "current_tariff", tariff_name)
        return f"🔌 Тариф <b>{tariff_name}</b> успешно выбран."

    async def buy_tariff(self, user_id: int, tariff_name: str) -> str:
        """Покупает тариф, если он еще не куплен и у пользователя достаточно средств."""
        tariff = self.config.electricity_tariffs.get(tariff_name)
        if not tariff:
            return "Такой тариф не существует."

        owned, _ = await self.get_user_tariffs_info(user_id)
        if tariff_name in owned:
            return "Этот тариф уже куплен."

        price = tariff.unlock_price
        if price > 0:
            debit_success, _ = await self.user_service.debit_balance(
                user_id, price, reason=f"Покупка тарифа {tariff_name}"
            )
            if not debit_success:
                price_f = f"{price:,.0f}".replace(",", " ")
                return f"Недостаточно средств для покупки тарифа <b>{tariff_name}</b> (нужно {price_f} монет)."
        
        pipe = self.redis.pipeline()
        pipe.sadd(self.keys.owned_tariffs(user_id), tariff_name)
        pipe.hset(self.keys.user_profile(user_id), "current_tariff", tariff_name)
        if price > 0:
            pipe.hincrbyfloat(self.keys.user_game_stats(user_id), "spent_total", price)
        await pipe.execute()

        return f"🎉 Тариф <b>{tariff_name}</b> успешно приобретён и выбран текущим!"