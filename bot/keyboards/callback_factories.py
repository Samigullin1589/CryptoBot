# =============================================================================
# Файл: bot/keyboards/callback_factories.py
# Версия: PRODUCTION 2025 — согласовано с mining_keyboards.py и mining_game_handler.py
# Примечания:
#   • Единые фабрики CallbackData для всех модулей.
#   • Совместимы с действиями: shop/shop_page/start/confirm_purchase/main_menu/
#     my_farm/electricity/invite/withdraw/tariff_select/tariff_buy и др.
#   • Для AdminCallback используется sep="|" (в action могут быть двоеточия).
# =============================================================================

from typing import Optional
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
    value: Optional[str] = None
    page: Optional[int] = None


class GameCallback(CallbackData, prefix="game"):
    # Примеры: shop | shop_page | start | confirm_purchase | main_menu |
    # my_farm | electricity | invite | withdraw | tariff_select | tariff_buy
    action: str
    value: Optional[str] = None
    page: Optional[int] = None


class PaginatorCallback(CallbackData, prefix="pg"):
    page: int
    per_page: Optional[int] = None
    scope: Optional[str] = None


class CalculatorCallback(CallbackData, prefix="calc"):
    action: str
    value: Optional[str] = None
    asic_index: Optional[int] = None
    page: Optional[int] = None


# Админские фабрики: используем нестандартный разделитель,
# т.к. в action встречаются значения с ':' (например, "stats:general").
class AdminCallback(CallbackData, prefix="admin", sep="|"):
    action: str
    value: Optional[str] = None
    section: Optional[str] = None
    page: Optional[int] = None


# Стандартный разделитель ':' — хендлеры ожидают префикс "adgame:"
class GameAdminCallback(CallbackData, prefix="adgame"):
    action: str
    value: Optional[str] = None
    page: Optional[int] = None


class ThreatCallback(CallbackData, prefix="threat"):
    # actions: ban | pardon | ignore
    action: str
    user_id: Optional[int] = None
    message_id: Optional[int] = None
    chat_id: Optional[int] = None


class PriceCallback(CallbackData, prefix="price"):
    action: str
    value: Optional[str] = None
    symbol: Optional[str] = None
    fiat: Optional[str] = None
    page: Optional[int] = None
    source: Optional[str] = None
    # используется в price_handler.show_price_for_coin
    coin_id: Optional[str] = None


# Стандартный разделитель ':' — хендлеры ожидают префикс "asic:"
class AsicCallback(CallbackData, prefix="asic"):
    action: str
    value: Optional[str] = None
    asic_id: Optional[str] = None
    page: Optional[int] = None
    sort: Optional[str] = None
    vendor: Optional[str] = None


class NewsCallback(CallbackData, prefix="news"):
    # actions: source | category | page | open | refresh
    action: str
    source: Optional[str] = None
    category: Optional[str] = None
    value: Optional[str] = None
    page: Optional[int] = None


class QuizCallback(CallbackData, prefix="quiz"):
    # actions: start | answer | next | hint | results | page
    action: str
    value: Optional[str] = None
    quiz_id: Optional[str] = None
    question_id: Optional[str] = None
    answer_id: Optional[str] = None
    page: Optional[int] = None


# Стандартный разделитель ':' — хендлеры ожидают префикс "market:"
class MarketCallback(CallbackData, prefix="market"):
    # actions: list | view | page | buy | filter | sort | vendor | back
    action: str
    value: Optional[str] = None
    item_id: Optional[str] = None
    page: Optional[int] = None
    sort: Optional[str] = None
    vendor: Optional[str] = None
    q: Optional[str] = None


# Стандартный разделитель ':' — хендлеры ожидают префикс "crypto:"
class CryptoCenterCallback(CallbackData, prefix="crypto"):
    # actions: open | section | page | refresh | back
    action: str
    value: Optional[str] = None
    section: Optional[str] = None
    page: Optional[int] = None
    q: Optional[str] = None


# Стандартный разделитель ':' — хендлеры ожидают префикс "onb:"
class OnboardingCallback(CallbackData, prefix="onb"):
    # actions: start | step | next | back | skip | finish
    action: str
    step: Optional[int] = None
    value: Optional[str] = None
    page: Optional[int] = None