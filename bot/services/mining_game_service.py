# =================================================================================
# Файл: bot/services/mining_game_service.py (ФИНАЛЬНАЯ ИНТЕГРИРОВАННАЯ ВЕРСИЯ, АВГУСТ 2025)
# Описание: Главный сервис-оркестратор для игровой механики.
# ИСПРАВЛЕНИЕ: Устранена циклическая зависимость с помощью TYPE_CHECKING.
# =================================================================================

import time
import json
import logging
from typing import Optional, Tuple, Dict, List, TYPE_CHECKING
from datetime import datetime, timedelta, timezone

import redis.asyncio as redis
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup

from bot.config.settings import Settings
from bot.services.user_service import UserService
from bot.services.event_service import MiningEventService
from bot.services.achievement_service import AchievementService
from bot.utils.models import MiningSessionResult, AsicMiner, User, UserGameProfile
from bot.keyboards.game_keyboards import get_game_main_menu_keyboard, get_electricity_menu_keyboard
from bot.utils.lua_scripts import LuaScripts
from bot.utils.keys import KeyFactory

if TYPE_CHECKING:
    from bot.services.market_service import AsicMarketService

logger = logging.getLogger(__name__)

class MiningGameService:
    def __init__(self,
                 redis: redis.Redis,
                 scheduler: AsyncIOScheduler,
                 settings: Settings,
                 user_service: UserService,
                 market_service: "AsicMarketService",
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

    async def get_user_game_profile(self, user_id: int) -> UserGameProfile:
        """Получает игровой профиль пользователя, создавая его при необходимости."""
        profile_key = self.keys.user_game_profile(user_id)
        profile_data = await self.redis.hgetall(profile_key)

        if not profile_data:
            default_tariff = self.settings.game.default_electricity_tariff
            initial_data = {
                "balance": "0.0",
                "total_earned": "0.0",
                "current_tariff": default_tariff,
                "owned_tariffs": default_tariff,
            }
            await self.redis.hmset(profile_key, initial_data)
            profile_data.update(initial_data)
        
        current_tariff = profile_data.get("current_tariff")
        if not current_tariff:
            current_tariff = self.settings.game.default_electricity_tariff
            await self.redis.hset(profile_key, "current_tariff", current_tariff)

        game_profile = UserGameProfile(
            balance=float(profile_data.get("balance", 0.0)),
            total_earned=float(profile_data.get("total_earned", 0.0)),
            current_tariff=current_tariff,
            owned_tariffs=profile_data.get("owned_tariffs", "").split(',')
        )
        
        await self.redis.zadd(self.keys.game_leaderboard(), {str(user_id): game_profile.balance})
        return game_profile

    async def get_user_asics(self, user_id: int) -> List[AsicMiner]:
        """Получает список ASIC'ов в ангаре пользователя."""
        hangar_key = self.keys.user_hangar(user_id)
        asics_json = await self.redis.hvals(hangar_key)
        return [AsicMiner.model_validate_json(asic_str) for asic_str in asics_json]

    async def start_session(self, user_id: int, asic_id: str) -> str:
        """Запускает майнинг-сессию для указанного ASIC из ангара."""
        if await self.redis.exists(self.keys.active_session(user_id)):
            return "❌ У вас уже есть активная сессия майнинга!"
        
        hangar_key = self.keys.user_hangar(user_id)
        asic_data_json = await self.redis.hget(hangar_key, asic_id)
        if not asic_data_json:
            return "❌ У вас нет такого оборудования в ангаре."
            
        asic = AsicMiner.model_validate_json(asic_data_json)
        profile = await self.get_user_game_profile(user_id)
        current_tariff_cost = self.settings.game.electricity_tariffs[profile.current_tariff].cost_per_kwh
        session_duration = self.settings.game.session_duration_minutes * 60
        end_time = datetime.now(timezone.utc) + timedelta(seconds=session_duration)
        
        keys = [self.keys.active_session(user_id), hangar_key, self.keys.game_stats()]
        args = [asic_id, asic.name, asic.power or 0, asic.profitability or 0, int(time.time()), end_time.isoformat(), profile.current_tariff, current_tariff_cost]
        
        if await self.redis.evalsha(self.lua_start_session, len(keys), *keys, *args) == 0:
            return "❌ Не удалось запустить сессию. Возможно, асик уже используется."
        
        from bot.jobs.game_tasks import scheduled_end_session
        self.scheduler.add_job(scheduled_end_session, trigger='date', run_date=end_time, args=[user_id, self], id=f"end_session_for_{user_id}", replace_existing=True)
        
        logger.info(f"User {user_id} started session with ASIC ID {asic_id}. Ends at {end_time}.")
        return (f"✅ Сессия майнинга на <b>{asic.name}</b> запущена!\n\n"
                f"Она автоматически завершится через <b>{self.settings.game.session_duration_minutes / 60:.0f} часов</b>.")

    # ИСПРАВЛЕНО: Добавлен недостающий метод
    async def start_session_with_new_asic(self, user_id: int, asic: AsicMiner) -> str:
        """
        Добавляет новый ASIC в ангар пользователя и сразу запускает сессию.
        Используется при "покупке" в магазине.
        """
        # В текущей логике цена ASIC не учитывается, он просто добавляется.
        hangar_key = self.keys.user_hangar(user_id)
        await self.redis.hset(hangar_key, asic.id, asic.model_dump_json())
        logger.info(f"User {user_id} acquired new ASIC '{asic.name}' from shop.")
        
        # После добавления в ангар, вызываем стандартный метод запуска сессии.
        return await self.start_session(user_id, asic.id)

    async def end_session(self, user_id: int) -> Optional[MiningSessionResult]:
        """Завершает майнинг-сессию, вызывается планировщиком."""
        logger.info(f"Ending mining session for user {user_id}")
        event = self.events.get_random_event()
        
        keys = [self.keys.active_session(user_id), self.keys.user_game_profile(user_id), self.keys.user_hangar(user_id), self.keys.game_stats()]
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
        """Возвращает текстовое описание фермы и статистики игрока."""
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
                      f"<b>Баланс:</b> {profile.balance:,.2f} монет 💰\n"
                      f"<b>Всего заработано:</b> {profile.total_earned:,.2f} монет\n"
                      f"<b>Текущий тариф:</b> {profile.current_tariff}")
        return farm_info, stats_info

    async def process_withdrawal(self, user: User) -> Tuple[str, bool]:
        """Обрабатывает заявку на вывод средств."""
        profile_key = self.keys.user_game_profile(user.id)
        profile = await self.get_user_game_profile(user.id)
        balance = profile.balance
        min_withdrawal_amount = self.settings.game.min_withdrawal_amount
        if balance < min_withdrawal_amount:
            return f"❌ Минимальная сумма для вывода: <b>{min_withdrawal_amount}</b> монет. У вас на балансе {balance:,.2f}.", False
        
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.hincrbyfloat(profile_key, "balance", -balance)
            pipe.hincrby(self.keys.global_stats(), "pending_withdrawals", 1)
            await pipe.execute()
        
        if self.settings.ADMIN_CHAT_ID:
            await self.bot.send_message(
                self.settings.ADMIN_CHAT_ID,
                f"⚠️ <b>Новая заявка на вывод!</b>\n\n"
                f"Пользователь: <a href='tg://user?id={user.id}'>{user.first_name}</a> (@{user.username})\n"
                f"ID: <code>{user.id}</code>\n"
                f"Сумма: <b>{balance:,.2f} монет</b>"
            )
        logger.info(f"User {user.id} created a withdrawal request for {balance} coins.")
        return "✅ Ваша заявка на вывод принята! Администратор скоро свяжется с вами для уточнения деталей.", True

    async def get_electricity_menu(self, user_id: int) -> Tuple[str, InlineKeyboardMarkup]:
        """Возвращает текст и клавиатуру для меню управления тарифами."""
        profile = await self.get_user_game_profile(user_id)
        text = f"💡 <b>Управление электроэнергией</b>\n\nВаш текущий тариф: <b>{profile.current_tariff}</b>"
        keyboard = get_electricity_menu_keyboard(self.settings.game.electricity_tariffs, profile.owned_tariffs, profile.current_tariff)
        return text, keyboard

    async def select_tariff(self, user_id: int, tariff_name: str) -> str:
        """Выбирает активный тариф для пользователя."""
        profile = await self.get_user_game_profile(user_id)
        if tariff_name in profile.owned_tariffs:
            await self.redis.hset(self.keys.user_game_profile(user_id), "current_tariff", tariff_name)
            logger.info(f"User {user_id} switched tariff to {tariff_name}")
            return f"✅ Тариф '{tariff_name}' успешно выбран!"
        return "❌ У вас нет доступа к этому тарифу."

    async def buy_tariff(self, user_id: int, tariff_name: str) -> str:
        """Обрабатывает покупку нового тарифа."""
        profile_key = self.keys.user_game_profile(user_id)
        profile = await self.get_user_game_profile(user_id)
        if tariff_name in profile.owned_tariffs:
            return "✅ У вас уже есть этот тариф."
        
        tariff_info = self.settings.game.electricity_tariffs.get(tariff_name)
        if not tariff_info: return "❌ Тариф не найден."
        
        price = tariff_info.unlock_price
        if profile.balance < price:
            return f"❌ Недостаточно средств. Нужно {price:,.2f} монет, у вас {profile.balance:,.2f}."
        
        new_owned_list = profile.owned_tariffs + [tariff_name]
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

    async def get_leaderboard(self, top_n: int = 10) -> Dict[int, float]:
        """Возвращает топ-N игроков по балансу из Redis Sorted Set."""
        leaderboard_raw = await self.redis.zrevrange(self.keys.game_leaderboard(), 0, top_n - 1, withscores=True)
        return {int(user_id): score for user_id, score in leaderboard_raw}