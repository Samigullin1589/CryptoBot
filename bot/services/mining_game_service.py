# ===============================================================
# Файл: bot/services/mining_game_service.py (НОВЫЙ ФАЙЛ)
# Описание: Специализированный сервис для управления бизнес-логикой
# игры "Виртуальный Майнинг". Выделен из mining_tasks.py
# для соответствия принципу единой ответственности.
# ===============================================================

import time
import logging
from typing import Optional
import redis.asyncio as redis

from bot.config.settings import settings
from bot.utils.models import MiningSessionResult

logger = logging.getLogger(__name__)

class MiningGameService:
    """
    Сервис, инкапсулирующий всю бизнес-логику игры "Виртуальный Майнинг".
    """
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def end_session(self, user_id: int) -> Optional[MiningSessionResult]:
        """
        Завершает майнинг-сессию, выполняет расчеты и обновляет данные в Redis.
        Возвращает модель с результатами сессии или None, если сессия не найдена.
        """
        logger.info(f"Processing end of mining session for user {user_id}")

        session_key = f"mining:session:{user_id}"
        session_data_bytes = await self.redis.hgetall(session_key)
        
        if not session_data_bytes:
            logger.warning(f"No active mining session found for user {user_id} to end.")
            return None

        # Декодируем данные из Redis
        session_data = {k.decode('utf-8'): v.decode('utf-8') for k, v in session_data_bytes.items()}

        # --- Шаг 1: Получаем все необходимые данные для расчета ---
        
        # Тариф пользователя на электроэнергию
        user_tariff_key = f"user:{user_id}:tariff"
        user_tariff_name_bytes = await self.redis.get(user_tariff_key)
        user_tariff_name = user_tariff_name_bytes.decode('utf-8') if user_tariff_name_bytes else settings.game.DEFAULT_ELECTRICITY_TARIFF
        
        tariff_details = settings.game.ELECTRICITY_TARIFFS.get(user_tariff_name, {"cost_per_hour": 0.05, "unlock_price": 0})
        
        # Мощность и доходность оборудования из данных сессии
        power_watts = int(session_data.get("asic_power", 0))
        profitability_per_day = float(session_data.get("asic_profitability_per_day", 0))

        # --- Шаг 2: Вычисляем точное время работы и затраты ---
        start_time = int(session_data.get("start_time", int(time.time())))
        session_duration_real = int(time.time()) - start_time
        actual_duration_seconds = min(session_duration_real, settings.game.MINING_DURATION_SECONDS)

        # Расчет "грязного" дохода
        profit_per_second = profitability_per_day / 86400
        gross_earned = actual_duration_seconds * profit_per_second

        # Расчет затрат на электроэнергию
        power_kwh = (power_watts / 1000) * (actual_duration_seconds / 3600)
        total_electricity_cost = power_kwh * tariff_details["cost_per_hour"]
        
        net_earned = max(0, gross_earned - total_electricity_cost)

        # --- Шаг 3: Атомарно обновляем данные в Redis ---
        balance_key = f"user:{user_id}:balance"
        total_earned_key = f"user:{user_id}:total_earned"

        async with self.redis.pipeline() as pipe:
            pipe.delete(session_key)
            pipe.incrbyfloat(balance_key, net_earned)
            pipe.incrbyfloat(total_earned_key, net_earned)
            # Обновляем счетчики для админ-панели
            pipe.decr("stats:game:active_sessions")
            pipe.incrbyfloat("stats:game:total_balance", net_earned)
            await pipe.execute()

        logger.info(f"User {user_id} session ended. Gross: {gross_earned:.4f}, Cost: {total_electricity_cost:.4f}, Net: {net_earned:.4f}.")

        # --- Шаг 4: Возвращаем Pydantic-модель с результатами ---
        return MiningSessionResult(
            asic_name=session_data.get('asic_name', 'Неизвестный ASIC'),
            user_tariff_name=user_tariff_name,
            gross_earned=gross_earned,
            total_electricity_cost=total_electricity_cost,
            net_earned=net_earned
        )

