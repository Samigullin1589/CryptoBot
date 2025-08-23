# =================================================================================
# Файл: bot/utils/models.py (ВЕРСИЯ "Distinguished Engineer" - ИСПРАВЛЕННАЯ)
# Описание: Централизованное хранилище Pydantic-моделей.
# ИСПРАВЛЕНИЕ: Добавлена недостающая функция parse_datetime.
# =================================================================================
from __future__ import annotations

from enum import IntEnum
from typing import Any, List, Optional
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from pydantic import BaseModel, ConfigDict, Field

# --- ИСПРАВЛЕНО: Добавлена недостающая функция ---
def parse_datetime(date_string: Optional[str]) -> int:
    """Безопасно парсит строку с датой в Unix timestamp."""
    if not date_string:
        return int(datetime.now(timezone.utc).timestamp())
    try:
        # Пытаемся обработать стандартные форматы (RFC 2822, ISO 8601)
        dt = parsedate_to_datetime(date_string)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except (TypeError, ValueError):
        try:
            # Фолбэк для форматов типа '2025-08-23T12:00:00Z'
            dt = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
            return int(dt.timestamp())
        except Exception:
            return int(datetime.now(timezone.utc).timestamp())

# --- ИЕРАРХИЯ РОЛЕЙ ---
class UserRole(IntEnum):
    BANNED = 0
    USER = 1
    MODERATOR = 2
    ADMIN = 3
    SUPER_ADMIN = 4

# --- МОДЕЛЬ ВЕРИФИКАЦИИ ---
class VerificationData(BaseModel):
    is_verified: bool = False
    passport_verified: bool = False
    deposit: float = 0.0
    country_code: str = "RU"

# --- ЦЕНТРАЛЬНАЯ МОДЕЛЬ ПОЛЬЗОВАТЕЛЯ ---
class User(BaseModel):
    id: int
    username: Optional[str] = None
    first_name: str
    language_code: Optional[str] = None
    role: UserRole = UserRole.USER
    verification_data: VerificationData = Field(default_factory=VerificationData)
    electricity_cost: float = 0.05
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

# --- КАЛЬКУЛЯТОР ---
class CalculationInput(BaseModel):
    hashrate_str: str
    power_consumption_watts: int
    electricity_cost: float
    pool_commission: float

class CalculationResult(BaseModel):
    btc_price_usd: float
    usd_rub_rate: float
    gross_revenue_usd_daily: float
    electricity_cost_usd_daily: float
    pool_fee_usd_daily: float
    total_expenses_usd_daily: float
    net_profit_usd_daily: float

# --- ПРОЧИЕ МОДЕЛИ ---
class Coin(BaseModel):
    id: str
    symbol: str
    name: str

class AsicMiner(BaseModel):
    name: str
    hashrate: str
    power: int
    algorithm: Optional[str] = None
    profitability: Optional[float] = None
    price: Optional[float] = None
    net_profit: Optional[float] = None
    gross_profit: Optional[float] = None
    electricity_cost_per_day: Optional[float] = None
    id: Optional[str] = None # Для совместимости с данными из ангара
    
class NewsArticle(BaseModel):
    title: str
    url: str
    source: str
    timestamp: int
    body: Optional[str] = None
    ai_summary: Optional[str] = None

class AirdropProject(BaseModel):
    id: str
    name: str
    description: str
    status: str
    tasks: List[str]
    guide_url: Optional[str] = None
    
class MiningProject(BaseModel):
    id: str
    name: str
    description: str
    algorithm: str
    hardware: str
    status: str

class QuizQuestion(BaseModel):
    question: str
    options: List[str]
    correct_option_index: int

class MarketListing(BaseModel):
    id: str
    seller_id: int
    price: float
    created_at: int
    asic_data: str # JSON-строка с данными AsicMiner

# --- МОДЕЛИ ДЛЯ СИСТЕМЫ БЕЗОПАСНОСТИ ---
class ImageVerdict(BaseModel):
    action: str
    reason: Optional[str] = None
    
class SecurityVerdict(BaseModel):
    score: float = 0.0
    action: Optional[str] = None
    reason: Optional[str] = None
    details: List[str] = []
    domains: List[str] = []

class ImageAnalysisResult(BaseModel):
    is_spam: bool = False
    explanation: Optional[str] = None
    extracted_text: Optional[str] = None
    
# --- МОДЕЛИ ДЛЯ ИГРЫ ---
class ElectricityTariff(BaseModel):
    name: str
    cost_per_kwh: float
    unlock_price: float

class MiningSession(BaseModel):
    asic_json: str
    started_at: float
    ends_at: float
    tariff_json: str