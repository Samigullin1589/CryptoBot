# bot/utils/models.py
from __future__ import annotations

from enum import IntEnum
from typing import Any, List, Optional, Dict, Literal
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field


def parse_datetime(date_string: Optional[str]) -> int:
    """
    Безопасно парсит строку с датой в Unix timestamp.
    
    Args:
        date_string: Строка с датой в различных форматах
        
    Returns:
        int: Unix timestamp в секундах
    """
    if not date_string:
        return int(datetime.now(timezone.utc).timestamp())
    
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(date_string)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except (TypeError, ValueError, ImportError):
        pass
    
    try:
        dt = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        return int(dt.timestamp())
    except Exception:
        return int(datetime.now(timezone.utc).timestamp())


class UserRole(IntEnum):
    """Роли пользователей в системе"""
    BANNED = 0
    USER = 1
    MODERATOR = 2
    ADMIN = 3
    SUPER_ADMIN = 4


class VerificationData(BaseModel):
    """Данные верификации пользователя"""
    is_verified: bool = False
    passport_verified: bool = False
    deposit: float = 0.0
    country_code: str = "RU"


class User(BaseModel):
    """Модель пользователя"""
    id: int
    username: Optional[str] = None
    first_name: str
    language_code: Optional[str] = None
    role: UserRole = UserRole.USER
    verification_data: VerificationData = Field(default_factory=VerificationData)
    electricity_cost: float = 0.05
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )


class CalculationInput(BaseModel):
    """Входные данные для калькулятора майнинга"""
    hashrate_str: str
    power_consumption_watts: int
    electricity_cost: float
    pool_commission: float


class CalculationResult(BaseModel):
    """Результат расчета майнинга"""
    btc_price_usd: float
    usd_rub_rate: float
    gross_revenue_usd_daily: float
    electricity_cost_usd_daily: float
    pool_fee_usd_daily: float
    total_expenses_usd_daily: float
    net_profit_usd_daily: float


class Coin(BaseModel):
    """Модель криптовалюты"""
    id: str
    symbol: str
    name: str


class AsicMiner(BaseModel):
    """Модель ASIC-майнера"""
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
    """Модель новостной статьи"""
    title: str
    url: str
    source: str
    timestamp: int
    body: Optional[str] = None
    ai_summary: Optional[str] = None


class AirdropProject(BaseModel):
    """Модель airdrop-проекта"""
    id: str
    name: str
    description: str
    status: str
    tasks: List[str]
    guide_url: Optional[str] = None


class MiningProject(BaseModel):
    """Модель майнинг-проекта"""
    id: str
    name: str
    description: str
    algorithm: str
    hardware: str
    status: str


class QuizQuestion(BaseModel):
    """Модель вопроса викторины"""
    question: str
    options: List[str]
    correct_option_index: int


class MarketListing(BaseModel):
    """Модель объявления на маркетплейсе"""
    id: str
    seller_id: int
    price: float
    created_at: int
    asic_data: str


class AchievementCondition(BaseModel):
    """Условие получения достижения"""
    type: str
    event: Optional[str] = None
    threshold: Optional[int | float] = None
    counter_key: Optional[str] = None
    window_days: Optional[int] = None
    tiers: Optional[List[Dict[str, Any]]] = None


class AchievementNotify(BaseModel):
    """Настройки уведомления о достижении"""
    template_ru: str


class Achievement(BaseModel):
    """
    Модель достижения.
    Соответствует структуре achievements.yaml
    """
    id: str
    category: str
    rarity: str
    icon: str
    title: Dict[str, str]
    desc: Dict[str, str]
    points: int
    repeatable: bool = False
    condition: Optional[AchievementCondition] = None
    notify: Optional[AchievementNotify] = None
    type: str = "static"
    trigger_conditions: Optional[Dict[str, Any]] = None
    
    @property
    def name(self) -> str:
        """Алиас для title['ru'] для обратной совместимости"""
        return self.title.get('ru', self.id)
    
    @property
    def description(self) -> str:
        """Алиас для desc['ru'] для обратной совместимости"""
        return self.desc.get('ru', '')
    
    @property
    def reward_coins(self) -> int:
        """Алиас для points для обратной совместимости"""
        return self.points
    
    @property
    def trigger_event(self) -> Optional[str]:
        """Алиас для condition.event для обратной совместимости"""
        return self.condition.event if self.condition else None


