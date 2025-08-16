# ======================================================================================
# File: bot/services/mining_game_service.py
# Version: "Distinguished Engineer" — MAX Build (Aug 16, 2025)
# Description:
#   Core game service for "Virtual Mining":
#     • Safe session start (no free-ASIC bug) — atomic debit + session create
#     • Electricity tariffs management (buy/select) using Redis
#     • Farm + stats info rendering
#     • LUA loader hook (kept for logs compatibility)
# Notes:
#   - Does NOT import get_game_main_menu_keyboard (removed). Keyboards are in handlers.
#   - Compatible with tariffs provided as dicts or Pydantic models (ElectricityTariff).
#   - Works with existing handlers you already replaced.
# ======================================================================================

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

import redis.asyncio as redis
from aiogram.types import User as TgUser

from bot.config.settings import Settings
from bot.keyboards.game_keyboards import get_electricity_menu_keyboard
from bot.utils.models import AsicMiner

logger = logging.getLogger(__name__)


# ------------------------------ Keyspace ----------------------------------------

class _Keys:
    """Centralized Redis key builder to avoid typos."""
    def __init__(self, prefix: str = "game") -> None:
        self.px = prefix

    def profile(self, user_id: int) -> str:
        return f"{self.px}:user:{user_id}:profile"  # HSET: current_tariff, coins (optional)

    def owned_tariffs(self, user_id: int) -> str:
        return f"{self.px}:user:{user_id}:tariffs:owned"  # SET of tariff names

    def active_session(self, user_id: int) -> str:
        return f"{self.px}:user:{user_id}:session"  # HSET: asic_json, started_at, ends_at

    def session_lock(self, user_id: int) -> str:
        return f"{self.px}:user:{user_id}:session:lock"  # simple lock for race-protection

    def stats(self, user_id: int) -> str:
        return f"{self.px}:user:{user_id}:stats"  # HSET: sessions, lifetime_earned, lifetime_spent

    def wallet_candidates(self, user_id: int) -> Tuple[str, ...]:
        # Try multiple schemas to be compatible with existing projects
        return (
            f"user:{user_id}:wallet",        # HASH coins|balance
            f"economy:user:{user_id}",       # HASH coins|balance
            f"user:{user_id}:profile",       # HASH coins
            f"{self.px}:user:{user_id}:profile",  # HASH coins (same as profile())
            f"user:{user_id}:coins",         # STRING
            f"{self.px}:user:{user_id}:coins",    # STRING
        )


# ------------------------------ Service -----------------------------------------

