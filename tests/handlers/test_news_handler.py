from types import SimpleNamespace
from datetime import datetime
from unittest.mock import AsyncMock
import importlib.util
from pathlib import Path

import pytest
from aiogram.types import Message, Chat, User, CallbackQuery


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "news_handler", ROOT / "bot/handlers/public/news_handler.py"
)
news_handler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(news_handler)


class DummyNewsService:
    async def get_cached(self):
        return [
            {"title": f"Title {i}", "url": "http://example.com", "src": "SRC"}
            for i in range(9)
        ]


class EmptyNewsService:
    async def get_cached(self):
        return []


@pytest.mark.asyncio
async def test_cmd_news_renders_items():
    deps = SimpleNamespace(news_service=DummyNewsService())
    message = Message(
        message_id=1,
        date=datetime.now(),
        chat=Chat(id=1, type="private"),
        from_user=User(id=1, is_bot=False, first_name="t"),
        text="/news",
    )
    object.__setattr__(message, "answer", AsyncMock())
    await news_handler.cmd_news(message, deps)
    message.answer.assert_called_once()
    assert "Крипто-новости" in message.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_cmd_news_empty_list():
    deps = SimpleNamespace(news_service=EmptyNewsService())
    message = Message(
        message_id=1,
        date=datetime.now(),
        chat=Chat(id=1, type="private"),
        from_user=User(id=1, is_bot=False, first_name="t"),
        text="/news",
    )
    object.__setattr__(message, "answer", AsyncMock())
    await news_handler.cmd_news(message, deps)
    message.answer.assert_called_once()
    assert "Пока новостей нет" in message.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_cb_news_page_navigation():
    deps = SimpleNamespace(news_service=DummyNewsService())
    msg = Message(
        message_id=1,
        date=datetime.now(),
        chat=Chat(id=1, type="private"),
        from_user=User(id=1, is_bot=False, first_name="t"),
    )
    object.__setattr__(msg, "edit_text", AsyncMock())
    call = CallbackQuery(id="1", from_user=msg.from_user, chat_instance="1", data="news:page:1", message=msg)
    object.__setattr__(call, "answer", AsyncMock())
    await news_handler.cb_news(call, deps)
    call.answer.assert_called_once()
    msg.edit_text.assert_called_once()
    assert "страница 2" in msg.edit_text.call_args.args[0]