class MiningSessionResult(BaseModel):
    """Результат сессии майнинга"""
    asic_name: str
    user_tariff_name: str
    gross_earned: float
    total_electricity_cost: float
    net_earned: float
    event_description: Optional[str] = None
    unlocked_achievement: Optional[Achievement] = None


class BanRecord(BaseModel):
    """Запись о бане пользователя"""
    user_id: int
    by_admin_id: int
    reason: Optional[str] = None
    created_at: datetime
    until: Optional[datetime] = None


class MuteRecord(BaseModel):
    """Запись о муте пользователя"""
    user_id: int
    by_admin_id: int
    reason: Optional[str] = None
    created_at: datetime
    until: datetime


class Verdict(BaseModel):
    """Вердикт системы безопасности"""
    ok: bool
    reasons: List[str] = Field(default_factory=list)
    weight: int = 1


class Escalation(BaseModel):
    """Эскалация нарушения"""
    count: int
    decision: Literal["ban", "mute", "warn", "none"]
    mute_seconds: int


class ImageVerdict(BaseModel):
    """Вердикт анализа изображения"""
    action: str
    reason: Optional[str] = None


class SecurityVerdict(BaseModel):
    """Вердикт системы безопасности"""
    score: float = 0.0
    action: Optional[str] = None
    reason: Optional[str] = None
    details: List[str] = []
    domains: List[str] = []


class ImageAnalysisResult(BaseModel):
    """Результат анализа изображения"""
    is_spam: bool = False
    explanation: Optional[str] = None
    extracted_text: Optional[str] = None


class ElectricityTariff(BaseModel):
    """Тариф электроэнергии"""
    name: str
    cost_per_kwh: float
    unlock_price: float


class MiningSession(BaseModel):
    """Сессия майнинга"""
    asic_json: str
    started_at: float
    ends_at: float
    tariff_json: str


class UserGameStats(BaseModel):
    """Игровая статистика пользователя"""
    sessions_total: int = 0
    spent_total: float = 0.0
    earned_total: float = 0.0


class EventItem(BaseModel):
    """Игровое событие"""
    id: str
    name: str
    description: str
    domain: str = "all"
    multiplier: float = 1.0
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    def is_active(self, now: datetime) -> bool:
        """
        Проверяет активно ли событие в указанное время.
        
        Args:
            now: Время для проверки
            
        Returns:
            bool: True если событие активно
        """
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        return True


class BTCNetworkStatus(BaseModel):
    """Статус сети Bitcoin"""
    hashrate: Optional[float] = None
    difficulty: Optional[float] = None
    block_height: Optional[int] = None
    next_difficulty_estimate: Optional[float] = None


class HalvingInfo(BaseModel):
    """Информация о халвинге Bitcoin"""
    current_block_height: Optional[int] = None
    next_halving_block: Optional[int] = None
    blocks_until_halving: Optional[int] = None
    estimated_halving_date: Optional[datetime] = None


class CoinMarketData(BaseModel):
    """Рыночные данные монеты"""
    id: str
    symbol: str
    name: str
    current_price: float
    market_cap: float
    market_cap_rank: Optional[int] = None
    price_change_percentage_24h: Optional[float] = None
    total_volume: Optional[float] = None
    circulating_supply: Optional[float] = None


class MarketOverview(BaseModel):
    """
    Полная сводка рыночных данных.
    Агрегирует данные из различных источников.
    """
    btc_price_usd: Optional[float] = None
    top_coins: List[CoinMarketData] = Field(default_factory=list)
    btc_network: Optional[BTCNetworkStatus] = None
    halving: Optional[HalvingInfo] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))