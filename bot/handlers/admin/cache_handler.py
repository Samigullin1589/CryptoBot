# ======================================================================================
# File: bot/handlers/admin/cache_handler.py
# Version: "Distinguished Engineer" — Aug 16, 2025
# Description:
#   Admin-only cache utilities:
#     • /cache_info                         — show cache stats & TTLs
#     • /cache_clear [coins|prices|news|all] — purge selected caches
# ======================================================================================

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.config.settings import settings

router = Router(name="admin_cache")


def _is_admin(uid: int) -> bool:
    try:
        return uid in (settings.admin_ids or [])
    except Exception:
        return False


async def _count_scan(r, pattern: str, *, batch: int = 500) -> int:
    if not r:
        return 0
    cur = 0
    total = 0
    while True:
        cur, keys = await r.scan(cursor=cur, match=pattern, count=batch)
        total += len(keys)
        if cur == 0:
            break
    return total


@router.message(Command("cache_info"))
async def cache_info(message: Message, deps) -> None:  # deps из DependenciesMiddleware
    if not _is_admin(message.from_user.id):
        await message.answer("⛔ Доступ только для администраторов.")
        return

    r = getattr(deps, "redis", None)
    if not r:
        await message.answer("Redis не сконфигурирован.")
        return

    # собираем показатели
    coin_exists = await r.exists("coin:list")
    coin_ttl = await r.ttl("coin:list")

    news_exists = await r.exists("news:latest")
    news_ttl = await r.ttl("news:latest")

    price_cnt = await _count_scan(r, "price:*")
    # пример TTL для BTC/USDT
    sample_ttl = await r.ttl("price:BTC:USDT")

    lines = [
        "<b>🧰 Cache info</b>",
        f"• coin:list — {'есть' if coin_exists else 'нет'}, ttl={coin_ttl}s",
        f"• news:latest — {'есть' if news_exists else 'нет'}, ttl={news_ttl}s",
        f"• price:* — ~{price_cnt} ключ(ей), ttl(BTC/USDT)={sample_ttl}s",
    ]
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("cache_clear"))
async def cache_clear(message: Message, deps) -> None:
    if not _is_admin(message.from_user.id):
        await message.answer("⛔ Доступ только для администраторов.")
        return

    args = (message.text or "").split()
    target = args[1].lower() if len(args) > 1 else "all"

    r = getattr(deps, "redis", None)
    if not r:
        await message.answer("Redis не сконфигурирован.")
        return

    deleted = 0

    async def _del_pattern(pat: str) -> int:
        cur = 0
        total = 0
        while True:
            cur, keys = await r.scan(cursor=cur, match=pat, count=500)
            if keys:
                await r.delete(*keys)
                total += len(keys)
            if cur == 0:
                break
        return total

    if target in ("coins", "coin", "all"):
        deleted += await _del_pattern("coin:index:*")
        deleted += int(await r.delete("coin:list") or 0)

    if target in ("prices", "price", "all"):
        deleted += await _del_pattern("price:*")

    if target in ("news", "all"):
        deleted += int(await r.delete("news:latest") or 0)

    await message.answer(f"🧹 Удалено ключей: <b>{deleted}</b>", parse_mode="HTML")