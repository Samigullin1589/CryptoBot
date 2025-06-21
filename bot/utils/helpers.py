import logging
import sys
import re
import asyncio
from typing import Literal, Optional, Any, Union

import aiohttp
import bleach
from aiogram.types import Message, CallbackQuery

from bot.utils.keyboards import get_main_menu_keyboard

logger = logging.getLogger(__name__)

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        stream=sys.stdout,
    )
    logging.getLogger("aiogram.dispatcher").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

async def make_request(
    session: aiohttp.ClientSession,
    url: str,
    response_type: Literal['json', 'text'] = 'json',
    headers: Optional[dict] = None,
    retries: int = 3
) -> Optional[Any]:
    for attempt in range(retries):
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with session.get(url, headers=headers, timeout=timeout) as response:
                response.raise_for_status()
                if response_type == 'json':
                    return await response.json()
                return await response.text()
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            if attempt < retries - 1:
                logger.warning(f"Request to {url} failed. Retrying in {attempt + 1}s... Error: {e}")
                await asyncio.sleep(attempt + 1)
            else:
                logger.error(f"Request to {url} failed after {retries} retries. Error: {e}")
        except Exception:
            logger.exception("Unexpected error in make_request for URL: %s", url)
            break
    return None

def sanitize_html(text: str) -> str:
    if not text:
        return ""
    return bleach.clean(text, tags=['b', 'i', 'u', 's', 'code', 'pre', 'a'], attributes={'a': ['href']}, strip=True)

def parse_profitability(s: str) -> float:
    if not isinstance(s, str):
        s = str(s)
    match = re.search(r'[\d.]+', s.replace(',', '.'))
    return float(match.group(0)) if match else 0.0

def parse_power(s: str) -> Optional[int]:
    if not isinstance(s, str):
        s = str(s)
    match = re.search(r'[\d]+', s)
    return int(match.group(0)) if match else None

async def get_message_and_chat_id(update: Union[CallbackQuery, Message]):
    if isinstance(update, CallbackQuery):
        await update.answer()
        return update.message, update.message.chat.id
    return update, update.chat.id

async def show_main_menu(message: Message):
    try:
        await message.edit_text("Главное меню:", reply_markup=get_main_menu_keyboard())
    except Exception:
        await message.answer("Главное меню:", reply_markup=get_main_menu_keyboard())