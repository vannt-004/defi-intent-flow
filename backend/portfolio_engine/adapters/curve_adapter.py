from app.domain.asset import AssetClassifier
from app.domain.position import UnifiedPosition


class CurveAdapter:
    def __init__(self):
        self.classifier = AssetClassifier()

    def transform(self, positions):
        result = []

        for p in positions:
            exposure = "staking" if p["type"] == "gauge" else "lp_provider"

            result.append(
                UnifiedPosition(
                    position_id=p.get("position_id"),
                    protocol="curve",
                    exposure_type=exposure,
                    assets=p["asset"],
                    base_value_usd=p["value_usd"],
                    net_value_usd=p["value_usd"],
                    asset_category=self.classifier.classify(p["asset"]),
                    metadata={
                        "pool": p.get("pool"),
                        "pool_tvl": p.get("pool_tvl"),
                        "type": p.get("type"),
                    },
                )
            )

        return result