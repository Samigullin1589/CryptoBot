# ======================================================================================
# File: bot/handlers/admin/health_handler.py
# Version: "Distinguished Engineer" — Aug 16, 2025
# Description:
#   Admin-only /health and /diag commands that run full self-diagnostics.
# ======================================================================================

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.config.settings import settings
from bot.diagnostics.self_test import run_full

router = Router(name="admin_health")


def _is_admin(uid: int) -> bool:
    try:
        return uid in (settings.admin_ids or [])
    except Exception:
        return False


@router.message(Command(commands={"health", "diag"}))
async def cmd_health(message: Message, deps) -> None:  # deps приходит из DependenciesMiddleware
    uid = message.from_user.id if message.from_user else 0
    if not _is_admin(uid):
        await message.answer("⛔ Доступ только для администраторов.")
        return

    try:
        result = await run_full(deps)
        await message.answer(result["report_html"], parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:  # noqa: BLE001
        await message.answer(f"❌ Self-test crashed: <code>{e}</code>", parse_mode="HTML")