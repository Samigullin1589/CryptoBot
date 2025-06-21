from typing import Optional
from pydantic import BaseModel

class CryptoCoin(BaseModel):
    id: str
    symbol: str
    name: str
    price: float
    price_change_24h: Optional[float] = None
    algorithm: Optional[str] = None

class AsicMiner(BaseModel):
    name: str
    profitability: float
    algorithm: Optional[str] = None
    hashrate: Optional[str] = None
    power: Optional[int] = None
    source: Optional[str] = None