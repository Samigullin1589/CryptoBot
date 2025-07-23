# ===============================================================
# Файл: bot/services/coin_list_service.py (ОКОНЧАТЕЛЬНЫЙ FIX)
# Описание: Восстановлен метод get_coin_list для обратной
# совместимости, чтобы исправить AttributeError в PriceService.
# ===============================================================
import logging
from typing import Dict, Optional, List
import aiohttp
from async_lru import alru_cache

from bot.config.settings import settings
from bot.utils.helpers import make_request

logger = logging.getLogger(__name__)

class CoinListService:
    def __init__(self, http_session: aiohttp.ClientSession):
        self.session = http_session
        self._coin_data = {}

    # --- НОВЫЙ МЕТОД, ВОССТАНОВЛЕННЫЙ ДЛЯ СОВМЕСТИМОСТИ ---
    @alru_cache(maxsize=1, ttl=3600)
    async def get_coin_list(self) -> Dict[str, str]:
        """
        Возвращает список монет в формате {СИМВОЛ: АЛГОРИТМ} для обратной совместимости
        с другими сервисами, такими как PriceService.
        """
        logger.info("Providing coin list for backward compatibility...")
        full_data = await self.get_full_coin_data()
        if not full_data:
            return {}
        
        # Преобразуем новый формат данных (список словарей) в старый (словарь)
        return {
            coin.get('coin', ''): coin.get('algorithm', 'Unknown')
            for coin in full_data if coin.get('coin')
        }
    # --- КОНЕЦ НОВОГО МЕТОДА ---

    @alru_cache(maxsize=1, ttl=3600)
    async def get_full_coin_data(self) -> List[Dict]:
        """
        Получает и кэширует полный список данных о монетах.
        """
        logger.info("Updating full coin data list...")
        
        # Источник №1: MinerStat
        minerstat_data = await make_request(self.session, f"{settings.minerstat_api_base}/coins")
        if minerstat_data and isinstance(minerstat_data, list):
            logger.info(f"Successfully fetched {len(minerstat_data)} coins from MinerStat.")
            self._coin_data = minerstat_data
            return self._coin_data

        # Резервный источник №2: CoinGecko
        logger.warning("MinerStat failed, using CoinGecko as a fallback.")
        gecko_data = await make_request(self.session, f"{settings.coingecko_api_base}/coins/list?include_platform=false")
        if gecko_data and isinstance(gecko_data, list):
            logger.info(f"Successfully fetched {len(gecko_data)} coins from CoinGecko.")
            # Адаптируем данные от Gecko под наш формат
            self._coin_data = [{'coin': c.get('symbol', '').upper(), 'name': c.get('id'), 'algorithm': 'Unknown'} for c in gecko_data]
            return self._coin_data
        
        logger.error("Failed to fetch coin list from all sources.")
        return []

    async def find_coin_by_name(self, query: str) -> Optional[str]:
        """
        Ищет монету по тикеру или названию в закэшированном списке.
        """
        query = query.strip().lower()
        if not query:
            return None

        coin_data = await self.get_full_coin_data()
        if not coin_data:
            return "Не удалось обновить базу данных монет. Попробуйте позже."

        # Поиск по точному совпадению тикера (BTC, ETH)
        for coin in coin_data:
            if coin.get('coin', '').lower() == query:
                return self._format_coin_info(coin)

        # Поиск по точному совпадению ID/имени (bitcoin, ethereum)
        for coin in coin_data:
            if coin.get('name', '').lower() == query:
                return self._format_coin_info(coin)
        
        return None

    def _format_coin_info(self, coin: Dict) -> str:
        """Форматирует информацию о монете в красивое сообщение."""
        name = coin.get('name', 'N/A')
        ticker = coin.get('coin', 'N/A')
        algorithm = coin.get('algorithm', 'N/A')
        
        return (
            f"<b>ℹ️ Информация о монете:</b>\n\n"
            f"<b>Название:</b> {name.capitalize()}\n"
            f"<b>Тикер:</b> {ticker}\n"
            f"<b>Алгоритм:</b> {algorithm}"
        )
