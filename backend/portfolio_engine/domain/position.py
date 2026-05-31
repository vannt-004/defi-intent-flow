class UnifiedPosition:
    def __init__(
        self,
        protocol: str,
        position_id: str,
        exposure_type: str,
        assets: list[str],
        base_value_usd: float,
        net_value_usd: float,
        deposited_usd: float = 0.0,
        withdrawn_usd: float = 0.0,
        fee_earned_usd: float = 0.0,
        asset_category: str = None,
        metadata: dict = None,
    ):
        self.protocol = protocol
        self.position_id = position_id
        self.exposure_type = exposure_type
        self.assets = assets
        self.base_value_usd = base_value_usd
        self.net_value_usd = net_value_usd
        self.deposited_usd = deposited_usd
        self.withdrawn_usd = withdrawn_usd
        self.fee_earned_usd = fee_earned_usd
        self.asset_category = asset_category
        self.metadata = metadata or {}

    def to_dict(self):
        return {
            "protocol": self.protocol,
            "positionId": self.position_id,
            "exposureType": self.exposure_type,
            "assets": self.assets,
            "baseValueUsd": self.base_value_usd,
            "netValueUsd": self.net_value_usd,
            "depositedUsd": self.deposited_usd,
            "withdrawnUsd": self.withdrawn_usd,
            "feeEarnedUsd": self.fee_earned_usd,
            "assetCategory": self.asset_category,
            "metadata": self.metadata,
        }


class AavePortfolioSummary:
    positionCount: int
    totalSupplyUsd: float
    totalBorrowUsd: float
    netWorthUsd: float
    collateralUsd: float
    healthFactor: float