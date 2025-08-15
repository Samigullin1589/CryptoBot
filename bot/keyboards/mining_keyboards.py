# ===============================================================
# Файл: bot/keyboards/mining_keyboards.py (ПРОДАКШН-ВЕРСИЯ 2025 - ПОЛНАЯ ВОССТАНОВЛЕННАЯ)
# Описание: Генераторы клавиатур для игры "Виртуальный Майнинг" и Калькулятора.
# ИСПРАВЛЕНИЯ:
#   • Переход на фабрики CallbackData.
#   • Клавиатура тарифов поддерживает dict/объекты, безопасное форматирование цены.
#   • Корректные действия: покупка/выбор/пометка текущего, кнопка «Назад».
#   • Совместима с вашим mining_game_handler.py (confirm_purchase и т.д.).
# ===============================================================

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence, List
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.utils.models import AsicMiner
from bot.utils.text_utils import normalize_asic_name
from .callback_factories import MenuCallback, GameCallback, PaginatorCallback, CalculatorCallback  # noqa: F401

PAGE_SIZE = 5

# -------------------------- утилиты ---------------------------

def _get(obj: Any, key: str, default=None):
    """Атрибут из объекта или ключ из dict."""
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _fmt_money(val: Any, digits: int = 0, dash: str = "—") -> str:
    """Безопасное форматирование суммы (None -> '—')."""
    try:
        if val is None:
            return dash
        return f"{float(val):,.{digits}f}".replace(",", " ")
    except (TypeError, ValueError):
        return str(val) if val is not None else dash


def _normalize_items(tariffs: Iterable[Any] | Mapping[str, Any]) -> Sequence[tuple[str, Any]]:
    """Приводим тарифы к списку пар (name, data)."""
    if isinstance(tariffs, Mapping):
        return [(k, tariffs[k]) for k in sorted(tariffs.keys())]
    items: list[tuple[str, Any]] = []
    for i, t in enumerate(tariffs):
        inferred = _get(t, "name", None)
        items.append((inferred or f"Тариф {i + 1}", t))
    return items


# -------------------- Клавиатуры игры -------------------------

def get_mining_menu_keyboard(is_session_active: bool) -> InlineKeyboardMarkup:
    """
    Главное меню игры (динамически скрывает кнопку запуска сессии).
    """
    builder = InlineKeyboardBuilder()

    if not is_session_active:
        builder.button(text="▶️ Начать сессию", callback_data=GameCallback(action="shop").pack())

    builder.button(text="🏠 Моя ферма", callback_data=GameCallback(action="my_farm").pack())
    builder.button(text="💡 Электричество", callback_data=GameCallback(action="electricity").pack())
    builder.button(text="🤝 Пригласить друга", callback_data=GameCallback(action="invite").pack())
    builder.button(text="⬅️ Назад в меню", callback_data=MenuCallback(level=0, action="main").pack())

    builder.adjust(1 if not is_session_active else 2, 2, 1)
    return builder.as_markup()


def get_shop_keyboard(asics: List[AsicMiner], page: int = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    start_offset = page * PAGE_SIZE
    end_offset = start_offset + PAGE_SIZE

    for asic in asics[start_offset:end_offset]:
        asic_id = normalize_asic_name(asic.name)
        profit_str = f" ({_fmt_money(asic.profitability, 2)}$/день)" if getattr(asic, "profitability", None) is not None else ""
        builder.button(
            text=f"Купить {asic.name}{profit_str}",
            callback_data=GameCallback(action="start", value=asic_id).pack(),
        )

    # Навигация
    nav_buttons: list[InlineKeyboardButton] = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=GameCallback(action="shop_page", page=page - 1).pack(),
            )
        )

    total_pages = (len(asics) + PAGE_SIZE - 1) // PAGE_SIZE
    if total_pages > 1:
        nav_buttons.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="do_nothing"))

    if end_offset < len(asics):
        nav_buttons.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=GameCallback(action="shop_page", page=page + 1).pack(),
            )
        )

    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="⬅️ Назад в меню", callback_data=GameCallback(action="main_menu").pack()))
    builder.adjust(1)
    return builder.as_markup()


