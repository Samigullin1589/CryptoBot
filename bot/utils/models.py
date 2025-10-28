# =================================================================================
# Файл: bot/utils/models.py (ВЕРСИЯ "Distinguished Engineer" - ИСПРАВЛЕННАЯ)
# Описание: Централизованное хранилище Pydantic-моделей.
# ИСПРАВЛЕНИЕ: Achievement модель теперь соответствует конфигу achievements.yaml
# =================================================================================
from __future__ import annotations

from enum import IntEnum
from typing import Any, List, Optional, Dict, Literal
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

from pydantic import BaseModel, ConfigDict, Field

def parse_datetime(date_string: Optional[str]) -> int:
    """Безопасно парсит строку с датой в Unix timestamp."""
    if not date_string:
        return int(datetime.now(timezone.utc).timestamp())
    try:
        dt = parsedate_to_datetime(date_string)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except (TypeError, ValueError):
        try:
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
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

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
    id: Optional[str] = None

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
    asic_data: str


# ═══════════════════════════════════════════════════════════════
# ✅ ИСПРАВЛЕННАЯ МОДЕЛЬ ACHIEVEMENT
# Теперь соответствует структуре achievements.yaml
# ═══════════════════════════════════════════════════════════════

class AchievementCondition(BaseModel):
    """Условие получения достижения"""
    type: str  # 'counter', 'streak', 'tiered', etc.
    event: Optional[str] = None
    threshold: Optional[int] = None
    counter_key: Optional[str] = None
    window_days: Optional[int] = None
    tiers: Optional[List[Dict[str, Any]]] = None


class AchievementNotify(BaseModel):
    """Настройки уведомления о достижении"""
    template_ru: str


class Achievement(BaseModel):
    """
    Модель достижения
    ✅ ИСПРАВЛЕНО: Поля соответствуют конфигу achievements.yaml
    """
    id: str
    category: str
    rarity: str
    icon: str
    
    # ✅ ИСПРАВЛЕНО: title вместо name
    title: Dict[str, str]  # {'ru': 'Название'}
    
    # ✅ ИСПРАВЛЕНО: desc вместо description
    desc: Dict[str, str]  # {'ru': 'Описание'}
    
    # ✅ ИСПРАВЛЕНО: points вместо reward_coins
    points: int
    
    repeatable: bool = False
    
    # ✅ ИСПРАВЛЕНО: condition объект вместо trigger_event строки
    condition: Optional[AchievementCondition] = None
    
    notify: Optional[AchievementNotify] = None
    
    # ✅ Добавлены свойства для обратной совместимости со старым кодом
    @property
    def name(self) -> str:
        """Алиас для title['ru'] - для обратной совместимости"""
        return self.title.get('ru', self.id)
    
    @property
    def description(self) -> str:
        """Алиас для desc['ru'] - для обратной совместимости"""
        return self.desc.get('ru', '')
    
    @property
    def reward_coins(self) -> int:
        """Алиас для points - для обратной совместимости"""
        return self.points
    
    @property
    def trigger_event(self) -> Optional[str]:
        """Алиас для condition.event - для обратной совместимости"""
        return self.condition.event if self.condition else None
    
    # Старое поле type для совместимости
    type: str = "static"
    
    # Старое поле trigger_conditions для совместимости
    trigger_conditions: Optional[Dict[str, Any]] = None


# ═══════════════════════════════════════════════════════════════
# ОСТАЛЬНЫЕ МОДЕЛИ (БЕЗ ИЗМЕНЕНИЙ)
# ═══════════════════════════════════════════════════════════════

class MiningSessionResult(BaseModel):
    asic_name: str
    user_tariff_name: str
    gross_earned: float
    total_electricity_cost: float
    net_earned: float
    event_description: Optional[str] = None
    unlocked_achievement: Optional[Achievement] = None

# --- МОДЕЛИ МОДЕРАЦИИ ---
class BanRecord(BaseModel):
    user_id: int
    by_admin_id: int
    reason: Optional[str] = None
    created_at: datetime
    until: Optional[datetime] = None

class MuteRecord(BaseModel):
    user_id: int
    by_admin_id: int
    reason: Optional[str] = None
    created_at: datetime
    until: datetime

# --- МОДЕЛИ ДЛЯ СИСТЕМЫ БЕЗОПАСНОСТИ ---
class Verdict(BaseModel):
    ok: bool
    reasons: List[str] = Field(default_factory=list)
    weight: int = 1

class Escalation(BaseModel):
    count: int
    decision: Literal["ban", "mute", "warn", "none"]
    mute_seconds: int

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

class UserGameStats(BaseModel):
    sessions_total: int = 0
    spent_total: float = 0.0
    earned_total: float = 0.0

class EventItem(BaseModel):
    id: str
    name: str
    description: str
    domain: str = "all"
    multiplier: float = 1.0
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    def is_active(self, now: datetime) -> bool:
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        return True