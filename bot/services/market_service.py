# =================================================================================
# Файл: bot/services/market_service.py (ВЕРСИЯ "ГЕНИЙ 2.0" - АБСОЛЮТНО ПОЛНАЯ)
# Описание: Полностью самодостаточный сервис для управления рынком
# оборудования (ASIC), обеспечивающий атомарность операций и систему достижений.
# =================================================================================

import json
import uuid
import time
import logging
from typing import List, Optional

import redis.asyncio as redis
from aiogram import Bot

from bot.config.settings import AppSettings
from bot.utils.models import AsicMiner, MarketListing
from bot.utils.lua_scripts import LuaScripts
from bot.services.achievement_service import AchievementService

logger = logging.getLogger(__name__)

class _KeyFactory:
    """Генератор ключей Redis, специфичных для рынка."""
    @staticmethod
    def user_hangar(user_id: int) -> str: return f"game:hangar:{user_id}"
    @staticmethod
    def user_game_profile(user_id: int) -> str: return f"game:profile:{user_id}"
    @staticmethod
    def market_listings_by_price() -> str: return "market:listings:price"
    @staticmethod
    def market_listing_data(listing_id: str) -> str: return f"market:listing:{listing_id}"

class AsicMarketService:
    """Сервис, управляющий всеми операциями на рынке ASIC'ов."""

    def __init__(self,
                 redis_client: redis.Redis,
                 settings: AppSettings,
                 achievement_service: AchievementService,
                 bot: Bot):
        self.redis = redis_client
        self.settings = settings
        self.achievements = achievement_service
        self.bot = bot
        self.keys = _KeyFactory
        self.lua_list_item = self.redis.script_load(LuaScripts.LIST_ITEM_FOR_SALE)
        self.lua_cancel_listing = self.redis.script_load(LuaScripts.CANCEL_LISTING)
        self.lua_buy_item = self.redis.script_load(LuaScripts.BUY_ITEM_FROM_MARKET)

    async def list_asic_for_sale(self, user_id: int, asic_id: str, price: float) -> Optional[str]:
        """Выставляет ASIC из ангара пользователя на продажу. Операция атомарна."""
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
        """Снимает лот с продажи и возвращает ASIC в ангар владельца. Атомарно."""
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
        """Покупает ASIC с рынка и проверяет достижение для продавца."""
        commission_rate = self.settings.game.market_commission_rate
        
        seller_id_bytes = await self.redis.hget(self.keys.market_listing_data(listing_id), "seller_id")
        seller_id = int(seller_id_bytes) if seller_id_bytes else None

        keys = [
            self.keys.market_listing_data(listing_id),
            self.keys.market_listings_by_price(),
            self.keys.user_game_profile(buyer_id),
        ]
        args = [listing_id, buyer_id, commission_rate]
        
        result_code = await self.redis.evalsha(self.lua_buy_item, len(keys), *args)

        if result_code == 1:
            logger.info(f"User {buyer_id} successfully bought listing {listing_id}.")
            if seller_id:
                unlocked_ach = await self.achievements.process_event(seller_id, "ASIC_SOLD")
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
        """Получает список лотов с рынка, отсортированных по цене."""
        listing_ids = await self.redis.zrange(self.keys.market_listings_by_price(), offset, offset + count - 1)
        if not listing_ids:
            return []

        pipe = self.redis.pipeline()
        for listing_id in listing_ids:
            pipe.hgetall(self.keys.market_listing_data(listing_id.decode('utf-8')))
        
        listings_data = await pipe.execute()
        
        market_listings = []
        for data in listings_data:
            if data:
                # Преобразуем bytes в str для Pydantic
                str_data = {k.decode('utf-8'): v.decode('utf-8') for k, v in data.items()}
                market_listings.append(MarketListing(**str_data))
        
        return market_listings