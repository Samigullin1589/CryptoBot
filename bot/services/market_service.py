# =================================================================================
# Файл: bot/services/market_service.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ)
# Описание: Сервис, управляющий рынком ASIC-майнеров.
# ИСПРАВЛЕНИЕ: Реализован паттерн асинхронной инициализации для
# корректной и "чистой" загрузки LUA-скриптов.
# =================================================================================

import json
import uuid
import time
import logging
from typing import List, Optional

import redis.asyncio as redis
from aiogram import Bot

from bot.config.settings import Settings
from bot.utils.models import AsicMiner, MarketListing
from bot.utils.lua_scripts import LuaScripts
from bot.services.achievement_service import AchievementService
from bot.utils.keys import KeyFactory

logger = logging.getLogger(__name__)

class AsicMarketService:
    def __init__(self,
                 redis: redis.Redis,
                 settings: Settings,
                 achievement_service: AchievementService,
                 bot: Bot):
        self.redis = redis
        self.settings = settings
        self.achievements = achievement_service
        self.bot = bot
        self.keys = KeyFactory
        self.lua_list_item = None
        self.lua_cancel_listing = None
        self.lua_buy_item = None

    async def setup(self):
        """Асинхронно загружает LUA-скрипты после создания объекта."""
        self.lua_list_item = await self.redis.script_load(LuaScripts.LIST_ITEM_FOR_SALE)
        self.lua_cancel_listing = await self.redis.script_load(LuaScripts.CANCEL_LISTING)
        self.lua_buy_item = await self.redis.script_load(LuaScripts.BUY_ITEM_FROM_MARKET)
        logger.info("LUA-скрипты для AsicMarketService успешно загружены.")

    async def list_asic_for_sale(self, user_id: int, asic_id: str, price: float) -> Optional[str]:
        if price <= 0:
            return None

        hangar_key = self.keys.user_hangar(user_id)
        listing_id = str(uuid.uuid4())
        
        keys = [hangar_key, self.keys.market_listing_data(listing_id), self.keys.market_listings_by_price()]
        args = [asic_id, listing_id, user_id, price, int(time.time())]
        
        result = await self.redis.evalsha(self.lua_list_item, len(keys), *keys, *args)
        
        if result == 1:
            logger.info(f"User {user_id} listed ASIC {asic_id} for {price} (listing ID: {listing_id})")
            return listing_id
        else:
            logger.error(f"Failed to list ASIC {asic_id} for user {user_id}. Item not found in hangar.")
            return None

    async def cancel_listing(self, user_id: int, listing_id: str) -> bool:
        keys = [self.keys.market_listing_data(listing_id), self.keys.market_listings_by_price(), self.keys.user_hangar(user_id)]
        args = [listing_id, user_id]
        
        result = await self.redis.evalsha(self.lua_cancel_listing, len(keys), *keys, *args)
        
        if result == 1:
            logger.info(f"User {user_id} cancelled listing {listing_id}.")
            return True
        else:
            logger.warning(f"Failed to cancel listing {listing_id} for user {user_id}. Not owner or listing not found.")
            return False

    async def buy_asic(self, buyer_id: int, listing_id: str) -> str:
        commission_rate = self.settings.game.market_commission_rate
        
        seller_id_str = await self.redis.hget(self.keys.market_listing_data(listing_id), "seller_id")
        seller_id = int(seller_id_str) if seller_id_str else None

        keys = [
            self.keys.market_listing_data(listing_id),
            self.keys.market_listings_by_price(),
            self.keys.user_game_profile(buyer_id),
            self.keys.user_hangar(buyer_id),
            self.keys.user_game_profile(seller_id) if seller_id else "nil"
        ]
        args = [listing_id, buyer_id, seller_id or 0, commission_rate]
        
        result_code = await self.redis.evalsha(self.lua_buy_item, len(keys), *keys, *args)

        if result_code == 1:
            logger.info(f"User {buyer_id} successfully bought listing {listing_id}.")
            if seller_id:
                unlocked_ach = await self.achievements.process_static_event(seller_id, "asic_sold")
                if unlocked_ach:
                    try:
                        await self.bot.send_message(
                            seller_id,
                            f"🏆 <b>Новое достижение!</b>\n\n"
                            f"<b>{unlocked_ach.name}</b>: {unlocked_ach.description}\n"
                            f"<i>Награда: +{unlocked_ach.reward_coins} монет.</i>"
                        )
                    except Exception as e:
                        logger.error(f"Не удалось отправить уведомление о достижении продавцу {seller_id}: {e}")
            return "✅ Поздравляем с приобретением! Оборудование уже в вашем ангаре."
        elif result_code == -1:
            return "❌ Вы не можете купить собственное оборудование."
        elif result_code == -2:
            return "❌ Недостаточно средств для покупки."
        elif result_code == -3:
            return "❌ Этот лот больше не доступен. Возможно, его уже купили или сняли с продажи."
        else:
            return "❌ Произошла неизвестная ошибка при покупке."
            
    async def get_market_listings(self, offset: int = 0, count: int = 20) -> List[MarketListing]:
        listing_ids = await self.redis.zrange(self.keys.market_listings_by_price(), offset, offset + count - 1)
        if not listing_ids:
            return []

        pipe = self.redis.pipeline()
        for listing_id in listing_ids:
            pipe.hgetall(self.keys.market_listing_data(listing_id))
        
        listings_data = await pipe.execute()
        
        market_listings = []
        for data in listings_data:
            if data:
                market_listings.append(MarketListing(**data))
        
        return market_listings
