# utils/models.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class AsicMiner:
    name: str
    profitability: float
    algorithm: Optional[str] = None
    hashrate: Optional[str] = None
    power: Optional[int] = None
    source: Optional[str] = None

@dataclass
class CryptoCoin:
    id: str
    symbol: str
    name: str
    price: float
    algorithm: Optional[str] = None
    price_change_24h: Optional[float] = None