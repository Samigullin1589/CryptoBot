# =============================================================================
# Файл: bot/keyboards/callback_factories.py
# Версия: PRODUCTION 2025 — согласовано с mining_keyboards.py и mining_game_handler.py
# Примечания:
#   • Единые фабрики CallbackData для всех модулей.
#   • Совместимы с действиями: shop/shop_page/start/confirm_purchase/main_menu/
#     my_farm/electricity/invite/withdraw/tariff_select/tariff_buy и др.
#   • Для AdminCallback используется sep="|" (в action могут быть двоеточия).
# =============================================================================

from aiogram.filters.callback_data import CallbackData

__all__ = [
    "MenuCallback",
    "GameCallback",
    "PaginatorCallback",
    "CalculatorCallback",
    "AdminCallback",
    "GameAdminCallback",
    "ThreatCallback",
    "PriceCallback",
    "AsicCallback",
    "NewsCallback",
    "QuizCallback",
    "MarketCallback",
    "CryptoCenterCallback",
    "OnboardingCallback",
]


class MenuCallback(CallbackData, prefix="menu"):
    level: int
    action: str
    value: str | None = None
    page: int | None = None


class GameCallback(CallbackData, prefix="game"):
    # Примеры: shop | shop_page | start | confirm_purchase | main_menu |
    # my_farm | electricity | invite | withdraw | tariff_select | tariff_buy
    action: str
    value: str | None = None
    page: int | None = None


class PaginatorCallback(CallbackData, prefix="pg"):
    page: int
    per_page: int | None = None
    scope: str | None = None


class CalculatorCallback(CallbackData, prefix="calc"):
    action: str
    value: str | None = None
    asic_index: int | None = None
    page: int | None = None


# Админские фабрики: используем нестандартный разделитель,
# т.к. в action встречаются значения с ':' (например, "stats:general").
class AdminCallback(CallbackData, prefix="admin", sep="|"):
    action: str
    value: str | None = None
    section: str | None = None
    page: int | None = None


# Стандартный разделитель ':' — хендлеры ожидают префикс "adgame:"
class GameAdminCallback(CallbackData, prefix="adgame"):
    action: str
    value: str | None = None
    page: int | None = None


class ThreatCallback(CallbackData, prefix="threat"):
    # actions: ban | pardon | ignore
    action: str
    user_id: int | None = None
    message_id: int | None = None
    chat_id: int | None = None


class PriceCallback(CallbackData, prefix="price"):
    action: str
    value: str | None = None
    symbol: str | None = None
    fiat: str | None = None
    page: int | None = None
    source: str | None = None
    # используется в price_handler.show_price_for_coin
    coin_id: str | None = None


# Стандартный разделитель ':' — хендлеры ожидают префикс "asic:"
class AsicCallback(CallbackData, prefix="asic"):
    action: str
    value: str | None = None
    asic_id: str | None = None
    page: int | None = None
    sort: str | None = None
    vendor: str | None = None


class NewsCallback(CallbackData, prefix="news"):
    # actions: source | category | page | open | refresh
    action: str
    source: str | None = None
    category: str | None = None
    value: str | None = None
    page: int | None = None


class QuizCallback(CallbackData, prefix="quiz"):
    # actions: start | answer | next | hint | results | page
    action: str
    value: str | None = None
    quiz_id: str | None = None
    question_id: str | None = None
    answer_id: str | None = None
    page: int | None = None


# Стандартный разделитель ':' — хендлеры ожидают префикс "market:"
class MarketCallback(CallbackData, prefix="market"):
    # actions: list | view | page | buy | filter | sort | vendor | back
    action: str
    value: str | None = None
    item_id: str | None = None
    page: int | None = None
    sort: str | None = None
    vendor: str | None = None
    q: str | None = None


# Стандартный разделитель ':' — хендлеры ожидают префикс "crypto:"
class CryptoCenterCallback(CallbackData, prefix="crypto"):
    # actions: open | section | page | refresh | back
    action: str
    value: str | None = None
    section: str | None = None
    page: int | None = None
    q: str | None = None


# Стандартный разделитель ':' — хендлеры ожидают префикс "onb:"
class OnboardingCallback(CallbackData, prefix="onb"):
    # actions: start | step | next | back | skip | finish
    action: str
    step: int | None = None
    value: str | None = None
    page: int | None = None
