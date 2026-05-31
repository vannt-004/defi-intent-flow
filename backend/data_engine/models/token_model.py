from dataclasses import dataclass
from typing import Optional


@dataclass
class TokenModel:
    symbol: str
    name: str
    coingecko_id: str
    price: Optional[float] = None
    image: Optional[str] = None
    address: Optional[str] = None
    decimals: Optional[int] = None
    is_stablecoin: bool = False


@dataclass
class PriceSnapshotModel:
    coingecko_id: str
    price: float
    timestamp: int