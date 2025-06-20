# services/api_client.py
import asyncio
import logging
import json
from typing import List, Dict, Optional

import aiohttp
import feedparser
from bs4 import BeautifulSoup
from cachetools import TTLCache, cached
from fuzzywuzzy import process, fuzz

from config import config
from utils.models import AsicMiner, CryptoCoin
from utils.helpers import make_request, parse_power, parse_profitability, sanitize_html

logger = logging.getLogger(__name__)

# Кэши
asic_cache = TTLCache(maxsize=1, ttl=3600)
price_cache = TTLCache(maxsize=100, ttl=300)
fear_greed_cache = TTLCache(maxsize=1, ttl=14400)
news_cache = TTLCache(maxsize=1, ttl=1800)
coin_list_cache = TTLCache(maxsize=1, ttl=86400)
rub_rate_cache = TTLCache(maxsize=1, ttl=43200)

class ApiClient:
    def __init__(self, openai_client=None):
        self.openai_client = openai_client

    async def _scrape_asicminervalue(self, session: aiohttp.ClientSession) -> List[AsicMiner]:
        miners = []
        html = await make_request(session, config.ASICMINERVALUE_URL, 'text')
        if not html: return miners
        
        soup = BeautifulSoup(html, 'lxml')
        table = soup.find('table', {'id': 'datatable'})
        if not table or not table.tbody: return miners
        
        for row in table.tbody.find_all('tr', limit=50):
            cols = row.find_all('td')
            if len(cols) > 4:
                try:
                    name = cols[1].find('a').text.strip()
                    profitability = parse_profitability(cols[3].text)
                    power = parse_power(cols[4].text)
                    if profitability > 0:
                        miners.append(AsicMiner(name=name, profitability=profitability, power=power, source='AsicMinerValue'))
                except AttributeError:
                    continue
        logger.info(f"Scraped {len(miners)} miners from AsicMinerValue")
        return miners

    async def _fetch_whattomine_asics(self, session: aiohttp.ClientSession) -> List[AsicMiner]:
        miners = []
        # ИЗМЕНЕНИЕ: Добавлен правильный заголовок 'Accept' для WhatToMine
        headers = {'Accept': 'application/json'}
        data = await make_request(session, config.WHATTOOMINE_ASICS_URL, headers=headers)
        if not data or 'asics' not in data: return miners
        
        for name, asic_data in data['asics'].items():
            if asic_data.get('status') == 'Active' and 'revenue' in asic_data:
                profit = parse_profitability(asic_data['revenue'])
                if profit > 0:
                    miners.append(AsicMiner(
                        name=name, profitability=profit, algorithm=asic_data.get('algorithm'),
                        hashrate=str(asic_data.get('hashrate')), power=parse_power(str(asic_data.get('power', 0))),
                        source='WhatToMine'
                    ))
        logger.info(f"Fetched {len(miners)} miners from WhatToMine")
        return miners

    @cached(cache=asic_cache)
    async def get_profitable_asics(self) -> List[AsicMiner]:
        logger.info("Updating ASIC miners cache...")
        async with aiohttp.ClientSession() as session:
            tasks = [self._scrape_asicminervalue(session), self._fetch_whattomine_asics(session)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        all_miners = [miner for res in results if isinstance(res, list) for miner in res]
        if not all_miners:
            logger.warning("Using fallback ASIC list.")
            return [AsicMiner(**asic) for asic in config.FALLBACK_ASICS]

        final_miners: Dict[str, AsicMiner] = {}
        for miner in sorted(all_miners, key=lambda m: m.name):
            best_match, score = process.extractOne(miner.name, final_miners.keys(), scorer=fuzz.token_set_ratio) if final_miners else (None, 0)
            
            if score > 90 and best_match:
                existing = final_miners[best_match]
                if miner.profitability > existing.profitability: existing.profitability = miner.profitability
                existing.algorithm = existing.algorithm or miner.algorithm
                existing.hashrate = existing.hashrate or miner.hashrate
                existing.power = existing.power or miner.power
            else:
                final_miners[miner.name] = miner
        
        sorted_list = sorted(final_miners.values(), key=lambda m: m.profitability, reverse=True)
        logger.info(f"ASIC cache updated with {len(sorted_list)} unique devices.")
        return sorted_list

    @cached(cache=coin_list_cache)
    async def get_coin_list(self) -> Dict[str, str]:
        logger.info("Updating coin list cache...")
        coin_algo_map = {}
        async with aiohttp.ClientSession() as s:
            data = await make_request(s, f"{config.MINERSTAT_API_BASE}/coins")
            if data:
                for coin_data in data:
                    if symbol := coin_data.get('coin'):
                        coin_algo_map[symbol.upper()] = coin_data.get('algorithm')
        logger.info(f"Coin list cache updated with {len(coin_algo_map)} coins.")
        return coin_algo_map

    @cached(cache=price_cache)
    async def get_crypto_price(self, query: str) -> Optional[CryptoCoin]:
        query_norm = config.TICKER_ALIASES.get(query.strip().lower(), query.strip().lower())
        
        async with aiohttp.ClientSession() as session:
            logger.info(f"Attempting to fetch price for '{query_norm}' from CoinGecko.")
            cg_search_data = await make_request(session, f"{config.COINGECKO_API_BASE}/search?query={query_norm}")
            if cg_search_data and cg_search_data.get('coins'):
                coin_id = cg_search_data['coins'][0].get('id')
                market_data_list = await make_request(session, f"{config.COINGECKO_API_BASE}/coins/markets?vs_currency=usd&ids={coin_id}")
                if market_data_list:
                    md = market_data_list[0]
                    symbol = md.get('symbol', '').upper()
                    coin_list = await self.get_coin_list()
                    logger.info(f"Successfully fetched price for '{query_norm}' from CoinGecko.")
                    return CryptoCoin(
                        id=md.get('id'), symbol=symbol, name=md.get('name'), price=md.get('current_price', 0.0),
                        price_change_24h=md.get('price_change_percentage_24h'), algorithm=coin_list.get(symbol)
                    )
            
            logger.warning(f"Failed to get price from CoinGecko for '{query_norm}'. Falling back to CoinPaprika.")
            cp_search_data = await make_request(session, f"{config.COINPAPRIKA_API_BASE}/search?q={query_norm}&c=currencies")
            if cp_search_data and cp_search_data.get('currencies'):
                target_coin = next((c for c in cp_search_data['currencies'] if c['symbol'].lower() == query_norm), cp_search_data['currencies'][0])
                coin_id = target_coin.get('id')
                
                ticker_data = await make_request(session, f"{config.COINPAPRIKA_API_BASE}/tickers/{coin_id}")
                if ticker_data:
                    quotes = ticker_data.get('quotes', {}).get('USD', {})
                    symbol = ticker_data.get('symbol', '').upper()
                    coin_list = await self.get_coin_list()
                    logger.info(f"Successfully fetched price for '{query_norm}' from CoinPaprika.")
                    return CryptoCoin(
                        id=ticker_data.get('id'), symbol=symbol, name=ticker_data.get('name'),
                        price=quotes.get('price', 0.0), price_change_24h=quotes.get('percent_change_24h'),
                        algorithm=coin_list.get(symbol)
                    )
        logger.error(f"Failed to get price for '{query_norm}' from all sources.")
        return None
    
    @cached(cache=rub_rate_cache)
    async def get_usd_rub_rate(self) -> float:
        logger.info("Fetching USD/RUB exchange rate.")
        async with aiohttp.ClientSession() as session:
            data = await make_request(session, config.CBR_DAILY_JSON_URL)
            if data and "Valute" in data and "USD" in data["Valute"]:
                rate = data["Valute"]["USD"]["Value"]
                logger.info(f"Current USD/RUB rate: {rate}")
                return float(rate)
        logger.warning("Using fallback USD/RUB rate.")
        return 90.0

    @cached(cache=fear_greed_cache)
    async def get_fear_and_greed_index(self) -> Optional[Dict]:
        async with aiohttp.ClientSession() as session:
            if config.CMC_API_KEY:
                headers = {'X-CMC_PRO_API_KEY': config.CMC_API_KEY}
                data = await make_request(session, config.CMC_FEAR_AND_GREED_URL, headers=headers)
                if data and 'data' in data:
                    logger.info("Fetched F&G index from CoinMarketCap")
                    return data['data'][0]
                logger.warning("Failed to fetch from CMC, falling back to Alternative.me")
            data = await make_request(session, config.FEAR_AND_GREED_API_URL)
            if data and 'data' in data and data['data']:
                logger.info("Fetched F&G index from Alternative.me")
                return data['data'][0]
        logger.error("Failed to fetch F&G index from all sources.")
        return None

    @cached(cache=news_cache)
    async def fetch_latest_news(self) -> List[Dict]:
        all_news = []
        async def parse_feed(url):
            try:
                async with aiohttp.ClientSession() as s:
                    text = await make_request(s, url, 'text')
                    if text:
                        feed = feedparser.parse(text)
                        for entry in feed.entries:
                            all_news.append({'title': sanitize_html(entry.title), 'link': entry.link, 'published': getattr(entry, 'published_parsed', None)})
            except Exception as e:
                logger.warning(f"Failed to parse RSS feed {url}", extra={'error': str(e)})
        await asyncio.gather(*(parse_feed(url) for url in config.NEWS_RSS_FEEDS))
        all_news.sort(key=lambda x: x['published'] or (0,), reverse=True)
        return list({item['title'].lower(): item for item in all_news}.values())[:5]

    async def get_halving_info(self) -> str:
        async with aiohttp.ClientSession() as s:
            height_str = await make_request(s, "https://mempool.space/api/blocks/tip/height", 'text')
            if not height_str or not height_str.isdigit(): return "❌ Не удалось получить данные о халвинге."
            current_block, interval = int(height_str), 210000
            blocks_left = interval - (current_block % interval)
            days = blocks_left / 144
            return f"⏳ <b>До халвинга Bitcoin осталось:</b>\n\n🧱 <b>Блоков:</b> <code>{blocks_left:,}</code>\n🗓 <b>Примерно дней:</b> <code>{days:.1f}</code>"

    async def get_btc_network_status(self) -> str:
        async with aiohttp.ClientSession() as s:
            urls = ["https://mempool.space/api/v1/fees/recommended", "https://mempool.space/api/mempool"]
            fees, mempool = await asyncio.gather(*(make_request(s, url) for url in urls))
            if not fees or not mempool: return "❌ Не удалось получить статус сети BTC."
            return (f"📡 <b>Статус сети Bitcoin:</b>\n\n"
                    f"📈 <b>Транзакций в мемпуле:</b> <code>{mempool.get('count', 'N/A'):,}</code>\n\n"
                    f"💸 <b>Рекомендуемые комиссии (sat/vB):</b>\n"
                    f"  - 🚀 Высокий: <code>{fees.get('fastestFee', 'N/A')}</code>\n"
                    f"  - 🚶‍♂️ Средний: <code>{fees.get('halfHourFee', 'N/A')}</code>\n"
                    f"  - 🐢 Низкий: <code>{fees.get('hourFee', 'N/A')}</code>")

    async def generate_quiz_question(self) -> Optional[Dict]:
        if not self.openai_client: return None
        logger.info("Generating quiz question with OpenAI...")
        prompt = ('Создай 1 интересный вопрос для викторины на тему криптовалют или майнинга. '
                  'Ответ верни строго в формате JSON-объекта с ключами: "question", '
                  '"options" (массив из 4 строк), "correct_option_index" (число от 0 до 3).')
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o", messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}, temperature=0.8
            )
            quiz_data = json.loads(response.choices[0].message.content)
            if all(k in quiz_data for k in ['question', 'options', 'correct_option_index']):
                return quiz_data
        except Exception as e:
            logger.error("Failed to generate quiz question", extra={'error': str(e)})
        return None