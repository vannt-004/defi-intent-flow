from portfolio_engine.domain.asset import AssetClassifier
from portfolio_engine.domain.position import UnifiedPosition


class UniswapAdapter:
    def __init__(self):
        self.classifier = AssetClassifier()

    def transform(self, positions):
        result = []

        for p in positions:
            token0, token1 = p["asset"]

            deposited_usd = self._calc_usd(
                p["deposited_token0"],
                p["deposited_token1"],
                p
            )

            withdrawn_usd = self._calc_usd(
                p["withdrawn_token0"],
                p["withdrawn_token1"],
                p
            )

            result.append(
                UnifiedPosition(
                    protocol="uniswap_v3",
                    position_id=p["position_id"],

                    exposure_type="LP_PROVIDER",
                    assets=[token0, token1],

                    base_value_usd=p["value_usd"],
                    net_value_usd=p["value_usd"],

                    deposited_usd=deposited_usd,
                    withdrawn_usd=withdrawn_usd,
                    fee_earned_usd=p["collected_fee_usd"],

                    asset_category=self.classifier.classify([token0, token1]),

                    metadata={
                        "amount0": p["amount0"],
                        "amount1": p["amount1"],

                        "tick_lower": p["tick_lower"],
                        "tick_upper": p["tick_upper"],
                        "fee_tier": p["fee_tier"],

                        # nếu có thì thêm
                        "current_price": p.get("token0_price") # fix
                        # "entry_price": ...
                    },
                )
            )

        return result

    def _calc_usd(self, amount0, amount1, p):
        token0, token1 = p["asset"]

        price0 = p.get("price0", 0)
        price1 = p.get("price1", 0)

        return amount0 * price0 + amount1 * price1