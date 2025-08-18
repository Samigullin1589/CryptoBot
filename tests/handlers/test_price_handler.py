from types import SimpleNamespace
from datetime import datetime
from unittest.mock import AsyncMock
import importlib.util
from pathlib import Path

import pytest
from aiogram.types import Message, Chat, User, CallbackQuery


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "price_handler", ROOT / "bot/handlers/public/price_handler.py"
)
price_handler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(price_handler)


class DummyPriceService:
    async def get_price(self, symbol: str, vs: str):
        return 123.45

    async def _get_top_symbols(self):
        return ["BTC", "ETH"]


class FailingPriceService:
    async def get_price(self, symbol: str, vs: str):
        return None

    async def _get_top_symbols(self):
        return ["BTC", "ETH"]


@pytest.mark.asyncio
async def test_cmd_price_success():
    deps = SimpleNamespace(
        price_service=DummyPriceService(),
        market_data_service=None,
        settings=SimpleNamespace(price_service=SimpleNamespace(default_quote="USDT")),
    )
    message = Message(
        message_id=1,
        date=datetime.now(),
        chat=Chat(id=1, type="private"),
        from_user=User(id=1, is_bot=False, first_name="t"),
        text="/price BTC USDT",
    )
    object.__setattr__(message, "answer", AsyncMock())
    await price_handler.cmd_price(message, deps)
    message.answer.assert_called_once()
    assert "BTC/USDT" in message.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_cmd_price_no_data():
    deps = SimpleNamespace(
        price_service=FailingPriceService(),
        market_data_service=None,
        settings=SimpleNamespace(price_service=SimpleNamespace(default_quote="USDT")),
    )
    message = Message(
        message_id=1,
        date=datetime.now(),
        chat=Chat(id=1, type="private"),
        from_user=User(id=1, is_bot=False, first_name="t"),
        text="/price ABC USDT",
    )
    object.__setattr__(message, "answer", AsyncMock())
    await price_handler.cmd_price(message, deps)
    message.answer.assert_called_once()
    assert "Не удалось получить цену" in message.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_cb_price_invalid_request():
    deps = SimpleNamespace(price_service=DummyPriceService(), market_data_service=None)
    msg = Message(
        message_id=1,
        date=datetime.now(),
        chat=Chat(id=1, type="private"),
        from_user=User(id=1, is_bot=False, first_name="t"),
    )
    object.__setattr__(msg, "answer", AsyncMock())
    call = CallbackQuery(id="1", from_user=msg.from_user, chat_instance="1", data="price:only", message=msg)
    object.__setattr__(call, "answer", AsyncMock())
    await price_handler.cb_price(call, deps)
    call.answer.assert_called_once()
    msg.answer.assert_called_once()
    assert "Некорректный запрос" in msg.answer.call_args.args[0]
