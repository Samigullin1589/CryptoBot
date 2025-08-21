# =============================================================================
# Файл: bot/keyboards/callback_factories.py
# Версия: "Distinguished Engineer" — ПРОДАКШН-СБОРКА (Aug 21, 2025)
# Описание: Единые, строго типизированные фабрики CallbackData для всех модулей.
# Устранена избыточность и неоднозначность полей.
# =============================================================================

from typing import Optional
from aiogram.filters.callback_data import CallbackData

class MenuCallback(CallbackData, prefix="menu"):
    action: str

class GameCallback(CallbackData, prefix="game"):
    action: str
    value: Optional[str] = None
    page: Optional[int] = None

class CalculatorCallback(CallbackData, prefix="calc"):
    action: str
    value: Optional[str] = None
    asic_index: Optional[int] = None
    page: Optional[int] = None

class AdminCallback(CallbackData, prefix="admin", sep="|"):
    action: str

class GameAdminCallback(CallbackData, prefix="adgame"):
    action: str

class ThreatCallback(CallbackData, prefix="threat"):
    action: str
    user_id: int
    chat_id: int

class PriceCallback(CallbackData, prefix="price"):
    action: str
    coin_id: str

class AsicCallback(CallbackData, prefix="asic"):
    action: str
    asic_id: Optional[str] = None
    page: Optional[int] = None

class NewsCallback(CallbackData, prefix="news"):
    action: str
    source_key: Optional[str] = None

class QuizCallback(CallbackData, prefix="quiz"):
    action: str
    is_correct: int

class MarketCallback(CallbackData, prefix="market"):
    action: str
    listing_id: Optional[str] = None
    asic_id: Optional[str] = None
    page: Optional[int] = None

class CryptoCenterCallback(CallbackData, prefix="crypto_center"):
    action: str
    project_id: Optional[str] = None
    task_index: Optional[int] = None
    page: Optional[int] = 0

class OnboardingCallback(CallbackData, prefix="onb"):
    action: str