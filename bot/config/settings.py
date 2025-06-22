from typing import List, Dict
from pydantic_settings import BaseSettings, SettingsConfigDict

class AppSettings(BaseSettings):
    bot_token: str
    redis_url: str 
    openai_api_key: str = ""
    admin_chat_id: int
    news_chat_id: int
    cmc_api_key: str = ""

    coingecko_api_base: str = "https://api.coingecko.com/api/v3"
    coinpaprika_api_base: str = "https://api.coinpaprika.com/v1"
    minerstat_api_base: str = "https://api.minerstat.com/v2"
    whattomine_asics_url: str = "https://whattomine.com/asics.json"
    asicminervalue_url: str = "https://www.asicminervalue.com/"
    fear_and_greed_api_url: str = "https://api.alternative.me/fng/?limit=1"
    cmc_fear_and_greed_url: str = "https://pro-api.coinmarketcap.com/v3/fear-and-greed/historical"
    cbr_daily_json_url: str = "https://www.cbr-xml-daily.ru/daily_json.js"

    # Путь к нашему новому файлу с резервными данными
    fallback_asics_path: str = "bot/data/fallback_asics.json"

    news_rss_feeds: List[str] = [
        "https://forklog.com/feed",
        "https://beincrypto.ru/feed/",
        "https://cointelegraph.com/rss/tag/russia"
    ]
    news_interval_hours: int = 3
    asic_cache_update_hours: int = 1

    ticker_aliases: Dict[str, str] = {'бтк': 'BTC', 'биткоин': 'BTC', 'биток': 'BTC', 'eth': 'ETH', 'эфир': 'ETH', 'эфириум': 'ETH'}

    popular_tickers: List[str] = ['BTC', 'ETH', 'SOL', 'TON', 'KAS']

    MINING_DURATION_SECONDS: int = 8 * 3600
    MINING_RATE_PER_HOUR: float = 10.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

settings = AppSettings()