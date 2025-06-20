# Файл: bot/utils/helpers.py

import logging
import sys
import re
import asyncio
from typing import Literal, Optional, Any
import aiohttp
import bleach

logger = logging.getLogger(__name__)

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        stream=sys.stdout,
    )
    logging.getLogger("aiogram.dispatcher").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)

async def make_request(
    session: aiohttp.ClientSession,
    url: str,
    response_type: Literal['json', 'text'] = 'json',
    headers: Optional[dict] = None
) -> Optional[Any]:
    try:
        timeout = aiohttp.ClientTimeout(total=15) # Увеличим таймаут на всякий случай
        async with session.get(url, headers=headers, timeout=timeout) as response:
            response.raise_for_status()
            if response_type == 'json':
                return await response.json()
            return await response.text()
    except aiohttp.ClientResponseError as e:
        logger.error(f"HTTP Error: {e.status} for URL: {url}")
    except asyncio.TimeoutError:
        logger.error(f"Request Timeout for URL: {url}")
    except aiohttp.ClientError as e:
        logger.error(f"ClientError: {e.__class__.__name__} for URL: {url}")
    except Exception:
        logger.exception("Unexpected error in make_request for URL: %s", url)
    return None

def sanitize_html(text: str) -> str:
    if not text: return ""
    return bleach.clean(text, tags=['b', 'i', 'u', 's', 'code', 'pre', 'a'], attributes={'a': ['href']}, strip=True)

def parse_profitability(s: str) -> float:
    if not isinstance(s, str): s = str(s)
    match = re.search(r'[\d.]+', s.replace(',', '.'))
    return float(match.group(0)) if match else 0.0

def parse_power(s: str) -> Optional[int]:
    if not isinstance(s, str): s = str(s)
    match = re.search(r'[\d]+', s)
    return int(match.group(0)) if match else None