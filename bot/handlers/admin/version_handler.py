# ======================================================================================
# File: bot/handlers/admin/version_handler.py
# Version: "Distinguished Engineer" — Aug 16, 2025
# Description:
#   Admin-only /version — shows runtime versions and feature flags.
# ======================================================================================

from __future__ import annotations

import platform
import sys

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.config.settings import settings

router = Router(name="admin_version")


def _is_admin(uid: int) -> bool:
    try:
        return uid in (settings.admin_ids or [])
    except Exception:
        return False


@router.message(Command("version"))
async def cmd_version(message: Message, deps) -> None:
    if not _is_admin(message.from_user.id):
        await message.answer("⛔ Доступ только для администраторов.")
        return

    # Lib versions (best-effort)
    try:
        import aiogram  # type: ignore
        import aiohttp  # type: ignore
        import redis  # type: ignore
        import apscheduler  # type: ignore
        import openai  # type: ignore
        import google.generativeai as genai  # type: ignore
    except Exception:
        aiogram = aiohttp = redis = apscheduler = openai = genai = None  # type: ignore

    # Feature flags
    has_openai = bool(getattr(settings, "OPENAI_API_KEY", None))
    has_gemini = bool(getattr(settings, "GEMINI_API_KEY", None) or getattr(settings, "GOOGLE_API_KEY", None))
    has_cp = bool(getattr(settings, "CRYPTOPANIC_TOKEN", None))
    has_newsapi = bool(getattr(settings, "NEWSAPI_KEY", None))

    lines = [
        "<b>🧩 CryptoBot — Version</b>",
        f"• Python: <code>{platform.python_version()}</code> ({sys.platform})",
        f"• aiogram: <code>{getattr(aiogram, '__version__', 'n/a')}</code>",
        f"• aiohttp: <code>{getattr(aiohttp, '__version__', 'n/a')}</code>",
        f"• redis: <code>{getattr(redis, '__version__', 'n/a')}</code>",
        f"• APScheduler: <code>{getattr(apscheduler, '__version__', 'n/a')}</code>",
        f"• openai: <code>{getattr(openai, '__version__', 'n/a')}</code> — {'✅' if has_openai else '—'}",
        f"• google-generativeai: <code>{getattr(genai, '__version__', 'n/a') if genai else 'n/a'}</code> — {'✅' if has_gemini else '—'}",
        "",
        "<b>Providers</b>",
        f"• CryptoPanic: {'✅' if has_cp else '—'}",
        f"• NewsAPI: {'✅' if has_newsapi else '—'}",
        "",
        "<i>Совет: /health для полной диагностики</i>",
    ]
    await message.answer("\n".join(lines), parse_mode="HTML", disable_web_page_preview=True)