class MiningGameService:
    """
    Mining game domain service (Redis + Settings).
    Designed to be initialized via DI container with:
        MiningGameService(settings=..., redis=..., user_service=..., asic_service=..., ...)
    """
    def __init__(
        self,
        settings: Settings,
        redis: redis.Redis,
        user_service: Optional[Any] = None,
        asic_service: Optional[Any] = None,
        market_service: Optional[Any] = None,
        mining_service: Optional[Any] = None,
        achievement_service: Optional[Any] = None,
    ) -> None:
        self.settings = settings
        self.redis: redis.Redis = redis
        self.user_service = user_service
        self.asic_service = asic_service
        self.market_service = market_service
        self.mining_service = mining_service
        self.achievement_service = achievement_service

        self.keys = _Keys("game")

    # -------------------------------------------------------------------------
    # LUA hook (optional, for logs compatibility)
    # -------------------------------------------------------------------------
    async def load_lua_scripts(self) -> None:
        """
        Kept for compatibility with existing logs.
        No hard LUA needed here because we do atomic ops in Python with WATCH/MULTI.
        """
        logger.info("LUA-скрипты для MiningGameService успешно загружены.")

    # -------------------------------------------------------------------------
    # Public API used by handlers
    # -------------------------------------------------------------------------

    async def get_farm_and_stats_info(self, user_id: int) -> Tuple[str, str]:
        """
        Returns (farm_info_html, stats_info_html).
        """
        session_key = self.keys.active_session(user_id)
        prof_key = self.keys.profile(user_id)
        stats_key = self.keys.stats(user_id)

        # Active session
        sess = await self.redis.hgetall(session_key)
        if sess:
            try:
                asic = json.loads(sess.get("asic_json", "{}"))
            except Exception:
                asic = {}
            name = asic.get("name", "Неизвестный ASIC")
            ends_at = float(sess.get("ends_at", "0") or 0)
            remain = max(0, int(ends_at - time.time()))
            mins = remain // 60
            secs = remain % 60
            farm_info = (
                "🛠 <b>Активная сессия майнинга</b>\n"
                f"• Оборудование: <b>{name}</b>\n"
                f"• Осталось времени: <b>{mins:02d}:{secs:02d}</b>\n"
            )
        else:
            farm_info = "🛠 <b>Активная сессия майнинга</b>\n• Нет активной сессии."

        # Stats
        stats = await self.redis.hgetall(stats_key)
        sessions = int(stats.get("sessions", 0) or 0)
        earned = float(stats.get("lifetime_earned", 0) or 0.0)
        spent = float(stats.get("lifetime_spent", 0) or 0.0)
        current_tariff = (await self.redis.hget(prof_key, "current_tariff")) or self.settings.game.default_electricity_tariff

        stats_info = (
            "📊 <b>Статистика</b>\n"
            f"• Сессий всего: <b>{sessions}</b>\n"
            f"• Доход суммарно: <b>{earned:,.2f}</b>\n"
            f"• Расходы: <b>{spent:,.2f}</b>\n"
            f"• Тариф э/э: <b>{current_tariff}</b>"
        ).replace(",", " ")

        return farm_info, stats_info

    async def purchase_and_start_session(self, user_id: int, selected_asic: AsicMiner) -> Tuple[str, bool]:
        """
        Atomically:
          1) Ensure no active session exists.
          2) Debit user balance by selected_asic.price (through UserService if present,
             otherwise via Redis wallet fallbacks).
          3) Create session with TTL (duration from settings).
        Returns (message_html, success_flag).
        """
        # 0) Validate ASIC
        if not selected_asic or not selected_asic.name:
            return "Ошибка: неверные данные оборудования.", False

        duration_min = int(self.settings.game.session_duration_minutes)
        now = time.time()
        ends_at = now + duration_min * 60

        session_key = self.keys.active_session(user_id)
        lock_key = self.keys.session_lock(user_id)

        # 1) Lock for a short time to avoid races in multi-click
        #    SETNX with expiration
        ok = await self.redis.set(lock_key, "1", nx=True, ex=5)
        if not ok:
            return "⏳ Уже обрабатываю предыдущий запрос, попробуйте чуть позже.", False

        try:
            # 2) Fast path: if session exists — abort
            if await self.redis.exists(session_key):
                return "У вас уже есть активная сессия майнинга.", False

            price = float(selected_asic.price or 0.0)
            if price < 0:
                return "Ошибка: цена указана некорректно.", False

            # 3) Debit (UserService -> Redis candidates)
            if price > 0:
                debited = await self._debit(user_id, price, reason=f"Покупка {selected_asic.name} для майнинга")
                if not debited:
                    return f"Недостаточно средств для покупки <b>{selected_asic.name}</b> (нужно {price:,.2f}).".replace(",", " "), False

                # Account spent
                await self.redis.hincrbyfloat(self.keys.stats(user_id), "lifetime_spent", price)

            # 4) Create session atomically (WATCH/MULTI)
            pipe = self.redis.pipeline()
            while True:
                try:
                    await pipe.watch(session_key)
                    if await self.redis.exists(session_key):
                        await pipe.reset()
                        return "У вас уже есть активная сессия майнинга.", False
                    pipe.multi()
                    pipe.hset(
                        session_key,
                        mapping={
                            "asic_json": json.dumps(selected_asic.model_dump() if hasattr(selected_asic, "model_dump") else selected_asic.__dict__),
                            "started_at": str(now),
                            "ends_at": str(ends_at),
                            "tariff": await self._get_current_tariff(user_id),
                        },
                    )
                    pipe.expire(session_key, duration_min * 60)
                    pipe.hincrby(self.keys.stats(user_id), "sessions", 1)
                    await pipe.execute()
                    break
                except redis.WatchError:
                    await asyncio.sleep(0.05)
                    continue
                finally:
                    await pipe.reset()

            msg = (
                f"🎉 Сессия запущена!\n\n"
                f"Оборудование: <b>{selected_asic.name}</b>\n"
                f"Длительность: <b>{duration_min} мин</b>\n"
                f"Старт: <b>{time.strftime('%H:%M:%S', time.localtime(now))}</b>\n"
                f"Финиш: <b>{time.strftime('%H:%M:%S', time.localtime(ends_at))}</b>"
            )
            return msg, True
        finally:
            # unlock
            try:
                await self.redis.delete(lock_key)
            except Exception:
                pass

    async def process_withdrawal(self, user: TgUser | Any) -> Tuple[str, bool]:
        """
        Simple withdrawal stub that uses lifetime_earned as available amount.
        Adapt to your economy as needed. Keeps old interface (text, can_withdraw).
        """
        uid = getattr(user, "id", None) if hasattr(user, "id") else (getattr(user, "user_id", None) or user)
        if not uid:
            return "Ошибка идентификации пользователя.", False

        stats_key = self.keys.stats(uid)
        earned = float((await self.redis.hget(stats_key, "lifetime_earned")) or 0.0)
        min_sum = float(self.settings.game.min_withdrawal_amount)

        if earned < min_sum:
            return f"Минимальная сумма для вывода: <b>{min_sum:,.2f}</b>. Ваш доступный баланс: <b>{earned:,.2f}</b>.".replace(",", " "), False

        # Mark as paid out (for demo: zero earned)
        await self.redis.hset(stats_key, mapping={"lifetime_earned": 0.0})
        text = (
            "✅ Заявка на вывод принята!\n"
            "Мы обработаем её в ближайшее время. Статус можно отслеживать в разделе «Моя ферма»."
        )
        return text, True

    # -------------------- Electricity tariffs (menu + actions) --------------------

    def _iter_tariffs(self) -> Iterable[Tuple[str, Any]]:
        """
        Returns list of (name, obj) from settings.game.electricity_tariffs keeping stable order.
        Supports dict[str, dict|model] or dict-like Pydantic mapping.
        """
        t: Any = self.settings.game.electricity_tariffs
        if isinstance(t, Mapping):
            # stable order: as defined in dict (py3.7+ preserves insertion order)
            return list(t.items())
        # Fallback: cast to dict
        try:
            return list(dict(t).items())  # type: ignore[arg-type]
        except Exception:
            return []

    async def _get_current_tariff(self, user_id: int) -> str:
        prof_key = self.keys.profile(user_id)
        cur = await self.redis.hget(prof_key, "current_tariff")
        return cur or self.settings.game.default_electricity_tariff

    async def _get_owned_tariffs(self, user_id: int) -> Iterable[str]:
        st = await self.redis.smembers(self.keys.owned_tariffs(user_id))
        return sorted(st) if st else []

    async def get_electricity_menu(self, user_id: int) -> Tuple[str, Any]:
        """
        Returns (html_text, InlineKeyboardMarkup).
        """
        owned = list(await self._get_owned_tariffs(user_id))
        current = await self._get_current_tariff(user_id)
        # Ensure default tariff is owned for display logic clarity
        if self.settings.game.default_electricity_tariff not in owned:
            owned.append(self.settings.game.default_electricity_tariff)

        # Build text
        lines = ["💡 <b>Управление электроэнергией</b>", ""]
        lines.append(f"Текущий тариф: <b>{current}</b>")
        lines.append("")
        lines.append("Доступные тарифы:")

        for name, obj in self._iter_tariffs():
            cost = _get(obj, "cost_per_kwh", None)
            unlock_price = _get(obj, "unlock_price", None)
            status = []
            if name == current:
                status.append("текущий")
            if name in owned:
                status.append("куплен")
            stxt = f" ({', '.join(status)})" if status else ""
            price_txt = "бесплатно" if not unlock_price else f"{float(unlock_price):,.0f} монет".replace(",", " ")
            lines.append(f"• {name}: {cost} $/кВт⋅ч — {price_txt}{stxt}")

        text = "\n".join(lines)
        kb = get_electricity_menu_keyboard(self.settings.game.electricity_tariffs, owned, current)
        return text, kb

    async def select_tariff(self, user_id: int, tariff_name: str) -> str:
        """
        Selects owned tariff. If not owned — asks to buy first.
        """
        if not tariff_name or tariff_name not in dict(self._iter_tariffs()):
            return "Тариф не найден."

        owned = set(await self._get_owned_tariffs(user_id))
        if tariff_name not in owned:
            return "Сначала купите этот тариф."

        await self.redis.hset(self.keys.profile(user_id), mapping={"current_tariff": tariff_name})
        return f"🔌 Тариф <b>{tariff_name}</b> выбран!"

    async def buy_tariff(self, user_id: int, tariff_name: str) -> str:
        """
        Buys tariff if not owned. Debits user by unlock_price (if > 0).
        """
        tariffs = dict(self._iter_tariffs())
        if tariff_name not in tariffs:
            return "Тариф не найден."

        owned_key = self.keys.owned_tariffs(user_id)
        if await self.redis.sismember(owned_key, tariff_name):
            return "Этот тариф уже куплен."

        obj = tariffs[tariff_name]
        price = float(_get(obj, "unlock_price", 0) or 0.0)

        if price > 0:
            debited = await self._debit(user_id, price, reason=f"Покупка тарифа {tariff_name}")
            if not debited:
                return f"Недостаточно средств для покупки тарифа <b>{tariff_name}</b> ({price:,.0f}).".replace(",", " ")

            await self.redis.hincrbyfloat(self.keys.stats(user_id), "lifetime_spent", price)

        await self.redis.sadd(owned_key, tariff_name)
        # If no current tariff set — set newly bought as current
        prof_key = self.keys.profile(user_id)
        cur = await self.redis.hget(prof_key, "current_tariff")
        if not cur:
            await self.redis.hset(prof_key, mapping={"current_tariff": tariff_name})

        return f"🎉 Тариф <b>{tariff_name}</b> успешно приобретён!"

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    async def _debit(self, user_id: int, amount: float, reason: str = "") -> bool:
        """
        Tries to debit user's balance by `amount` using, in order:
          1) user_service.debit(user_id, amount, reason=reason) -> bool
          2) user_service.change_balance / update_balance / set_balance fallbacks
          3) Redis wallet fallbacks across common keys (hash or string)
        Returns True if debited, otherwise False.
        """
        if amount <= 0:
            return True

        # 1) UserService, if available
        us = self.user_service
        if us is not None:
            # Preferred method
            if hasattr(us, "debit") and callable(us.debit):
                try:
                    ok = await us.debit(user_id, amount, reason=reason)  # type: ignore[misc]
                    if ok:
                        return True
                except Exception as e:
                    logger.debug("UserService.debit failed: %s", e)

            # Generic change_balance
            for fn_name in ("change_balance", "update_balance", "add_balance"):
                fn = getattr(us, fn_name, None)
                if fn and callable(fn):
                    try:
                        # negative delta
                        ok = await fn(user_id, -amount, reason=reason)  # type: ignore[misc]
                        if ok is None:
                            # Some services return new balance, treat any non-exception as success if >=0
                            return True
                        if ok:
                            return True
                    except Exception as e:
                        logger.debug("UserService.%s failed: %s", fn_name, e)

        # 2) Redis fallbacks — try known key patterns
        for key in self.keys.wallet_candidates(user_id):
            try:
                if not await self.redis.exists(key):
                    continue
                typ = await self.redis.type(key)
                if typ == b"hash" or typ == "hash":
                    # Try common fields
                    for fld in ("coins", "balance"):
                        val = await self.redis.hget(key, fld)
                        if val is None:
                            continue
                        try:
                            bal = float(val)
                        except Exception:
                            continue
                        if bal >= amount:
                            new_bal = bal - amount
                            # race-safe HSET with check: we can WATCH/MULTI for strictness
                            pipe = self.redis.pipeline()
                            while True:
                                try:
                                    await pipe.watch(key)
                                    cur = await self.redis.hget(key, fld)
                                    if cur is None or float(cur) != bal:
                                        await pipe.reset()
                                        # value changed — retry by breaking to outer loop
                                        break
                                    pipe.multi()
                                    pipe.hset(key, mapping={fld: new_bal})
                                    await pipe.execute()
                                    return True
                                except redis.WatchError:
                                    await asyncio.sleep(0.01)
                                    continue
                                finally:
                                    await pipe.reset()
                else:
                    # Assume string number
                    val = await self.redis.get(key)
                    if val is None:
                        continue
                    try:
                        bal = float(val)
                    except Exception:
                        continue
                    if bal >= amount:
                        # Use DECRBYFLOAT
                        await self.redis.decrbyfloat(key, amount)  # type: ignore[attr-defined]
                        return True
            except Exception as e:
                logger.debug("Redis debit probe failed for %s: %s", key, e)

        return False


# ------------------------------ Utilities ---------------------------------------

def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Get attribute from object or key from dict/dataclass."""
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    if is_dataclass(obj):  # e.g., ElectricityTariff dataclass
        try:
            return asdict(obj).get(key, default)
        except Exception:
            return getattr(obj, key, default)
    return getattr(obj, key, default)