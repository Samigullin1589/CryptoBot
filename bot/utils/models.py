from typing import Optional
from pydantic import BaseModel, Field

class CryptoCoin(BaseModel):
    id: str
    symbol: str
    name: str
    price: float
    # Делаем поле опциональным и даем ему псевдоним
    price_change_24h: Optional[float] = Field(None, alias='percent_change_24h')
    algorithm: Optional[str] = None

class AsicMiner(BaseModel):
    name: str
    profitability: float
    algorithm: Optional[str] = None
    hashrate: Optional[str] = None
    power: Optional[int] = None
    source: Optional[str] = None