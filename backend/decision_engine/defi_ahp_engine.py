# decision_engine/defi_ahp_engine.py
import math
from typing import Dict, Any, List
from decision_engine.ahp_engine import AHPEngine


class DeFiAHPEngine:
    def __init__(self):
        self.default_matrices = {
            "safe": [
                [1.0, 1.0 / 5.0, 1.0 / 2.0], [5.0, 1.0, 3.0], [2.0, 1.0 / 3.0, 1.0]
            ], "balanced": [
                [1.0, 1.5, 2.0], [1.0 / 1.5, 1.0, 1.2], [1.0 / 2.0, 1.0 / 1.2, 1.0]
            ], "degen": [
                [1.0, 6.0, 3.0], [1.0 / 6.0, 1.0, 1.0 / 2.0], [1.0 / 3.0, 2.0, 1.0]
            ]
        }

    def rank_markets(self,
                     unified_markets: List[Dict[str, Any]],
                     profile_or_matrix: Any) -> List[Dict[str, Any]]:
        if isinstance(profile_or_matrix, dict):
            matrix = self._matrix_from_weights(profile_or_matrix)
        elif isinstance(profile_or_matrix, str):
            matrix = self.default_matrices.get(
                profile_or_matrix, self.default_matrices["balanced"]
            )
        else:
            matrix = profile_or_matrix

        consistency = AHPEngine.ensure_consistent(matrix)
        w_yield, w_safety, w_efficiency = AHPEngine.calculate_weights(matrix)
        ahp_meta = {
            "weights": {
                "yield": round(w_yield, 6),
                "safety": round(w_safety, 6),
                "efficiency": round(w_efficiency, 6),
            },
            "lambdaMax": round(consistency["lambda_max"], 6),
            "consistencyIndex": round(consistency["ci"], 6),
            "consistencyRatio": round(consistency["cr"], 6),
        }
        ranked_list = []

        for market in unified_markets:
            evaluated_pool = dict(market)
            raw = market[
                "raw_data"]
            flags = []

            category = market["category"]
            tvl = market["tvl_usd"]
            apr = market["apr"]

            s_yield = 0.0
            s_safety = 0.0
            s_efficiency = 0.0

            if tvl < 10_000.0:
                flags.append("LOW_TVL_RISK")

            if category == "dex_liquidity":
                volume_24h = float(
                    raw.get("volume_usd_24h") or raw.get("volumeUsd") or 0.0
                )

                if 8.0 <= apr <= 35.0:
                    s_yield = 100.0
                elif apr > 35.0:
                    s_yield = max(10.0, 100.0 - 0.08 * ((apr - 35.0) ** 2))
                else:
                    s_yield = (apr / 8.0) * 100.0 if apr > 0 else 0.0

                s_safety = min(100.0, 15.0 * math.log10(tvl)) if tvl > 1.0 else 0.0

                turnover = (volume_24h / tvl * 100.0) if tvl > 0 else 0.0
                evaluated_pool["capitalEfficiencyRate"] = round(turnover, 2)
                s_efficiency = 100.0 if 30.0 <= turnover <= 70.0 else (
                                                                          turnover / 30.0) * 100.0 if turnover < 30.0 else 85.0

            else:
                max_ltv = float(raw.get("maxLtv") or raw.get("maximumLTV") or 0.0)
                deposit = float(raw.get("totalDepositUsd") or tvl)
                borrow = float(raw.get("totalBorrowUsd") or 0.0)

                utilization = (borrow / deposit * 100.0) if deposit > 0 else 0.0
                evaluated_pool["utilizationRate"] = round(utilization, 2)

                if utilization > 85.0: flags.append("LIQUIDITY_CRUNCH_HAZARD")

                if 4.0 <= apr <= 12.0:
                    s_yield = 100.0
                elif apr > 12.0:
                    s_yield = max(15.0, 100.0 - 0.15 * ((apr - 12.0) ** 2))
                else:
                    s_yield = (apr / 4.0) * 100.0 if apr > 0 else 0.0

                s_safety = min(100.0, 14.5 * math.log10(tvl)) if tvl > 1.0 else 0.0

                s_ltv = 100.0 if 70.0 <= max_ltv <= 82.0 else (max_ltv / 70.0) * 100.0 if max_ltv < 70.0 else max(
                    30.0, 100.0 - 0.25 * ((max_ltv - 82.0) ** 2)
                )
                s_util = 100.0 if 55.0 <= utilization <= 80.0 else max(
                    10.0, 100.0 - 0.15 * ((utilization - 80.0) ** 2)
                ) if utilization > 80.0 else (utilization / 55.0) * 100.0
                s_efficiency = (s_ltv + s_util) / 2.0

            match_index = (s_yield * w_yield) + (s_safety * w_safety) + (
                s_efficiency * w_efficiency)

            if "LOW_TVL_RISK" in flags: match_index -= 40.0
            if "LIQUIDITY_CRUNCH_HAZARD" in flags: match_index -= 25.0
            match_index = max(0.0, min(100.0, match_index))

            evaluated_pool["ahpMatchIndex"] = round(match_index, 2)
            evaluated_pool["ahpModel"] = ahp_meta
            evaluated_pool["flags"] = flags
            evaluated_pool[
                "tier"] = "Tier A+" if match_index >= 85 else "Tier A" if match_index >= 70 else "Tier B" if match_index >= 50 else "Tier C" if match_index >= 30 else "Tier D"

            ranked_list.append(evaluated_pool)

        ranked_list.sort(key=lambda x: x["ahpMatchIndex"], reverse=True)
        return ranked_list

    def _matrix_from_weights(self, weights: Dict[str, float]) -> list[list[float]]:
        raw = [
            max(float(weights.get("yield") or 0), 0.01),
            max(float(weights.get("safety") or 0), 0.01),
            max(float(weights.get("efficiency") or 0), 0.01),
        ]
        total = sum(raw)
        normalized = [value / total for value in raw]

        return [[1.0 if i == j else normalized[i] / normalized[j] for j in range(3)] for
            i in range(3)]
