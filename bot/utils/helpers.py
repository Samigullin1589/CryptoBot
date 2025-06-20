# utils/helpers.py
import logging
import json
import re
import random
import asyncio
from typing import Optional, Any

import aiohttp
import bleach
from pythonjsonlogger import jsonlogger

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    if logger.hasHandlers():
        logger.handlers.clear()
    log_handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter('%(asctime)s %(name)s %(levelname)s %(message)s')
    log_handler.setFormatter(formatter)
    logger.addHandler(log_handler)

def sanitize_html(text: str) -> str:
    return bleach.clean(text, tags=[], attributes={}, strip=True).strip()

async def make_request(session: aiohttp.ClientSession, url: str, response_type='json', **kwargs) -> Optional[Any]:
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
    ]
    headers = kwargs.get('headers', {})
    if 'User-Agent' not in headers:
        headers['User-Agent'] = random.choice(user_agents)
    kwargs['headers'] = headers
    
    logger = logging.getLogger(__name__)
    
    try:
        async with session.get(url, timeout=15, **kwargs) as response:
            response.raise_for_status()
            if response_type == 'json':
                return await response.json()
            elif response_type == 'text':
                return await response.text()
    except Exception as e:
        logger.warning("Request failed", extra={'url': url, 'error': str(e)})
    return None

def parse_power(power_str: str) -> Optional[int]:
    cleaned = re.sub(r'[^0-9]', '', str(power_str))
    return int(cleaned) if cleaned.isdigit() else None

def parse_profitability(profit_str: str) -> float:
    cleaned = re.sub(r'[^\d.]', '', str(profit_str))
    return float(cleaned) if cleaned and cleaned != '.' else 0.0