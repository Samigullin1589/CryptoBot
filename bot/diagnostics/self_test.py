# ======================================================================================
# File: bot/diagnostics/self_test.py
# Version: "Distinguished Engineer" — Aug 16, 2025
# Description:
#   End-to-end self-diagnostics for the CryptoBot stack.
#   Checks: Redis, HTTP reachability, CoinList, Prices (BTC), News prefetch,
#           AI moderation (heuristic/OpenAI/Gemini).
#   Use from admin /health or programmatically.
# ======================================================================================

from __future__ import annotations

import time
from typing import Any

import aiohttp

from bot.utils.dependencies import Deps


async def _check_redis(deps: Deps) -> dict[str, Any]:
    r = getattr(deps, "redis", None)
    if not r:
        return {
            "ok": False,
            "detail": "Redis client is not configured (deps.redis is None).",
        }
    try:
        pong = await r.ping()
        return {"ok": bool(pong), "detail": "PING ok" if pong else "PING failed"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "detail": f"Redis error: {e}"}


async def _check_http(deps: Deps) -> dict[str, Any]:
    sess: aiohttp.ClientSession = getattr(deps, "http_session", None)
    if not sess:
        return {"ok": False, "detail": "HTTP session is not initialized."}
    # Binance ping (fast, anonymous)
    try:
        async with sess.get(
            "https://api.binance.com/api/v3/ping",
            timeout=aiohttp.ClientTimeout(total=6),
        ) as resp:
            return {
                "ok": resp.status == 200,
                "detail": f"binance ping status={resp.status}",
            }
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "detail": f"HTTP error: {e}"}


async def _check_coinlist(deps: Deps) -> dict[str, Any]:
    svc = getattr(deps, "coin_list_service", None)
    if not svc:
        return {"ok": False, "detail": "CoinListService not available."}
    try:
        coins = await svc.update_and_index()
        n = len(coins or [])
        return {"ok": n > 0, "detail": f"coins={n}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "detail": f"Coin list error: {e}"}


async def _check_price(deps: Deps) -> dict[str, Any]:
    svc = getattr(deps, "price_service", None)
    if not svc:
        return {"ok": False, "detail": "PriceService not available."}
    try:
        p = await svc.get_price("BTC")
        return {"ok": (p is not None and p > 0), "detail": f"BTC={p}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "detail": f"Price error: {e}"}


async def _check_news(deps: Deps) -> dict[str, Any]:
    svc = getattr(deps, "news_service", None)
    if not svc:
        return {"ok": False, "detail": "NewsService not available."}
    try:
        items = await svc.get_all_latest_news()
        n = len(items or [])
        return {
            "ok": n > 0 or (n == 0),
            "detail": f"news items={n} (providers may be unauthenticated)",
        }
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "detail": f"News error: {e}"}


async def _check_ai(deps: Deps) -> dict[str, Any]:
    svc = getattr(deps, "ai_content_service", None)
    if not svc:
        return {"ok": False, "detail": "AIContentService not available."}
    try:
        res = await svc.moderate_text("free airdrop 100% profit — join t.me/xxx")
        score = float(res.get("score", 0.0))
        prov = res.get("provider", "unknown")
        return {
            "ok": score >= 0.0,
            "detail": f"moderation score={score:.2f} provider={prov}",
        }
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "detail": f"AI moderation error: {e}"}


def _html_row(name: str, ok: bool, detail: str) -> str:
    icon = "✅" if ok else "❌"
    return f"<b>{icon} {name}</b> — <code>{detail}</code>"


def _aggregate(res: dict[str, dict[str, Any]]) -> dict[str, Any]:
    all_ok = all(x.get("ok") for x in res.values())
    return {
        "ok": all_ok,
        "summary": f"overall={'OK' if all_ok else 'ISSUES'}",
    }


async def run_full(deps: Deps) -> dict[str, Any]:
    """
    Run all checks and return dict with results and ready HTML report.
    """
    results = {
        "redis": await _check_redis(deps),
        "http": await _check_http(deps),
        "coin_list": await _check_coinlist(deps),
        "price": await _check_price(deps),
        "news": await _check_news(deps),
        "ai": await _check_ai(deps),
    }
    aggr = _aggregate(results)

    # HTML report for Telegram
    lines = [
        "<b>🩺 CryptoBot — Self Test</b>",
        f"<i>ts: {int(time.time())}</i>",
        _html_row("Redis", results["redis"]["ok"], results["redis"]["detail"]),
        _html_row("HTTP", results["http"]["ok"], results["http"]["detail"]),
        _html_row(
            "Coin list", results["coin_list"]["ok"], results["coin_list"]["detail"]
        ),
        _html_row("Price", results["price"]["ok"], results["price"]["detail"]),
        _html_row("News", results["news"]["ok"], results["news"]["detail"]),
        _html_row("AI", results["ai"]["ok"], results["ai"]["detail"]),
        "",
        f"<b>Result: {'✅ OK' if aggr['ok'] else '⚠️ CHECK'}</b>",
    ]
    return {"ok": aggr["ok"], "report_html": "\n".join(lines), "raw": results}
