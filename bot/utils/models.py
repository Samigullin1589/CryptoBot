\==============================
Файл: bot/utils/models.py
ВЕРСИЯ: "Distinguished Engineer" — Август 2025 (Азия/Тбилиси)
Кратко: Удалён артефакт "====" в начале файла. Шапка переведена в комментарии, чтобы при вставке не было SyntaxError. В AIVerdict добавлены поля score и reasons для ThreatFilter. Остальные интерфейсы без изменений.

# ==============================

# Файл: bot/utils/models.py  — "Distinguished Engineer", Август 2025 (Азия/Тбилиси)

# Кратко: Полный набор моделей. Безопасная шапка (как комментарии).

# Исправления: добавлен vendor в AsicMiner; добавлены score и reasons в AIVerdict.

# ==============================

from **future** import annotations

from enum import IntEnum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

# --- ИЕРАРХИЯ РОЛЕЙ ---

class UserRole(IntEnum):
BANNED = 0
USER = 1
MODERATOR = 2
ADMIN = 3
SUPER\_ADMIN = 4

# --- ВЕРИФИКАЦИЯ ---

class VerificationData(BaseModel):
is\_verified: bool = False
passport\_verified: bool = False
deposit: float = 0.0
country\_code: str = "🇷🇺"

# --- ИГРОВАЯ МОДЕЛЬ ---

class UserGameProfile(BaseModel):
balance: float = 0.0
total\_earned: float = 0.0
current\_tariff: str
owned\_tariffs: List\[str]

# --- ЦЕНТРАЛЬНАЯ МОДЕЛЬ ПОЛЬЗОВАТЕЛЯ ---

class User(BaseModel):
id: int = Field(alias="user\_id")
username: Optional\[str] = None
first\_name: str = Field(alias="full\_name")
language\_code: Optional\[str] = None
role: UserRole = UserRole.USER
verification\_data: VerificationData = Field(default\_factory=VerificationData)
electricity\_cost: float = 0.05

```
model_config = ConfigDict(
    populate_by_name=True,
    arbitrary_types_allowed=True,
)
```

# --- КАЛЬКУЛЯТОР ---

class CalculationInput(BaseModel):
hashrate\_str: str
power\_consumption\_watts: int
electricity\_cost: float
pool\_commission: float

class CalculationResult(BaseModel):
btc\_price\_usd: float
usd\_rub\_rate: float
network\_hashrate\_ths: float
block\_reward\_btc: float
gross\_revenue\_usd\_daily: float
electricity\_cost\_usd\_daily: float
pool\_fee\_usd\_daily: float
total\_expenses\_usd\_daily: float
net\_profit\_usd\_daily: float

# --- ПРОЧИЕ МОДЕЛИ ---

class Coin(BaseModel):
id: str
symbol: str
name: str

class PriceInfo(BaseModel):
price: float
market\_cap: Optional\[float] = None
volume\_24h: Optional\[float] = None
change\_24h: Optional\[float] = None

class MiningEvent(BaseModel):
name: str
description: str
probability: float = Field(ge=0.0, le=1.0)
profit\_multiplier: float = 1.0
cost\_multiplier: float = 1.0

class AsicMiner(BaseModel):
id: str
name: str
vendor: Optional\[str] = "Unknown"
hashrate: str
power: int
algorithm: str
profitability: Optional\[float] = None
price: Optional\[float] = None
net\_profit: Optional\[float] = None
gross\_profit: Optional\[float] = None
electricity\_cost\_per\_day: Optional\[float] = None

class NewsArticle(BaseModel):
title: str
url: str
body: Optional\[str] = None
source: Optional\[str] = None
timestamp: Optional\[int] = None
published\_at: Optional\[str] = None
ai\_summary: Optional\[str] = None

class AirdropProject(BaseModel):
id: str
name: str
description: str
status: str
tasks: List\[str]
guide\_url: Optional\[str] = None

class Achievement(BaseModel):
id: str
name: str
description: str
reward\_coins: float
trigger\_event: str
type: str = "static"
trigger\_conditions: Optional\[Dict\[str, Any]] = None

class MiningSessionResult(BaseModel):
asic\_name: str
user\_tariff\_name: str
gross\_earned: float
total\_electricity\_cost: float
net\_earned: float
event\_description: Optional\[str] = None
unlocked\_achievement: Optional\[Achievement] = None

class MarketListing(BaseModel):
id: str
seller\_id: int
price: float
created\_at: int
asic\_data: str

class QuizQuestion(BaseModel):
question: str
options: List\[str]
correct\_option\_index: int
explanation: Optional\[str] = None

# --- ВЕРДИКТ ДЛЯ ФИЛЬТРА УГРОЗ ---

class AIVerdict(BaseModel):
intent: str = "other"
toxicity\_score: float = 0.0
is\_potential\_scam: bool = False
is\_potential\_phishing: bool = False
\# Для ThreatFilter и логирования:
score: float = 0.0
reasons: List\[str] = Field(default\_factory=list)