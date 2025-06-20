# config.py
import os
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
    NEWS_CHAT_ID = os.getenv("NEWS_CHAT_ID")
    CMC_API_KEY = os.getenv("CMC_API_KEY")

    COINGECKO_API_BASE = "https://api.coingecko.com/api/v3"
    COINPAPRIKA_API_BASE = "https://api.coinpaprika.com/v1"
    MINERSTAT_API_BASE = "https://api.minerstat.com/v2"
    WHATTOOMINE_ASICS_URL = "https://whattomine.com/asics.json"
    ASICMINERVALUE_URL = "https://www.asicminervalue.com/"
    FEAR_AND_GREED_API_URL = "https://api.alternative.me/fng/?limit=1"
    CMC_FEAR_AND_GREED_URL = "https://pro-api.coinmarketcap.com/v1/crypto/fear-and-greed"
    CBR_DAILY_JSON_URL = "https://www.cbr-xml-daily.ru/daily_json.js"

    NEWS_RSS_FEEDS = [
        "https://forklog.com/feed", "https://bits.media/rss/", "https://www.rbc.ru/crypto/feed",
        "https://beincrypto.ru/feed/", "https://cointelegraph.com/rss/tag/russia"
    ]
    NEWS_INTERVAL_HOURS = 3
    ASIC_CACHE_UPDATE_HOURS = 1

    TICKER_ALIASES = {'бтк': 'BTC', 'биткоин': 'BTC', 'биток': 'BTC', 'eth': 'ETH', 'эфир': 'ETH', 'эфириум': 'ETH'}
    POPULAR_TICKERS = ['BTC', 'ETH', 'SOL', 'TON', 'KAS']

    # Обновленный и расширенный аварийный список ASIC
    FALLBACK_ASICS: List[Dict[str, Any]] = [
        # Antminer SHA-256
        {'name': 'Antminer S19 K Pro 110 Th/s', 'hashrate': '110 Th/s', 'profitability': 7.08, 'algorithm': 'SHA-256'},
        {'name': 'Antminer S19 K Pro 115 Th/s', 'hashrate': '115 Th/s', 'profitability': 7.39, 'algorithm': 'SHA-256'},
        {'name': 'Antminer S19 K Pro 120 Th/s', 'hashrate': '120 Th/s', 'profitability': 8.03, 'algorithm': 'SHA-256'},
        {'name': 'Antminer S19 XP 134 Th/s', 'hashrate': '134 Th/s', 'profitability': 9.43, 'algorithm': 'SHA-256'},
        {'name': 'Antminer S19J XP 151 Th/s', 'hashrate': '151 Th/s', 'profitability': 13.44, 'algorithm': 'SHA-256'},
        {'name': 'Antminer T21 190 Th/s', 'hashrate': '190 Th/s', 'profitability': 21.23, 'algorithm': 'SHA-256'},
        {'name': 'Antminer S21 200 Th/s', 'hashrate': '200 Th/s', 'profitability': 19.10, 'algorithm': 'SHA-256'},
        {'name': 'Antminer S21+ 235 Th/s', 'hashrate': '235 Th/s', 'profitability': 26.82, 'algorithm': 'SHA-256'},
        {'name': 'Antminer S21 XP 270 Th/s', 'hashrate': '270 Th/s', 'profitability': 52.52, 'algorithm': 'SHA-256'},
        # Antminer Hydro SHA-256
        {'name': 'Antminer S19 XP HYDRO 257 Th/s', 'hashrate': '257 Th/s', 'profitability': 19.83, 'algorithm': 'SHA-256'},
        {'name': 'Antminer S21 HYDRO 335 Th/s', 'hashrate': '335 Th/s', 'profitability': 45.17, 'algorithm': 'SHA-256'},
        {'name': 'Antminer S21+ HYDRO 395 Th/s', 'hashrate': '395 Th/s', 'profitability': 47.01, 'algorithm': 'SHA-256'},
        {'name': 'Antminer S21 XP HYDRO 473 Th/s', 'hashrate': '473 Th/s', 'profitability': 93.65, 'algorithm': 'SHA-256'},
        # Antminer Scrypt
        {'name': 'Antminer L7 8050 Mh/s', 'hashrate': '8050 Mh/s', 'profitability': 19.03, 'algorithm': 'Scrypt'},
        {'name': 'Antminer L7 9500 Mh/s', 'hashrate': '9500 Mh/s', 'profitability': 31.81, 'algorithm': 'Scrypt'},
        {'name': 'Antminer L9 17 Gh/s', 'hashrate': '17 Gh/s', 'profitability': 68.83, 'algorithm': 'Scrypt'},
        # Antminer KHeavyHash (Kaspa)
        {'name': 'Antminer KS5pro 21 T', 'hashrate': '21 T', 'profitability': 11.31, 'algorithm': 'kHeavyHash'},
        {'name': 'Antminer K7 66 Th/s', 'hashrate': '66 Th/s', 'profitability': 24.31, 'algorithm': 'kHeavyHash'},
        # Antminer Other Algos
        {'name': 'Antminer Z15 pro 840 ksol', 'hashrate': '840 ksol', 'profitability': 14.00, 'algorithm': 'Equihash'},
        {'name': 'Antminer D9 1770 Gh/s', 'hashrate': '1770 Gh/s', 'profitability': 30.63, 'algorithm': 'X11'},
        {'name': 'Antminer KA3 166 Th/s', 'hashrate': '166 Th/s', 'profitability': 27.77, 'algorithm': 'Kadena'},
        {'name': 'Antminer HS3 9 Th/s', 'hashrate': '9 Th/s', 'profitability': 17.41, 'algorithm': 'Blake2B-Sia'},
        # Avalon
        {'name': 'Avalon Miner A1466 150 Th/s', 'hashrate': '150 Th/s', 'profitability': 10.64, 'algorithm': 'SHA-256'},
        {'name': 'Avalon Miner A1566 212 Th/s', 'hashrate': '212 Th/s', 'profitability': 21.29, 'algorithm': 'SHA-256'},
        # Whatsminer
        {'name': 'Whatsminer M50 124 Th/s', 'hashrate': '124 Th/s', 'profitability': 6.25, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M50s+ 146 Th/s', 'hashrate': '146 Th/s', 'profitability': 10.46, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M50s++ 164 Th/s', 'hashrate': '164 Th/s', 'profitability': 13.44, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M60 180 Th/s', 'hashrate': '180 Th/s', 'profitability': 18.81, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M60s 186 Th/s', 'hashrate': '186 Th/s', 'profitability': 19.83, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M61 204 Th/s', 'hashrate': '204 Th/s', 'profitability': 19.18, 'algorithm': 'SHA-256'},
        {'name': 'Whatsminer M64 194 Th/s', 'hashrate': '194 Th/s', 'profitability': 21.01, 'algorithm': 'SHA-256'},
        # Jasminer
        {'name': 'Jasminer X16-Q Pro 2050 Mh/s', 'hashrate': '2050 Mh/s', 'profitability': 11.53, 'algorithm': 'Etchash'},
        {'name': 'Jasminer X16-P 5800 Mh/s', 'hashrate': '5800 Mh/s', 'profitability': 28.50, 'algorithm': 'Etchash'},
        # Elphapex
        {'name': 'Elphapex DG1+ 14.4 Gh/s', 'hashrate': '14.4 Gh/s', 'profitability': 44.44, 'algorithm': 'Scrypt'},
        # Bombax
        {'name': 'Bombax EZ-100 12500 Mh/s', 'hashrate': '12500 Mh/s', 'profitability': 69.10, 'algorithm': 'Equihash'},
        # Goldshell
        {'name': 'Goldshell DG MAX 6.5 Gh/s', 'hashrate': '6.5 Gh/s', 'profitability': 15.77, 'algorithm': 'Scrypt'},
        {'name': 'Goldshell AE BOX II 54 Mh/s', 'hashrate': '54 Mh/s', 'profitability': 7.09, 'algorithm': 'Eaglesong'},
        # Fluminer
        {'name': 'Fluminer L1 5.3 Gh/s', 'hashrate': '5.3 Gh/s', 'profitability': 25.94, 'algorithm': 'Scrypt'},
    ]

config = Config()