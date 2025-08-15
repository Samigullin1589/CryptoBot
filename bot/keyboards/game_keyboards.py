# =============================================================================
# File: bot/keyboards/game_keyboards.py
# Version: "Distinguished Engineer" - SAFE BUILD (merged)
# Notes:
#   - Electricity tariffs keyboard supports dicts and objects
#   - Uses GameCallback from your project; keeps payload shape
#   - Shows proper actions:
#       • not owned  -> 🛒 tariff_buy
#       • owned      -> 🔌 tariff_select
#       • current    -> ✅ <name> (текущий)
#   - Safe money formatting, stable order, Back button
# =============================================================================

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

# Try the canonical path first (used elsewhere in your codebase);
# keep fallbacks to avoid import errors in custom layouts.
GameCallback = None  # type: ignore[assignment]
try:
    from bot.keyboards.callback_factories import GameCallback as _GC  # main path in your repo
    GameCallback = _GC  # type: ignore[assignment]
except Exception:  # noqa: BLE001
    try:
        from bot.callbacks.game_callbacks import GameCallback as _GC  # alt path
        GameCallback = _GC  # type: ignore[assignment]
    except Exception:  # noqa: BLE001
        try:
            from bot.callbacks.game_callback import GameCallback as _GC  # alt path 2
            GameCallback = _GC  # type: ignore[assignment]
        except Exception:  # noqa: BLE001
            GameCallback = None  # final fallback – plain strings (see _pack_callback)


def _get(obj: Any, key: str, default=None):
    """Fetch attribute from object or key from dict."""
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _fmt_money(val: Any, digits: int = 0, dash: str = "—") -> str:
    """Safe money formatting: None -> '—', non-numeric -> as-is."""
    try:
        if val is None:
            return dash
        return f"{float(val):,.{digits}f}".replace(",", " ")
    except (TypeError, ValueError):
        return str(val) if val is not None else dash


def _pack_callback(action: str, value: str) -> str:
    """
    Pack callback_data using GameCallback if available,
    otherwise fall back to a plain 'action:value' string.
    NOTE: fallback will not match GameCallback.filter, so make sure
    your handlers can accept it if the factory isn't importable.
    """
    if GameCallback:
        return GameCallback(action=action, value=value).pack()
    return f"{action}:{value}"


def _normalize_items(
    tariffs: Iterable[Any] | Mapping[str, Any],
) -> Sequence[tuple[str, Any]]:
    """
    Normalize tariffs into a list[(name, data)].
    Supports:
      - Mapping[str, Any]  -> sorted by name
      - Iterable[Any]      -> keep order; name from item.name or fallback
    """
    if isinstance(tariffs, Mapping):
        return [(k, tariffs[k]) for k in sorted(tariffs.keys())]

    items: list[tuple[str, Any]] = []
    for i, t in enumerate(tariffs):
        inferred = _get(t, "name", None)
        items.append((inferred or f"Тариф {i + 1}", t))
    return items


def get_electricity_menu_keyboard(
    tariffs: Iterable[Any] | Mapping[str, Any],
    owned: Iterable[str] | None,
    current: str | None,
) -> InlineKeyboardMarkup:
    """
    Build keyboard for electricity tariffs.
    Accepts tariffs as:
      - list of objects with attributes: name, unlock_price
      - list of dicts with keys: name, unlock_price
      - dict mapping {name: tariff_dict_or_object}
    Buttons:
      - Not owned -> 🛒 <name> (<price>)  -> tariff_buy
      - Owned     -> 🔌 Выбрать: <name>   -> tariff_select
      - Current   -> ✅ <name> (текущий)  -> tariff_select
    """
    owned_set = set(owned or [])
    items = _normalize_items(tariffs)

    builder = InlineKeyboardBuilder()

    for raw_name, data in items:
        name = _get(data, "name", raw_name) or raw_name
        unlock_price = _get(data, "unlock_price", None)

        is_owned = name in owned_set
        is_current = (current == name)

        if is_owned:
            if is_current:
                # Current tariff — mark as selected
                builder.button(
                    text=f"✅ {name} (текущий)",
                    callback_data=_pack_callback("tariff_select", name),
                )
            else:
                builder.button(
                    text=f"🔌 Выбрать: {name}",
                    callback_data=_pack_callback("tariff_select", name),
                )
        else:
            # Not owned — show price and buy action
            price_txt = "бесплатно" if unlock_price in (None, 0, "0", "0.0") else f"{_fmt_money(unlock_price, 0)} монет"
            builder.button(
                text=f"🛒 {name} ({price_txt})",
                callback_data=_pack_callback("tariff_buy", name),
            )

        builder.adjust(1)

    # Back to main menu
    builder.button(
        text="⬅️ Назад",
        callback_data=_pack_callback("main_menu", "0"),
    )
    builder.adjust(1)

    return builder.as_markup()