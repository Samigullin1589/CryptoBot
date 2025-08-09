# =================================================================================
# Файл: bot/utils/models.py (ФИНАЛЬНАЯ ВЕРСИЯ С ИГРОВОЙ МОДЕЛЬЮ, АВГУСТ 2025)
# Описание: Полный набор Pydantic-моделей для всего проекта.
# ИЗМЕНЕНИЕ: Добавлена недостающая модель UserGameProfile.
# =================================================================================

from __future__ import annotations
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field, ConfigDict
from enum import IntEnum

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
    country_code: str = "🇷🇺"

# --- НОВАЯ МОДЕЛЬ ДЛЯ ИГРОВЫХ ДАННЫХ ---
class UserGameProfile(BaseModel):
    balance: float = 0.0
    total_earned: float = 0.0
    current_tariff: str
    owned_tariffs: List[str]

# --- ЦЕНТРАЛЬНАЯ МОДЕЛЬ ПОЛЬЗОВАТЕЛЯ ---
class User(BaseModel):
    id: int = Field(alias="user_id")
    username: Optional[str] = None
    first_name: str = Field(alias="full_name")
    language_code: Optional[str] = None
    role: UserRole = UserRole.USER
    verification_data: VerificationData = Field(default_factory=VerificationData)

    model_config = ConfigDict(
        populate_by_name=True
    )

# --- Остальные модели вашего проекта ---

class Coin(BaseModel):
    id: str
    symbol: str
    name: str

class PriceInfo(BaseModel):
    price: float
    market_cap: Optional[float] = None
    volume_24h: Optional[float] = None
    change_24h: Optional[float] = None

class MiningEvent(BaseModel):
    name: str
    description: str
    probability: float = Field(ge=0.0, le=1.0)
    profit_multiplier: float = 1.0
    cost_multiplier: float = 1.0

class AsicMiner(BaseModel):
    id: str
    name: str
    hashrate: str
    power: int
    algorithm: str
    profitability: Optional[float] = None
    price: Optional[float] = None

class NewsArticle(BaseModel):
    title: str
    url: str
    body: Optional[str] = None
    source: str
    timestamp: Optional[int] = None
    published_at: Optional[str] = None
    ai_summary: Optional[str] = None

class AirdropProject(BaseModel):
    id: str
    name: str
    description: str
    status: str
    tasks: List[str]
    guide_url: Optional[str] = None

class Achievement(BaseModel):
    id: str
    name: str
    description: str
    reward_coins: float
    trigger_event: str
    type: str = "static"
    trigger_conditions: Optional[Dict[str, Any]] = None

class MiningSessionResult(BaseModel):
    asic_name: str
    user_tariff_name: str
    gross_earned: float
    total_electricity_cost: float
    net_earned: float
    event_description: Optional[str] = None
    unlocked_achievement: Optional[Achievement] = None

class MarketListing(BaseModel):
    id: str
    seller_id: int
    price: float
    created_at: int
    asic_data: str

class QuizQuestion(BaseModel):
    question: str
    options: List[str]
    correct_option_index: int
    explanation: Optional[str] = None

class AIVerdict(BaseModel):
    intent: str = "other"
    toxicity_score: float = 0.0
    is_potential_scam: bool = False
    is_potential_phishing: bool = False
