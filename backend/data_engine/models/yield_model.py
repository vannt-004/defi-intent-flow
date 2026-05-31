from dataclasses import dataclass
from typing import Optional, List


@dataclass(slots=True)
class YieldMarketModel:
    id: str
    protocol: str
    asset: str
    tvl: float
    supply_apr: float
    borrow_apr: float
    liquidation_threshold: float
    max_ltv: float
    can_borrow: bool
    is_active: bool


@dataclass
class LendingPosition:
    type: str
    protocol: str
    position_id: Optional[str]
    market_id: Optional[str]
    asset: List[str]
    raw_symbol: str
    balance: float
    value_usd: float
    side: str
    is_collateral: bool
    max_ltv: float
    liquidation_threshold: float
    supply_apr: float
    borrow_apr: float
    borrow_stable_apr: float

    def to_camel_dict(self):
        return {
            "type": self.type,
            "protocol": self.protocol,
            "positionId": self.position_id,
            "marketId": self.market_id,
            "asset": self.asset,
            "rawSymbol": self.raw_symbol,
            "balance": self.balance,
            "valueUsd": self.value_usd,
            "side": self.side,
            "isCollateral": self.is_collateral,
            "maxLtv": self.max_ltv,
            "liquidationThreshold": self.liquidation_threshold,
            "supplyApr": self.supply_apr,
            "borrowApr": self.borrow_apr,
            "borrowStableApr": self.borrow_stable_apr,
        }