def get_confirm_purchase_keyboard(item_id: str) -> InlineKeyboardMarkup:
    """
    Клавиатура подтверждения покупки — строго под ваш handler:
    - Подтвердить -> action="confirm_purchase"
    - Отмена      -> action="main_menu"
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Купить", callback_data=GameCallback(action="confirm_purchase", value=item_id).pack())
    builder.button(text="❌ Отмена", callback_data=GameCallback(action="main_menu").pack())
    builder.adjust(2)
    return builder.as_markup()


def get_my_farm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Вывести средства", callback_data=GameCallback(action="withdraw").pack())
    builder.button(text="⬅️ Назад в меню", callback_data=GameCallback(action="main_menu").pack())
    builder.adjust(1)
    return builder.as_markup()


def get_withdraw_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Понятно", callback_data=GameCallback(action="main_menu").pack())
    return builder.as_markup()


def get_electricity_menu_keyboard(
    tariffs: Iterable[Any] | Mapping[str, Any],
    user_tariffs: List[str] | None,
    current_tariff: str | None,
) -> InlineKeyboardMarkup:
    """
    Клавиатура тарифов:
      • Если не куплен -> 🛒 <name> (<цена/бесплатно>) -> tariff_buy
      • Если куплен    -> 🔌 Выбрать: <name>           -> tariff_select
      • Если текущий   -> ✅ <name> (текущий)          -> tariff_select
    Поддерживает:
      - список объектов (name, unlock_price)
      - список dict'ов ({name, unlock_price})
      - dict[name] = объект/словарь
    """
    builder = InlineKeyboardBuilder()
    owned = set(user_tariffs or [])
    items = _normalize_items(tariffs)

    for raw_name, data in items:
        name = _get(data, "name", raw_name) or raw_name
        unlock_price = _get(data, "unlock_price", None)

        is_owned = name in owned
        is_current = (current_tariff == name)

        if is_owned:
            if is_current:
                builder.button(
                    text=f"✅ {name} (текущий)",
                    callback_data=GameCallback(action="tariff_select", value=name).pack(),
                )
            else:
                builder.button(
                    text=f"🔌 Выбрать: {name}",
                    callback_data=GameCallback(action="tariff_select", value=name).pack(),
                )
        else:
            price_txt = "бесплатно" if unlock_price in (None, 0, "0", "0.0") else f"{_fmt_money(unlock_price, 0)} монет"
            builder.button(
                text=f"🛒 {name} ({price_txt})",
                callback_data=GameCallback(action="tariff_buy", value=name).pack(),
            )

    builder.button(text="⬅️ Назад в меню", callback_data=GameCallback(action="main_menu").pack())
    builder.adjust(1)
    return builder.as_markup()

# ---------------- Клавиатуры калькулятора ---------------------

def get_calculator_cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="cancel_fsm")
    return builder.as_markup()


def get_currency_selection_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="USD ($)", callback_data=CalculatorCallback(action="currency", value="usd").pack())
    builder.button(text="RUB (₽)", callback_data=CalculatorCallback(action="currency", value="rub").pack())
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm"))
    builder.adjust(2)
    return builder.as_markup()


def get_asic_selection_keyboard(asics: List[AsicMiner], page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    start_offset = page * PAGE_SIZE
    end_offset = start_offset + PAGE_SIZE

    for i, asic in enumerate(asics[start_offset:end_offset], start=start_offset):
        builder.button(text=asic.name, callback_data=CalculatorCallback(action="select_asic", asic_index=i).pack())

    nav_buttons: list[InlineKeyboardButton] = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="⬅️ Назад", callback_data=CalculatorCallback(action="page", page=page - 1).pack())
        )
    if end_offset < len(asics):
        nav_buttons.append(
            InlineKeyboardButton(text="Вперед ➡️", callback_data=CalculatorCallback(action="page", page=page + 1).pack())
        )

    if nav_buttons:
        builder.row(*nav_buttons)
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm"))
    builder.adjust(1)
    return builder.as_markup()


def get_calculator_result_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Новый расчёт", callback_data=MenuCallback(level=1, action="calculator").pack())
    builder.button(text="🏠 Главное меню", callback_data=MenuCallback(level=0, action="main").pack())
    builder.adjust(1)
    return builder.as_markup()