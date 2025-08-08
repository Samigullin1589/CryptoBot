# =================================================================================
# Файл: bot/services/mining_game_service.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ ПОЛНАЯ)
# Описание: Главный сервис-оркестратор для игровой механики майнинга.
# ИСПРАВЛЕНИЕ: Реализован паттерн асинхронной инициализации,
# убрана заглушка для таблицы лидеров, исправлены ошибки декодирования.
# =================================================================================

import time
import json
import logging
from typing import Optional, Tuple, Dict, List
from datetime import datetime, timedelta, timezone

import redis.asyncio as redis
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup

from bot.config.settings import Settings
from bot.services.user_service import UserService
from bot.services.market_service import AsicMarketService
from bot.services.event_service import MiningEventService
from bot.services.achievement_service import AchievementService
from bot.utils.models import MiningSessionResult, AsicMiner, UserProfile
from bot.keyboards.game_keyboards import get_game_main_menu_keyboard, get_electricity_menu_keyboard
from bot.utils.lua_scripts import LuaScripts
from bot.utils.keys import KeyFactory

logger = logging.getLogger(__name__)

class MiningGameService:
    def __init__(self,
                 redis: redis.Redis,
                 scheduler: AsyncIOScheduler,
                 settings: Settings,
                 user_service: UserService,
                 market_service: AsicMarketService,
                 event_service: MiningEventService,
                 achievement_service: AchievementService,
                 bot: Bot):
        self.redis = redis
        self.scheduler = scheduler
        self.settings = settings
        self.user_service = user_service
        self.market = market_service
        self.events = event_service
        self.achievements = achievement_service
        self.bot = bot
        self.keys = KeyFactory
        self.lua_start_session = None
        self.lua_end_session = None

    async def setup(self):
        """Асинхронно загружает LUA-скрипты после создания объекта."""
        self.lua_start_session = await self.redis.script_load(LuaScripts.START_MINING_SESSION)
        self.lua_end_session = await self.redis.script_load(LuaScripts.END_MINING_SESSION)
        logger.info("LUA-скрипты для MiningGameService успешно загружены.")

    async def get_user_game_profile(self, user_id: int) -> Dict[str, any]:
        profile_key = self.keys.user_game_profile(user_id)
        if await self.redis.hsetnx(profile_key, "balance", "0.0"):
            default_tariff = self.settings.game.default_electricity_tariff
            await self.redis.hmset(profile_key, {
                "total_earned": "0.0",
                "current_tariff": default_tariff,
                "owned_tariffs": default_tariff,
            })
        profile_data = await self.redis.hgetall(profile_key)
        
        balance = float(profile_data.get("balance", 0.0))
        await self.redis.zadd(self.keys.game_leaderboard(), {str(user_id): balance})

        return {
            "balance": balance,
            "total_earned": float(profile_data.get("total_earned", 0.0)),
            "current_tariff": profile_data.get("current_tariff"),
            "owned_tariffs": profile_data.get("owned_tariffs", "").split(',')
        }

    async def get_user_asics(self, user_id: int) -> List[AsicMiner]:
        hangar_key = self.keys.user_hangar(user_id)
        asics_json = await self.redis.hvals(hangar_key)
        return [AsicMiner.model_validate_json(asic_str) for asic_str in asics_json]

    async def start_session(self, user_id: int, asic_id: str) -> str:
        if await self.redis.exists(self.keys.active_session(user_id)):
            return "❌ У вас уже есть активная сессия майнинга!"
        
        hangar_key = self.keys.user_hangar(user_id)
        asic_data_json = await self.redis.hget(hangar_key, asic_id)
        if not asic_data_json:
            return "❌ У вас нет такого оборудования в ангаре."
            
        asic = AsicMiner.model_validate_json(asic_data_json)
        profile = await self.get_user_game_profile(user_id)
        current_tariff_cost = self.settings.game.electricity_tariffs[profile['current_tariff']].cost_per_kwh
        session_duration = self.settings.game.session_duration_minutes * 60
        end_time = datetime.now(timezone.utc) + timedelta(seconds=session_duration)
        
        keys = [self.keys.active_session(user_id), hangar_key, self.keys.global_stats()]
        args = [asic_id, asic.name, asic.power or 0, asic.profitability or 0, int(time.time()), end_time.isoformat(), profile['current_tariff'], current_tariff_cost]
        
        if await self.redis.evalsha(self.lua_start_session, len(keys), *keys, *args) == 0:
            return "❌ Не удалось запустить сессию. Возможно, асик уже используется."
        
        from bot.jobs.game_tasks import scheduled_end_session
        self.scheduler.add_job(scheduled_end_session, trigger='date', run_date=end_time, args=[user_id, self], id=f"end_session_for_{user_id}", replace_existing=True)
        
        logger.info(f"User {user_id} started session with ASIC ID {asic_id}. Ends at {end_time}.")
        return (f"✅ Сессия майнинга на <b>{asic.name}</b> запущена!\n\n"
                f"Она автоматически завершится через <b>{session_duration / 3600:.0f} часов</b>.")

    async def end_session(self, user_id: int) -> Optional[MiningSessionResult]:
        logger.info(f"Ending mining session for user {user_id}")
        event = self.events.get_random_event()
        
        keys = [self.keys.active_session(user_id), self.keys.user_game_profile(user_id), self.keys.user_hangar(user_id), self.keys.global_stats()]
        args = [
            int(time.time()), self.settings.game.session_duration_minutes * 60,
            event.profit_multiplier if event else 1.0, event.cost_multiplier if event else 1.0
        ]
        
        result_json = await self.redis.evalsha(self.lua_end_session, len(keys), *keys, *args)
        if not result_json:
            logger.warning(f"No active session found for user {user_id} during scheduled end.")
            return None
            
        result_data = json.loads(result_json)
        result = MiningSessionResult(**result_data['result'])
        if event:
            result.event_description = event.description
        
        unlocked_ach = await self.achievements.process_static_event(user_id, "session_completed")
        if unlocked_ach:
            result.unlocked_achievement = unlocked_ach
        
        logger.info(f"User {user_id} session ended. Net profit: {result.net_earned:.4f}.")
        return result

    async def get_farm_and_stats_info(self, user_id: int) -> Tuple[str, str]:
        session_data = await self.redis.hgetall(self.keys.active_session(user_id))

        if session_data:
            end_time = datetime.fromisoformat(session_data['end_time_iso'])
            remaining_seconds = max(0, (end_time - datetime.now(end_time.tzinfo)).total_seconds())
            farm_info = (f"🏠 <b>Ваша ферма (в работе)</b>\n"
                         f"<b>Оборудование:</b> {session_data['asic_name']}\n"
                         f"<b>Завершение через:</b> {remaining_seconds / 3600:.1f} ч.")
        else:
            farm_info = "🏠 <b>Ваша ферма пуста</b>\n\nОборудование простаивает в ангаре."

        user_asics = await self.get_user_asics(user_id)
        if user_asics:
            farm_info += "\n\n🛠 <b>Ваш ангар (доступно):</b>\n" + "\n".join([f"• {asic.name}" for asic in user_asics])
        else:
            farm_info += "\n\n🛠 <b>Ваш ангар пуст.</b>"

        profile = await self.get_user_game_profile(user_id)
        stats_info = (f"📊 <b>Ваша статистика</b>\n\n"
                      f"<b>Баланс:</b> {profile['balance']:,.2f} монет 💰\n"
                      f"<b>Всего заработано:</b> {profile['total_earned']:,.2f} монет\n"
                      f"<b>Текущий тариф:</b> {profile['current_tariff']}")
        return farm_info, stats_info

    async def process_withdrawal(self, user_id: int, user_profile: UserProfile) -> Tuple[str, bool]:
        profile_key = self.keys.user_game_profile(user_id)
        profile = await self.get_user_game_profile(user_id)
        balance = profile['balance']
        min_withdrawal_amount = self.settings.game.min_withdrawal_amount
        if balance < min_withdrawal_amount:
            return f"❌ Минимальная сумма для вывода: <b>{min_withdrawal_amount}</b> монет. У вас на балансе {balance:,.2f}.", False
        
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.hincrbyfloat(profile_key, "balance", -balance)
            pipe.hincrby(self.keys.global_stats(), "pending_withdrawals", 1)
            await pipe.execute()
        
        await self.bot.send_message(
            self.settings.ADMIN_CHAT_ID,
            f"⚠️ <b>Новая заявка на вывод!</b>\n\n"
            f"Пользователь: <a href='tg://user?id={user_id}'>{user_profile.full_name}</a> (@{user_profile.username})\n"
            f"ID: <code>{user_id}</code>\n"
            f"Сумма: <b>{balance:,.2f} монет</b>"
        )
        logger.info(f"User {user_id} created a withdrawal request for {balance} coins.")
        return "✅ Ваша заявка на вывод принята! Администратор скоро свяжется с вами для уточнения деталей.", True

    async def get_electricity_menu(self, user_id: int) -> Tuple[str, InlineKeyboardMarkup]:
        profile = await self.get_user_game_profile(user_id)
        current_tariff_name = profile['current_tariff']
        owned_tariffs = profile['owned_tariffs']
        all_tariffs = self.settings.game.electricity_tariffs
        text = f"💡 <b>Управление электроэнергией</b>\n\nВаш текущий тариф: <b>{current_tariff_name}</b>"
        keyboard = get_electricity_menu_keyboard(all_tariffs, owned_tariffs, current_tariff_name)
        return text, keyboard

    async def select_tariff(self, user_id: int, tariff_name: str) -> str:
        profile = await self.get_user_game_profile(user_id)
        if tariff_name in profile['owned_tariffs']:
            await self.redis.hset(self.keys.user_game_profile(user_id), "current_tariff", tariff_name)
            logger.info(f"User {user_id} switched tariff to {tariff_name}")
            return f"✅ Тариф '{tariff_name}' успешно выбран!"
        return "❌ У вас нет доступа к этому тарифу."

    async def buy_tariff(self, user_id: int, tariff_name: str) -> str:
        profile_key = self.keys.user_game_profile(user_id)
        profile = await self.get_user_game_profile(user_id)
        if tariff_name in profile['owned_tariffs']:
            return "✅ У вас уже есть этот тариф."
        
        tariff_info = self.settings.game.electricity_tariffs.get(tariff_name)
        if not tariff_info: return "❌ Тариф не найден."
        
        price = tariff_info.unlock_price
        if profile['balance'] < price:
            return f"❌ Недостаточно средств. Нужно {price:,.2f} монет, у вас {profile['balance']:,.2f}."
        
        new_owned_list = profile['owned_tariffs'] + [tariff_name]
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.hincrbyfloat(profile_key, "balance", -price)
            pipe.hset(profile_key, "owned_tariffs", ",".join(new_owned_list))
            await pipe.execute()
        
        unlocked_ach = await self.achievements.process_static_event(
            user_id, "tariff_bought", {"tariff_name": tariff_name}
        )
        if unlocked_ach:
            try:
                await self.bot.send_message(
                    user_id,
                    f"🏆 <b>Новое достижение!</b>\n\n"
                    f"<b>{unlocked_ach.name}</b>: {unlocked_ach.description}\n"
                    f"<i>Награда: +{unlocked_ach.reward_coins} монет.</i>"
                )
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление о достижении пользователю {user_id}: {e}")
        
        logger.info(f"User {user_id} bought tariff {tariff_name}")
        return f"🎉 Поздравляем! Вы приобрели тариф '{tariff_name}'."

    async def get_current_electricity_price(self, tariff_name: str) -> float:
        price = await self.redis.hget(self.keys.electricity_market(), tariff_name)
        return float(price) if price else self.settings.game.electricity_tariffs[tariff_name].cost_per_kwh
        
    async def get_leaderboard(self, top_n: int = 10) -> Dict[int, float]:
        """Возвращает топ-N игроков по балансу из Redis Sorted Set."""
        leaderboard_raw = await self.redis.zrevrange(self.keys.game_leaderboard(), 0, top_n - 1, withscores=True)
        return {int(user_id): score for user_id, score in leaderboard_raw}
