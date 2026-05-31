from app.domain.asset import AssetClassifier
from app.domain.position import UnifiedPosition


class AaveAdapter:
    def __init__(self):
        self.classifier = AssetClassifier()

    def transform(self, positions: list[dict]) -> list[UnifiedPosition]:
        result = []

        for p in positions:
            base = float(p.get("value_usd", 0))

            side = p.get("side")

            if side == "BORROWING":
                net = -base
                exposure = "borrowing"
            else:  # LENDING
                net = base
                exposure = "lending"

            result.append(
                UnifiedPosition(
                    position_id=p.get("position_id"),
                    protocol="aave_v3",
                    exposure_type=exposure,
                    assets=p["asset"],
                    base_value_usd=base,
                    net_value_usd=net,
                    asset_category=self.classifier.classify(p["asset"]),
                    metadata={
                        "market_id": p.get("market_id"),
                        "side": side,
                        "is_collateral": p.get("is_collateral", False),

                        "supply_apr": p.get("supply_apr", 0),
                        "borrow_apr": p.get("borrow_apr", 0),
                        "borrow_stable_apr": p.get("borrow_stable_apr", 0),

                        "max_ltv": p.get("max_ltv", 0),
                        "liquidation_threshold": p.get("liquidation_threshold", 0),
                    },
                )
            )

        return result