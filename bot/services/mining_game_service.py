# ===============================================================
# Файл: bot/services/mining_game_service.py (ПРОДАКШН-ВЕРСИЯ 2025 - ОКОНЧАТЕЛЬНАЯ)
# Описание: Полная бизнес-логика игры "Виртуальный Майнинг"
# с автоматическим завершением сессий и системой заявок на вывод.
# ===============================================================

import time
import logging
from typing import Optional, Tuple, List
from datetime import datetime, timedelta

import redis.asyncio as redis
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.config.settings import AppSettings
from bot.services.admin_service import AdminService
from bot.utils.models import MiningSessionResult, AsicMiner, UserProfile
from bot.keyboards.mining_keyboards import get_electricity_menu_keyboard
from bot.services.user_service import RedisLock

logger = logging.getLogger(__name__)

class _KeyFactory:
    """Внутренний генератор ключей для Redis, специфичных для игры."""
    @staticmethod
    def user_game_profile(user_id: int) -> str:
        return f"game:profile:{user_id}"

    @staticmethod
    def active_session(user_id: int) -> str:
        return f"game:session:{user_id}"
    
    @staticmethod
    def global_stats() -> str:
        return "game:stats"

class MiningGameService:
    """Сервис, инкапсулирующий всю бизнес-логику игры 'Виртуальный Майнинг'."""
    
    def __init__(self, redis_client: redis.Redis, admin_service: AdminService, scheduler: AsyncIOScheduler, settings: AppSettings):
        self.redis = redis_client
        self.admin = admin_service
        self.scheduler = scheduler
        self.settings = settings
        self.keys = _KeyFactory

    async def _get_user_game_profile(self, user_id: int) -> dict:
        """Получает игровой профиль пользователя или создает новый."""
        profile_key = self.keys.user_game_profile(user_id)
        profile = await self.redis.hgetall(profile_key)
        if not profile:
            default_tariff = self.settings.game.default_electricity_tariff.value
            new_profile = {
                "balance": 0.0,
                "total_earned": 0.0,
                "current_tariff": default_tariff,
                "owned_tariffs": default_tariff,
            }
            await self.redis.hmset(profile_key, new_profile)
            return new_profile
        return profile

    async def start_session(self, user_id: int, asic: AsicMiner) -> str:
        """Начинает майнинг-сессию и планирует ее автоматическое завершение."""
        session_key = self.keys.active_session(user_id)
        if await self.redis.exists(session_key):
            return "❌ У вас уже есть активная сессия майнинга!"

        profile = await self._get_user_game_profile(user_id)
        session_duration = self.settings.game.mining_duration_seconds
        end_time = datetime.now() + timedelta(seconds=session_duration)
        
        session_data = {
            "start_time": int(time.time()),
            "end_time_iso": end_time.isoformat(),
            "asic_name": asic.name,
            "asic_power": asic.power or 0,
            "asic_profitability_per_day": asic.profitability or 0.0,
            "user_tariff": profile['current_tariff']
        }
        job_id = f"end_session_for_user_{user_id}"
        async with self.redis.pipeline(transaction=True) as pipe:
            await pipe.hmset(session_key, session_data)
            await pipe.hincrby(self.keys.global_stats(), "active_sessions", 1)
            await pipe.execute()

        self.scheduler.add_job(
            "bot.services.mining_game_service:scheduled_end_session", # Путь для импорта
            trigger='date', run_date=end_time,
            args=[user_id], id=job_id, replace_existing=True
        )
        
        logger.info(f"User {user_id} started a mining session with {asic.name}. Scheduled to end at {end_time}.")
        return (f"✅ Сессия майнинга на <b>{asic.name}</b> успешно запущена!\n\n"
                f"Она автоматически завершится через <b>{session_duration / 3600:.0f} часов</b>. "
                f"Я пришлю уведомление с результатами.")

    async def end_session(self, user_id: int) -> Optional[MiningSessionResult]:
        """Завершает сессию, рассчитывает и начисляет награду."""
        logger.info(f"Processing end of mining session for user {user_id}")
        session_key = self.keys.active_session(user_id)
        
        lock_key = f"lock:{session_key}"
        async with RedisLock(self.redis, lock_key, timeout=20):
            session_data = await self.redis.hgetall(session_key)
            if not session_data:
                logger.warning(f"No active mining session found for user {user_id} to end.")
                return None

            profile_key = self.keys.user_game_profile(user_id)
            profile = await self._get_user_game_profile(user_id)
            
            tariff_details = self.settings.game.electricity_tariffs.get(profile['current_tariff'])
            power_watts = int(session_data.get("asic_power", 0))
            profitability_per_day = float(session_data.get("asic_profitability_per_day", 0))
            start_time = int(session_data.get("start_time", int(time.time())))
            
            actual_duration = min(int(time.time()) - start_time, self.settings.game.mining_duration_seconds)
            gross_earned = (profitability_per_day / 86400) * actual_duration
            power_kwh = (power_watts / 1000) * (actual_duration / 3600)
            total_electricity_cost = power_kwh * tariff_details.cost_per_hour
            net_earned = max(0, gross_earned - total_electricity_cost)

            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.delete(session_key)
                pipe.hincrbyfloat(profile_key, "balance", net_earned)
                pipe.hincrbyfloat(profile_key, "total_earned", net_earned)
                pipe.hincrby(self.keys.global_stats(), "active_sessions", -1)
                pipe.hincrbyfloat(self.keys.global_stats(), "total_balance", net_earned)
                await pipe.execute()
        
        logger.info(f"User {user_id} session ended. Net profit: {net_earned:.4f}.")
        return MiningSessionResult(
            asic_name=session_data.get('asic_name', 'Неизвестный ASIC'),
            user_tariff_name=profile['current_tariff'],
            gross_earned=gross_earned, total_electricity_cost=total_electricity_cost, net_earned=net_earned
        )

    async def get_farm_and_stats_info(self, user_id: int) -> Tuple[str, str]:
        """Возвращает информацию о ферме и статистике пользователя."""
        session_data = await self.redis.hgetall(self.keys.active_session(user_id))
        
        if session_data:
            end_time = datetime.fromisoformat(session_data['end_time_iso'])
            remaining_seconds = max(0, (end_time - datetime.now(timezone.utc)).total_seconds())
            farm_info = (f"🏠 <b>Ваша ферма</b>\n\n"
                         f"<b>Оборудование:</b> {session_data['asic_name']}\n"
                         f"<b>Статус:</b> В работе ✅\n"
                         f"<b>Завершение через:</b> {remaining_seconds / 3600:.1f} ч.")
        else:
            farm_info = "🏠 <b>Ваша ферма пуста</b>\n\nВы можете запустить новую сессию в магазине."

        profile = await self._get_user_game_profile(user_id)
        stats_info = (f"📊 <b>Ваша статистика</b>\n\n"
                      f"<b>Баланс:</b> {float(profile['balance']):,.2f} монет 💰\n"
                      f"<b>Всего заработано:</b> {float(profile['total_earned']):,.2f} монет\n"
                      f"<b>Текущий тариф:</b> {profile['current_tariff']}")
        
        return farm_info, stats_info

    async def process_withdrawal(self, user_id: int, user_profile: UserProfile) -> Tuple[str, bool]:
        """Обрабатывает заявку на вывод средств."""
        profile_key = self.keys.user_game_profile(user_id)
        profile = await self._get_user_game_profile(user_id)
        balance = float(profile.get('balance', 0.0))
        
        min_withdrawal_amount = self.settings.game.min_withdrawal_amount
        if balance < min_withdrawal_amount:
            return f"❌ Минимальная сумма для вывода: <b>{min_withdrawal_amount}</b> монет. У вас на балансе {balance:,.2f}.", False

        # Атомарно списываем баланс и создаем заявку
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.hincrbyfloat(profile_key, "balance", -balance)
            pipe.hincrby(self.keys.global_stats(), "pending_withdrawals", 1)
            await pipe.execute()

        # Отправляем уведомление администратору
        admin_message = (
            f"⚠️ <b>Новая заявка на вывод!</b>\n\n"
            f"Пользователь: <a href='tg://user?id={user_id}'>{user_profile.full_name}</a> (@{user_profile.username})\n"
            f"ID: <code>{user_id}</code>\n"
            f"Сумма: <b>{balance:,.2f} монет</b>"
        )
        await self.admin.notify_admins(admin_message)

        logger.info(f"User {user_id} created a withdrawal request for {balance} coins.")
        return "✅ Ваша заявка на вывод принята! Администратор скоро свяжется с вами для уточнения деталей.", True

    async def get_electricity_menu(self, user_id: int) -> Tuple[str, 'InlineKeyboardMarkup']:
        profile = await self._get_user_game_profile(user_id)
        current_tariff = profile['current_tariff']
        owned_tariffs = profile.get('owned_tariffs', current_tariff).split(',')
        text = (f"💡 <b>Управление электроэнергией</b>\n\n"
                f"Ваш текущий тариф: <b>{current_tariff}</b>")
        keyboard = get_electricity_menu_keyboard(self.settings.game.electricity_tariffs, owned_tariffs, current_tariff)
        return text, keyboard

    async def select_tariff(self, user_id: int, tariff_name: str) -> str:
        """Устанавливает выбранный тариф как активный."""
        profile = await self._get_user_game_profile(user_id)
        owned_tariffs = profile.get('owned_tariffs', '').split(',')
        if tariff_name in owned_tariffs:
            await self.redis.hset(self.keys.user_game_profile(user_id), "current_tariff", tariff_name)
            logger.info(f"User {user_id} switched tariff to {tariff_name}")
            return f"✅ Тариф '{tariff_name}' успешно выбран!"
        return "❌ У вас нет доступа к этому тарифу."

    async def buy_tariff(self, user_id: int, tariff_name: str) -> str:
        """Покупает новый тариф, если достаточно средств."""
        profile_key = self.keys.user_game_profile(user_id)
        profile = await self._get_user_game_profile(user_id)
        balance = float(profile.get('balance', 0.0))
        owned_tariffs = profile.get('owned_tariffs', '').split(',')
        if tariff_name in owned_tariffs:
            return "✅ У вас уже есть этот тариф."
            
        tariff_info = self.settings.game.electricity_tariffs.get(tariff_name)
        if not tariff_info: return "❌ Тариф не найден."

        price = tariff_info.unlock_price
        if balance < price:
            return f"❌ Недостаточно средств. Нужно {price} монет, у вас {balance:,.2f}."
            
        new_owned_tariffs = ",".join(owned_tariffs + [tariff_name])
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.hincrbyfloat(profile_key, "balance", -price)
            pipe.hset(profile_key, "owned_tariffs", new_owned_tariffs)
            await pipe.execute()
            
        logger.info(f"User {user_id} bought tariff {tariff_name} for {price}")
        return f"🎉 Поздравляем! Вы приобрели тариф '{tariff_name}'."


async def scheduled_end_session(user_id: int):
    """
    Автономная функция для вызова из APScheduler.
    Она заново инициализирует зависимости для выполнения задачи.
    """
    from bot.utils.dependencies import deps
    if not deps.bot:
        await deps.initialize()
    
    result = await deps.mining_game_service.end_session(user_id)
    
    if result:
        text = (f"✅ Сессия майнинга на <b>{result.asic_name}</b> завершена!\n\n"
                f"📊 <b>Результаты:</b>\n"
                f"Доход: {result.gross_earned:.2f} монет\n"
                f"Затраты на э/э: {result.total_electricity_cost:.2f} монет\n"
                f"<b>Чистая прибыль: {result.net_earned:.2f} монет</b>")
        try:
            await deps.bot.send_message(user_id, text)
        except Exception as e:
            logger.error(f"Failed to send session end notification to user {user_id}: {e}")