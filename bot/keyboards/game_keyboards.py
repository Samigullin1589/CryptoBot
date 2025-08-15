# =============================================================================
# File: bot/keyboards/game_keyboards.py
# Version: "Distinguished Engineer" - SAFE BUILD
# Notes:
#   - Electricity tariffs keyboard now supports both dict and object items
#   - No changes in callback payload shape (uses your GameCallback if available)
# =============================================================================

from __future__ import annotations

from typing import Any, Iterable, Mapping

from aiogram.utils.keyboard import InlineKeyboardBuilder

# Try both typical paths; if none present, we'll build plain strings
try:
    from bot.callbacks.game_callbacks import GameCallback  # common path in your repo
except Exception:  # noqa: BLE001
    try:
        from bot.callbacks.game_callback import GameCallback
    except Exception:  # noqa: BLE001
        GameCallback = None  # type: ignore[misc,assignment]


def _get(obj: Any, key: str, default=None):
    """Fetches attribute from object or key from dict."""
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _get_name(tariff_obj: Any, fallback: str) -> str:
    name = _get(tariff_obj, "name", None)
    return name or fallback


def _pack_callback(action: str, value: str) -> str:
    """
    Packs callback_data using your GameCallback if it's available,
    otherwise returns a plain string with 'action:value'.
    """
    if GameCallback:
        return GameCallback(action=action, value=value).pack()
    return f"{action}:{value}"


def get_electricity_menu_keyboard(
    tariffs: Iterable[Any] | Mapping[str, Any],
    owned: list[str] | None,
    current: str | None,
):
    """
    Build keyboard for electricity tariffs.
    Accepts tariffs as:
      - list of objects with attributes: name, unlock_price
      - list of dicts with keys: name, unlock_price
      - dict mapping {name: tariff_dict_or_object}
    """
    builder = InlineKeyboardBuilder()
    owned = owned or []

    if isinstance(tariffs, Mapping):
        items: list[tuple[str, Any]] = list(tariffs.items())
    else:
        # If it's a list, try to infer names; fallback to index-based aliases
        items = []
        for i, t in enumerate(tariffs):
            inferred = _get(t, "name", None)
            items.append((inferred or f"Тариф {i + 1}", t))

    for raw_name, data in items:
        name = _get_name(data, raw_name)
        unlock_price = _get(data, "unlock_price", None)

        owned_mark = " ✅" if name in owned else ""
        current_mark = " • Текущий" if current and name == current else ""

        if unlock_price in (None, 0, "0", "0.0"):
            price_txt = "бесплатно"
        else:
            try:
                price_txt = f"{float(unlock_price):.0f} монет"
            except Exception:  # noqa: BLE001
                price_txt = f"{unlock_price} монет"

        builder.button(
            text=f"🛒 {name}{owned_mark}{current_mark} ({price_txt})",
            callback_data=_pack_callback("tariff_buy", name),
        )

    builder.adjust(1)
    return builder.as_markup()