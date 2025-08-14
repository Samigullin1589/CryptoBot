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


# Админские фабрики: только здесь используем нестандартный разделитель,
# т.к. в action встречаются значения с ':' (например, "stats:general").
class AdminCallback(CallbackData, prefix="admin", sep="|"):
    action: str
    value: Optional[str] = None
    section: Optional[str] = None
    page: Optional[int] = None


# Вернули стандартный разделитель ':' — многие обработчики матчат по "adgame:"
class GameAdminCallback(CallbackData, prefix="adgame"):
    action: str
    value: Optional[str] = None
    page: Optional[int] = None


class ThreatCallback(CallbackData, prefix="threat"):
    action: str  # ban | pardon | ignore
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
    coin_id: Optional[str] = None  # используется в price_handler.show_price_for_coin


# Вернули стандартный разделитель ':' — хендлеры ожидают префикс "asic:"
class AsicCallback(CallbackData, prefix="asic"):
    action: str
    value: Optional[str] = None
    asic_id: Optional[str] = None
    page: Optional[int] = None
    sort: Optional[str] = None
    vendor: Optional[str] = None


class NewsCallback(CallbackData, prefix="news"):
    action: str  # source | category | page | open | refresh
    source: Optional[str] = None
    category: Optional[str] = None
    value: Optional[str] = None
    page: Optional[int] = None


class QuizCallback(CallbackData, prefix="quiz"):
    action: str  # start | answer | next | hint | results | page
    value: Optional[str] = None
    quiz_id: Optional[str] = None
    question_id: Optional[str] = None
    answer_id: Optional[str] = None
    page: Optional[int] = None


# Вернули стандартный разделитель ':' — хендлеры ожидают префикс "market:"
class MarketCallback(CallbackData, prefix="market"):
    action: str  # list | view | page | buy | filter | sort | vendor | back
    value: Optional[str] = None
    item_id: Optional[str] = None
    page: Optional[int] = None
    sort: Optional[str] = None
    vendor: Optional[str] = None
    q: Optional[str] = None


# Вернули стандартный разделитель ':' — хендлеры ожидают префикс "crypto:"
class CryptoCenterCallback(CallbackData, prefix="crypto"):
    action: str  # open | section | page | refresh | back
    value: Optional[str] = None
    section: Optional[str] = None
    page: Optional[int] = None
    q: Optional[str] = None


# Вернули стандартный разделитель ':' — хендлеры ожидают префикс "onb:"
class OnboardingCallback(CallbackData, prefix="onb"):
    action: str  # start | step | next | back | skip | finish
    step: Optional[int] = None
    value: Optional[str] = None
    page: Optional[int] = None