import asyncio
import logging
import re
import sys
from typing import Any, Literal, Optional, Union

import aiohttp
import backoff
import bleach
from aiogram.types import CallbackQuery, Message
from aiogram.exceptions import TelegramBadRequest

from bot.keyboards.keyboards import get_main_menu_keyboard

logger = logging.getLogger(__name__)

def setup_logging():
    """Настраивает конфигурацию логирования для всего приложения."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        stream=sys.stdout,
    )
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def backoff_hdlr(details):
    """Обработчик для логирования повторных попыток backoff."""
    logger.warning(
        "Backing off {wait:0.1f} seconds after {tries} tries calling function {target}".format(**details)
    )


@backoff.on_exception(backoff.expo, aiohttp.ClientError, max_tries=3, on_backoff=backoff_hdlr)
async def make_request(
    session: aiohttp.ClientSession,
    url: str,
    response_type: Literal["json", "text"] = "json",
    headers: Optional[dict] = None
) -> Optional[Any]:
    """
    Выполняет асинхронный HTTP-запрос с использованием aiohttp и backoff для отказоустойчивости.
    """
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with session.get(url, headers=headers, timeout=timeout, ssl=False) as response:
            # ssl=False используется для обхода потенциальных SSL-ошибок с некоторыми API
            response.raise_for_status()
            if response_type == "json":
                # Игнорируем content_type для работы с некорректно настроенными API
                return await response.json(content_type=None)
            return await response.text()
    except aiohttp.ClientError as e:
        logger.error(f"Request to {url} failed after all retries: {e}")
        return None
    except Exception as e:
        logger.exception("An unexpected error occurred in make_request for URL: %s", url)
        return None


def sanitize_html(text: str) -> str:
    """Очищает текст от небезопасных HTML-тегов."""
    if not text:
        return ""
    return bleach.clean(text, tags=['b', 'i', 'u', 's', 'code', 'pre', 'a'], attributes={'a': ['href']}, strip=True)


def parse_profitability(s: str) -> float:
    """Извлекает числовое значение доходности из строки."""
    if not isinstance(s, str):
        s = str(s)
    match = re.search(r'[\d.]+', s.replace(',', '.'))
    return float(match.group(0)) if match else 0.0


def parse_power(s: str) -> Optional[int]:
    """Извлекает числовое значение мощности из строки."""
    if not isinstance(s, str):
        s = str(s)
    match = re.search(r'[\d]+', s)
    return int(match.group(0)) if match else None


async def get_message_and_chat_id(update: Union[CallbackQuery, Message]):
    """Извлекает объекты сообщения и чата из CallbackQuery или Message."""
    if isinstance(update, CallbackQuery):
        await update.answer()
        return update.message, update.message.chat.id
    return update, update.chat.id


async def show_main_menu(message: Message):
    """Отображает главное меню, пытаясь отредактировать сообщение или отправляя новое."""
    try:
        await message.edit_text("Главное меню:", reply_markup=get_main_menu_keyboard())
    except (TelegramBadRequest, AttributeError):
        await message.answer("Главное меню:", reply_markup=get_main_menu_keyboard())