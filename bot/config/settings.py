from typing import List, Dict
from pydantic_settings import BaseSettings, SettingsConfigDict

class AppSettings(BaseSettings):
    """
    Класс для хранения всех настроек и констант,
    загружаемых из переменных окружения.
    """
    # --- Ключи API и токены (обязательно укажите в .env) ---
    bot_token: str
    redis_url: str
    openai_api_key: str = ""
    admin_chat_id: int
    news_chat_id: int
    cmc_api_key: str = ""

    # --- Источники данных API ---
    coingecko_api_base: str = "https://api.coingecko.com/api/v3"
    coinpaprika_api_base: str = "https://api.coinpaprika.com/v1"
    minerstat_api_base: str = "https://api.minerstat.com/v2"
    whattomine_asics_url: str = "https://whattomine.com/asics.json"
    asicminervalue_url: str = "https://www.asicminervalue.com/"
    fear_and_greed_api_url: str = "https://api.alternative.me/fng/?limit=1"
    cmc_fear_and_greed_url: str = "https://pro-api.coinmarketcap.com/v1/crypto/fear-and-greed"
    cbr_daily_json_url: str = "https://www.cbr-xml-daily.ru/daily_json.js"

    # --- Настройки планировщика и новостей ---
    news_rss_feeds: List[str] = [
        "https://forklog.com/feed", "https://bits.media/rss/", "https://www.rbc.ru/crypto/feed",
        "https://beincrypto.ru/feed/", "https://cointelegraph.com/rss/tag/russia"
    ]
    news_interval_hours: int = 3
    asic_cache_update_hours: int = 1

    # --- Алиасы и популярные тикеры ---
    ticker_aliases: Dict[str, str] = {'бтк': 'BTC', 'биткоин': 'BTC', 'биток': 'BTC', 'eth': 'ETH', 'эфир': 'ETH', 'эфириум': 'ETH'}
    popular_tickers: List[str] = ['BTC', 'ETH', 'SOL', 'TON', 'KAS']

    # --- Обновленный и расширенный резервный список ASIC на основе ваших данных ---
    fallback_asics: List[Dict] = [
        # Antminer SHA-256
        {'name': 'Antminer S19 K Pro 110 Th/s', 'profitability': 7.08, 'algorithm': 'SHA-256'},
        {'name': 'Antminer S19 K Pro 115 Th/s', 'profitability': 7.39, 'algorithm': 'SHA-256'},
        {'name': 'Antminer S19 K Pro 120 Th/s', 'profitability': 8.03, 'algorithm': 'SHA-256'},
        {'name': 'Antminer S19 K Pro 120 Th/s бу', 'profitability': 5.72, 'algorithm': 'SHA-256'},
        {'name': 'Antminer S19 XP 134 Th/s бу', 'profitability': 9.43, 'algorithm': 'SHA-256'},
        {'name': 'Antminer S19 XP 141 Th/s бу', 'profitability': 10.18, 'algorithm': 'SHA-256'},
        {'name': 'Antminer S19J XP 136 Th/s', 'profitability': 11.90, 'algorithm': 'SHA-256'},
        {'name': 'Antminer S19J XP 143 Th/s', 'profitability': 12.85, 'algorithm': 'SHA-256'},
        {'name': 'Antminer S19J XP 151 Th/s', 'profitability': 13.44, 'algorithm': 'SHA-256'},
        {'name': 'Antminer S19 XP HYDRO 257 Th/s', 'profitability': 19.83, 'algorithm': 'SHA-256'},
        {'name': 'Antminer S19e XP HYDRO 240 Th/s', 'profitability': 18.37, 'algorithm': 'SHA-256'},
        {'name': 'Antminer S19e XP HYDRO 251 Th/s', 'profitability': 19.31, 'algorithm': 'SHA-256'},
        {'name': 'Antminer T21 180 Th/s', 'profitability': 19.10, 'algorithm': 'SHA-256'},
        {'name': 'Antminer T21 186 Th/s', 'profitability': 19.83, 'algorithm': 'SHA-256'},
        {'name': 'Antminer T21 190 Th/s', 'profitability': 21.23, 'algorithm': 'SHA-256'},
        {'name': 'Antminer T21 190 Th/s бу', 'profitability': 15.21, 'algorithm': 'SHA-256'},
        {'name': 'Antminer S21 188 Th/s бу', 'profitability': 18.15, 'algorithm': 'SHA-256'},
        {'name': 'Antminer S21 200 Th/s бу', 'profitability': 19.10, 'algorithm': 'SHA-256'},
        {'name': 'Antminer S21+ 225 Th/s', 'profitability': 26.37, 'algorithm': 'SHA-256'},
        {'name': 'Antminer S21+ 235 Th/s', 'profitability': 26.82, 'algorithm': 'SHA-256'},
        {'name': 'Antminer S21 XP 270 Th/s', 'profitability': 52.52, 'algorithm': 'SHA-256'},
        {'name': 'Antminer S21 HYDRO 302 Th/s', 'profitability': 40.77, 'algorithm': 'SHA-256'},
        {'name': 'Antminer S21 HYDRO 319 Th/s', 'profitability': 42.98, 'algorithm': 'SHA-256'},
        {'name': 'Antminer S21 HYDRO 335 Th/s', 'profitability': 45.17, 'algorithm': 'SHA-256'},
        {'name': 'Antminer S21+ HYDRO 358 Th/s', 'profitability': 44.38, 'algorithm': 'SHA-256'},
        {'name': 'Antminer S21+ HYDRO 395 Th/s', 'profitability': 47.01, 'algorithm': 'SHA-256'},
        {'name': 'Antminer S21 XP HYDRO 437 Th/s', 'profitability': 94.77, 'algorithm': 'SHA-256'},
        {'name': 'Antminer S21 XP HYDRO 473 Th/s', 'profitability': 93.65, 'algorithm': 'SHA-256'},
        # Antminer Equihash
        {'name': 'Antminer Z15 pro 840 ksol бу', 'profitability': 14.00, 'algorithm': 'Equihash'},
        # Antminer Scrypt
        {'name': 'Antminer L7 8050 Mh/s бу', 'profitability': 19.03, 'algorithm': 'Scrypt'},
        {'name': 'Antminer L7 8800 Mh/s бу', 'profitability': 22.62, 'algorithm': 'Scrypt'},
        {'name': 'Antminer L7 9050 Mh/s бу', 'profitability': 21.16, 'algorithm': 'Scrypt'},
        {'name': 'Antminer L7 9300 Mh/s бу', 'profitability': 21.89, 'algorithm': 'Scrypt'},
        {'name': 'Antminer L7 9500 Mh/s бу', 'profitability': 31.81, 'algorithm': 'Scrypt'},
        {'name': 'Antminer L9 15 Gh/s', 'profitability': 63.54, 'algorithm': 'Scrypt'},
        {'name': 'Antminer L9 16 Gh/s', 'profitability': 65.16, 'algorithm': 'Scrypt'},
        {'name': 'Antminer L9 16.5 Gh/s', 'profitability': 66.26, 'algorithm': 'Scrypt'},
        {'name': 'Antminer L9 17 Gh/s', 'profitability': 68.83, 'algorithm': 'Scrypt'},
        # Antminer X11
        {'name': 'Antminer D9 1770 Gh/s', 'profitability': 30.63, 'algorithm': 'X11'},
        # Antminer Kadena
        {'name': 'Antminer KA3 166 Th/s', 'profitability': 27.77, 'algorithm': 'Kadena'},
        # Antminer kHeavyHash
        {'name': 'Antminer K7 58 Th/s', 'profitability': 21.82, 'algorithm': 'kHeavyHash'},
        {'name': 'Antminer K7 60 Th/s', 'profitability': 22.55, 'algorithm': 'kHeavyHash'},
        {'name': 'Antminer K7 63.5 Th/s', 'profitability': 23.29, 'algorithm': 'kHeavyHash'},
        {'name': 'Antminer K7 66 Th/s', 'profitability': 24.31, 'algorithm': 'kHeavyHash'},
        {'name': 'Antminer KS5pro 21 T', 'profitability': 11.31, 'algorithm': 'kHeavyHash'},
        # Antminer Blake2B-Sia
        {'name': 'Antminer HS3 9 Th/s', 'profitability': 17.41, 'algorithm': 'Blake2B-Sia'},
        # Avalon SHA-256
        {'name': 'Avalon Miner A1466 150 Th/s', 'profitability': 10.64, 'algorithm': 'SHA-256'},
        {'name': 'Avalon Miner A1566 150 Th/s', 'profitability': 10.46, 'algorithm': 'SHA-256'},
        {'name': 'Avalon Miner A1566 209 Th/s', 'profitability': 21.06, 'algorithm': 'SHA-256'},
        {'name': 'Avalon Miner A1566 212 Th/s', 'profitability': 21.29, 'algorithm': 'SHA-256'},
        # Whatsminer SHA-256
        {'name': 'Whatsminer M50 112 Th/s', 'profitability': 5.29, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M50 114 Th/s', 'profitability': 5.36, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M50 118 Th/s', 'profitability': 5.75, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M50 120 Th/s', 'profitability': 5.50, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M50 122 Th/s', 'profitability': 6.12, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M50 124 Th/s', 'profitability': 6.25, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M50s 116 Th/s', 'profitability': 7.35, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M50s 122 Th/s', 'profitability': 7.68, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M50s 124 Th/s', 'profitability': 7.63, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M50s 126 Th/s', 'profitability': 7.70, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M50s 128 Th/s', 'profitability': 7.75, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M50s 130 Th/s', 'profitability': 7.90, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M50s 132 Th/s', 'profitability': 8.01, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M50s 134 Th/s', 'profitability': 8.10, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M50s+ 142 Th/s', 'profitability': 10.18, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M50s+ 144 Th/s', 'profitability': 10.32, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M50s+ 146 Th/s', 'profitability': 10.46, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M50s++ 146 Th/s', 'profitability': 11.53, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M50s++ 154 Th/s', 'profitability': 12.85, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M50s++ 156 Th/s', 'profitability': 13.15, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M50s++ 158 Th/s', 'profitability': 13.37, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M50s++ 160 Th/s', 'profitability': 13.15, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M50s++ 162 Th/s', 'profitability': 13.31, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M50s++ 164 Th/s', 'profitability': 13.44, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M60 164 Th/s', 'profitability': 15.57, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M60 172 Th/s', 'profitability': 16.24, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M60 174 Th/s', 'profitability': 16.46, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M60 176 Th/s', 'profitability': 16.68, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M60 178 Th/s', 'profitability': 17.48, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M60 180 Th/s', 'profitability': 18.81, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M60s 176 Th/s', 'profitability': 18.73, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M60s 178 Th/s', 'profitability': 18.95, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M60s 182 Th/s', 'profitability': 19.39, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M60s 184 Th/s', 'profitability': 19.62, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M60s 186 Th/s', 'profitability': 19.83, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M61 198 Th/s', 'profitability': 19.43, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M61 200 Th/s', 'profitability': 18.81, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M61 200 Th/s бу', 'profitability': 17.48, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M61 202 Th/s', 'profitability': 18.95, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M61 204 Th/s', 'profitability': 19.18, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M64 184 Th/s', 'profitability': 20.05, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M64 188 Th/s', 'profitability': 20.50, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M64 190 Th/s', 'profitability': 20.72, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M64 194 Th/s', 'profitability': 21.01, 'algorithm': 'SHA-256'},
        # Jasminer Etchash
        {'name': 'Jasminer X16-QE 1650 Mh/s', 'profitability': 7.45, 'algorithm': 'Etchash'},
        {'name': 'Jasminer X16-QE 1750 Mh/s', 'profitability': 6.58, 'algorithm': 'Etchash'},
        {'name': 'Jasminer X16-QE 1850 Mh/s', 'profitability': 7.82, 'algorithm': 'Etchash'},
        {'name': 'Jasminer X16-Q 1950 Mh/s', 'profitability': 10.09, 'algorithm': 'Etchash'},
        {'name': 'Jasminer X16-Q Pro 2050 Mh/s', 'profitability': 11.53, 'algorithm': 'Etchash'},
        {'name': 'Jasminer X16-P 5800 Mh/s', 'profitability': 28.50, 'algorithm': 'Etchash'},
        # Elphapex Scrypt
        {'name': 'Elphapex DG HOME1 2.1 Gh/s', 'profitability': 10.55, 'algorithm': 'Scrypt'},
        {'name': 'Elphapex DG1+ 13 Gh/s', 'profitability': 39.66, 'algorithm': 'Scrypt'},
        {'name': 'Elphapex DG1+ 13.5 Gh/s', 'profitability': 42.23, 'algorithm': 'Scrypt'},
        {'name': 'Elphapex DG1+ 14 Gh/s', 'profitability': 43.19, 'algorithm': 'Scrypt'},
        {'name': 'Elphapex DG1+ 14.4 Gh/s', 'profitability': 44.44, 'algorithm': 'Scrypt'},
        # Bombax Equihash
        {'name': 'Bombax EZ100-C 4000 Mh/s', 'profitability': 19.83, 'algorithm': 'Equihash'},
        {'name': 'Bombax EZ-100 12500 Mh/s', 'profitability': 69.10, 'algorithm': 'Equihash'},
        # Goldshell
        {'name': 'Goldshell DG MAX 6.5 Gh/s', 'profitability': 15.77, 'algorithm': 'Scrypt'},
        {'name': 'Goldshell AE BOX II 54 Mh/s', 'profitability': 7.09, 'algorithm': 'Eaglesong'},
        # Fluminer Scrypt
        {'name': 'Fluminer L1 5.3 Gh/s', 'profitability': 25.94, 'algorithm': 'Scrypt'},
    ]

    # --- Настройки виртуального майнинга ---
    MINING_DURATION_SECONDS: int = 8 * 3600
    MINING_RATE_PER_HOUR: float = 10.0

    # --- Настройки для .env файла ---
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

settings = AppSettings()