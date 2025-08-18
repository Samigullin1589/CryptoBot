from __future__ import annotations

from enum import IntEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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


# --- МОДЕЛЬ ИГРОВОГО ПРОФИЛЯ ---
class UserGameProfile(BaseModel):
    balance: float = 0.0
    total_earned: float = 0.0
    current_tariff: str
    owned_tariffs: list[str]


# --- ЦЕНТРАЛЬНАЯ МОДЕЛЬ ПОЛЬЗОВАТЕЛЯ ---
class User(BaseModel):
    id: int = Field(alias="user_id")
    username: str | None = None
    first_name: str = Field(alias="full_name")
    language_code: str | None = None
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
    network_hashrate_ths: float
    block_reward_btc: float
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


class PriceInfo(BaseModel):
    price: float
    market_cap: float | None = None
    volume_24h: float | None = None
    change_24h: float | None = None


class MiningEvent(BaseModel):
    name: str
    description: str
    probability: float = Field(ge=0.0, le=1.0)
    profit_multiplier: float = 1.0
    cost_multiplier: float = 1.0


class AsicMiner(BaseModel):
    id: str
    name: str
    vendor: str | None = "Unknown"
    hashrate: str
    power: int
    algorithm: str
    profitability: float | None = None
    price: float | None = None
    net_profit: float | None = None
    gross_profit: float | None = None
    electricity_cost_per_day: float | None = None


class NewsArticle(BaseModel):
    title: str
    url: str
    body: str | None = None
    source: str | None = None
    timestamp: int | None = None
    published_at: str | None = None
    ai_summary: str | None = None


class AirdropProject(BaseModel):
    id: str
    name: str
    description: str
    status: str
    tasks: list[str]
    guide_url: str | None = None


class Achievement(BaseModel):
    id: str
    name: str
    description: str
    reward_coins: float
    trigger_event: str
    type: str = "static"
    trigger_conditions: dict[str, Any] | None = None


class MiningSessionResult(BaseModel):
    asic_name: str
    user_tariff_name: str
    gross_earned: float
    total_electricity_cost: float
    net_earned: float
    event_description: str | None = None
    unlocked_achievement: Achievement | None = None


class MarketListing(BaseModel):
    id: str
    seller_id: int
    price: float
    created_at: int
    asic_data: str


class QuizQuestion(BaseModel):
    question: str
    options: list[str]
    correct_option_index: int
    explanation: str | None = None


# --- ВЕРДИКТ ДЛЯ ФИЛЬТРА УГРОЗ ---
class AIVerdict(BaseModel):
    intent: str = "other"
    toxicity_score: float = 0.0
    is_potential_scam: bool = False
    is_potential_phishing: bool = False
    # Для ThreatFilter и логирования:
    score: float = 0.0
    reasons: list[str] = Field(default_factory=list)
