# =================================================================================
# Файл: bot/utils/models.py (ФИНАЛЬНАЯ ИНТЕГРИРОВАННАЯ ВЕРСИЯ, АВГУСТ 2025)
# Описание: Полный и самодостаточный набор Pydantic-моделей для всего проекта,
# объединяющий профиль, верификацию и систему ролей в единой модели User.
# =================================================================================

from __future__ import annotations
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field, ConfigDict
from enum import IntEnum

# --- ИЕРАРХИЯ РОЛЕЙ ---
# Определена здесь, чтобы избежать циклических импортов
class UserRole(IntEnum):
    """Определяет роли пользователей с иерархией для сравнения."""
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

# --- ЦЕНТРАЛЬНАЯ МОДЕЛЬ ПОЛЬЗОВАТЕЛЯ ---
class User(BaseModel):
    """
    Центральная модель пользователя, объединяющая профиль Telegram,
    роль и данные о верификации. Сохраняет обратную совместимость через alias'ы.
    """
    id: int = Field(alias="user_id")
    username: Optional[str] = None
    first_name: str = Field(alias="full_name") # Имя в вашей системе
    language_code: Optional[str] = None
    
    # ИНТЕГРАЦИЯ: Роль является неотъемлемой частью данных пользователя
    role: UserRole = UserRole.USER
    
    # Встраиваем данные о верификации прямо в модель пользователя
    verification_data: VerificationData = Field(default_factory=VerificationData)

    model_config = ConfigDict(
        populate_by_name=True # Разрешаем Pydantic использовать alias'ы
    )

# --- Остальные модели вашего проекта ---

class Coin(BaseModel):
    id: str = Field(description="Уникальный идентификатор CoinGecko (например, 'bitcoin')")
    symbol: str = Field(description="Тикер монеты (например, 'btc')")
    name: str = Field(description="Полное название монеты (например, 'Bitcoin')")

class PriceInfo(BaseModel):
    price: float
    market_cap: Optional[float] = None
    volume_24h: Optional[float] = None
    change_24h: Optional[float] = None

class MiningEvent(BaseModel):
    name: str = Field(description="Название события")
    description: str = Field(description="Описание события для пользователя")
    probability: float = Field(ge=0.0, le=1.0, description="Вероятность возникновения (0.0-1.0)")
    profit_multiplier: float = Field(default=1.0, description="Множитель дохода (напр., 1.5 для +50%)")
    cost_multiplier: float = Field(default=1.0, description="Множитель затрат (напр., 0.5 для -50%)")

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
    intent: str = Field(default="other", description="Основное намерение сообщения.")
    toxicity_score: float = Field(default=0.0, description="Оценка токсичности от 0.0 до 1.0.")
    is_potential_scam: bool = Field(default=False, description="True, если сообщение похоже на мошенничество.")
    is_potential_phishing: bool = Field(default=False, description="True, если сообщение содержит подозрительные ссылки.")
