# =================================================================================
# Файл: bot/services/market_service.py
# Версия: "Distinguished Engineer" — ПРОДАКШН (Aug 16, 2025)
# Описание:
#   Универсальный сервис "рынка" поверх внешних API и Redis.
#   - Сводка рынка (BTC, топ-коины, сеть BTC)
#   - Прокси к AsicService для топ-ASIC по профитабилити
#   - Утилиты цен: get_prices([...])
#   - Безопасная загрузка LUA-скриптов (best-effort), чтобы DI не ругался
# Зависимости:
#   settings.endpoints.*, aiohttp.ClientSession, redis.asyncio.Redis, AsicService
# =================================================================================
from __future__ import annotations

import logging
from typing import Any

import aiohttp
from redis.asyncio import Redis

from bot.config.settings import Settings
from bot.utils.http_client import make_request
from bot.services.asic_service import AsicService  # для типизации/вызовов

logger = logging.getLogger(__name__)


class MarketService:
    def __init__(
        self,
        *,
        settings: Settings,
        http_session: aiohttp.ClientSession,
        redis: Redis,
        asic_service: AsicService,
    ) -> None:
        self.settings = settings
        self.endpoints = settings.endpoints
        self.session = http_session
        self.redis = redis
        self.asic_service = asic_service
        self._lua_loaded: bool = False
        self._lua_sha_ping: str | None = None

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    async def get_market_overview(self, *, top_n: int = 10) -> dict[str, Any]:
        """
        Возвращает обобщённую сводку рынка для UI:
          - btc_price_usd
          - top_coins (id, symbol, name, current_price, price_change_24h, market_cap)
          - btc_network {hashrate_ehs, difficulty_change, estimated_retarget_date}
          - halving {progressPercent, remainingBlocks, estimated_date}
        """
        # Цены/коины
        top_coins = await self.get_top_coins_by_market_cap(limit=top_n)
        # BTC price
        prices = await self.get_prices(["bitcoin"])
        btc_price = prices.get("bitcoin")
        # Статус сети BTC
        btc_network = await self.get_btc_network_status()
        # Халвинг
        halving = await self.get_halving_info()

        return {
            "btc_price_usd": btc_price,
            "top_coins": top_coins or [],
            "btc_network": btc_network,
            "halving": halving,
        }

    async def get_top_asics(
        self, electricity_cost_usd: float, count: int = 20
    ) -> tuple[list[dict[str, Any]], int]:
        """
        Прокси к AsicService: возвращает топ ASIC по доходности при заданной цене электричества.
        """
        try:
            asics, total = await self.asic_service.get_top_asics(
                electricity_cost_usd, count=count
            )
            # Нормализуем к списку словарей (если вернулись модели)
            norm = [
                a.model_dump() if hasattr(a, "model_dump") else dict(a) for a in asics
            ]
            return norm, int(total)
        except Exception as e:
            logger.error("get_top_asics() failed: %s", e, exc_info=True)
            return [], 0

    async def get_top_coins_by_market_cap(
        self, *, limit: int = 10
    ) -> list[dict[str, Any]] | None:
        """
        Топ-коины по капе (CoinGecko public или Pro — если дан ключ).
        """
        api_key = (
            self.settings.COINGECKO_API_KEY.get_secret_value()
            if self.settings.COINGECKO_API_KEY
            else None
        )
        headers = {"x-cg-pro-api-key": api_key} if api_key else {}
        base_url = (
            self.endpoints.coingecko_api_pro_base
            if api_key
            else self.endpoints.coingecko_api_base
        )
        url = f"{base_url}{self.endpoints.coins_markets_endpoint}"
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": max(1, min(250, int(limit))),
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "24h",
        }
        try:
            data = await make_request(
                self.session, str(url), params=params, headers=headers
            )
            if isinstance(data, list):
                # Оставим только часто используемое — чтобы не дёргать UI лишними полями
                trimmed = [
                    {
                        "id": it.get("id"),
                        "symbol": it.get("symbol"),
                        "name": it.get("name"),
                        "current_price": it.get("current_price"),
                        "market_cap": it.get("market_cap"),
                        "price_change_percentage_24h": it.get(
                            "price_change_percentage_24h"
                        ),
                        "image": it.get("image"),
                    }
                    for it in data
                ]
                return trimmed
        except Exception as e:
            logger.error("get_top_coins_by_market_cap() error: %s", e, exc_info=True)
        return None

    async def get_prices(self, coin_ids: list[str]) -> dict[str, float | None]:
        """
        Простая утилита цен через CoinGecko (fallback-friendly).
        Возвращает {id: usd_price|None}
        """
        if not coin_ids:
            return {}
        api_key = (
            self.settings.COINGECKO_API_KEY.get_secret_value()
            if self.settings.COINGECKO_API_KEY
            else None
        )
        headers = {"x-cg-pro-api-key": api_key} if api_key else {}
        base_url = (
            self.endpoints.coingecko_api_pro_base
            if api_key
            else self.endpoints.coingecko_api_base
        )
        url = f"{base_url}{self.endpoints.simple_price_endpoint}"
        params = {"ids": ",".join(coin_ids), "vs_currencies": "usd"}
        try:
            data = await make_request(
                self.session, str(url), params=params, headers=headers
            )
            res = {cid: None for cid in coin_ids}
            if isinstance(data, dict):
                for cid in coin_ids:
                    v = data.get(cid) or {}
                    res[cid] = v.get("usd")
            return res
        except Exception as e:
            logger.error("get_prices() error: %s", e, exc_info=True)
            return {cid: None for cid in coin_ids}

    async def get_btc_network_status(self) -> dict[str, Any] | None:
        """
        Хешрейт/ретаргет из публичных эндпоинтов mempool.space и blockchain.info
        """
        try:
            # Hashrate (blockchain.info/q/hashrate) — GH/s → переведём в EH/s
            hashrate_ghs_str = await make_request(
                self.session,
                str(self.endpoints.blockchain_info_hashrate),
                response_type="text",
            )
            hashrate_ehs = None
            if hashrate_ghs_str:
                try:
                    gh = float(hashrate_ghs_str)
                    hashrate_ehs = (gh * 1_000.0) / 1_000_000.0  # GH/s -> TH/s -> EH/s
                except Exception:
                    hashrate_ehs = None

            # Difficulty data
            diff = await make_request(
                self.session, str(self.endpoints.mempool_space_difficulty)
            )
            est_date = None
            if diff and diff.get("nextRetargetTimeEstimate"):
                try:
                    import datetime as _dt

                    est_date = _dt.datetime.fromtimestamp(
                        diff["nextRetargetTimeEstimate"]
                    ).strftime("%d.%m.%Y")
                except Exception:
                    est_date = None

            return {
                "hashrate_ehs": hashrate_ehs,
                "difficulty_change": (diff or {}).get("difficultyChange"),
                "estimated_retarget_date": est_date,
            }
        except Exception as e:
            logger.error("get_btc_network_status() error: %s", e, exc_info=True)
            return None

    async def get_halving_info(self) -> dict[str, Any] | None:
        """
        Псевдо-дубликация логики MarketDataService, чтобы не плодить хард-зависимость.
        """
        try:
            tip = await make_request(
                self.session,
                str(self.endpoints.mempool_space_tip_height),
                response_type="text",
            )
            current_height = int(tip)
            HALVING_INTERVAL = 210000
            AVG_BLOCK_TIME_MINUTES = 10

            halving_cycle = current_height // HALVING_INTERVAL
            next_halving_block = (halving_cycle + 1) * HALVING_INTERVAL
            blocks_remaining = next_halving_block - current_height
            progress = (current_height % HALVING_INTERVAL) / HALVING_INTERVAL * 100.0

            import datetime as _dt

            estimated_date = _dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(
                minutes=blocks_remaining * AVG_BLOCK_TIME_MINUTES
            )
            return {
                "progressPercent": progress,
                "remainingBlocks": blocks_remaining,
                "estimated_date": estimated_date.strftime("%d.%m.%Y"),
            }
        except Exception as e:
            logger.error("get_halving_info() error: %s", e, exc_info=True)
            return None

    # -------------------------------------------------------------------------
    # LUA scripts (optional) — чтобы DI.safe-load_lua_scripts() не падал
    # -------------------------------------------------------------------------
    async def load_lua_scripts(self) -> None:
        """
        Best-effort загрузка простой Lua-функции ("ping") — для smoke-теста Redis EVAL.
        Если Redis недоступен — просто логируем варнинг, ничего не падает.
        """
        if self._lua_loaded:
            return
        try:
            lua = "return 'pong'"
            self._lua_sha_ping = await self.redis.script_load(lua)
            self._lua_loaded = True
            try:
                # быстрый вызов EVALSHA для проверки
                _ = await self.redis.evalsha(self._lua_sha_ping, 0)
                logger.info("MarketService: Lua-пинг загружен и выполнен успешно.")
            except Exception as e:
                logger.debug("MarketService: Lua eval failed: %s", e)
        except Exception as e:
            logger.warning("MarketService: не удалось загрузить Lua-скрипты: %s", e)

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------
    async def aclose(self) -> None:
        """Ничего закрывать не требуется — метод для симметрии с остальными сервисами."""
        return None


__all__ = ["MarketService"]
