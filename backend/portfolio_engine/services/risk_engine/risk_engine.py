from portfolio_engine.services.risk_engine.aave_risk_analyzer import AaveRiskAnalyzer
from portfolio_engine.services.risk_engine.curve_risk_analyzer import CurveRiskAnalyzer
from portfolio_engine.services.risk_engine.uniswap_risk_analyzer import UniswapRiskAnalyzer


class RiskEngine:
    def __init__(self):
        self.uniswap = UniswapRiskAnalyzer()
        self.aave = AaveRiskAnalyzer()
        self.curve = CurveRiskAnalyzer()

    def analyze(self, positions, aave_summary=None):
        position_risks = []

        for p in positions:
            if p.protocol == "uniswap_v3":
                position_risks.append(self.uniswap.analyze(p))

            elif p.protocol == "curve":
                position_risks.append(self.curve.analyze(p))

            else:
                position_risks.append({
                    "type": "unknown",
                    "position_id": getattr(p, "position_id", None),
                    "risk_level": "LOW"
                })

        aave_risk = self.aave.analyze(aave_summary)

        return {
            "positions": position_risks,
            "aave": aave_risk,
            "portfolio": self._aggregate(position_risks, positions)
        }

    def _aggregate(self, risks, positions):
        if not positions:
            return {
                "high_risk_ratio": 0,
                "risk_level": "LOW"
            }

        total_value = sum(abs(p.net_value_usd or 0) for p in positions)

        high_risk_value = 0

        for i in range(min(len(positions), len(risks))):
            p = positions[i]
            r = risks[i]

            if r.get("risk_level") == "HIGH":
                high_risk_value += abs(p.net_value_usd or 0)

        ratio = high_risk_value / total_value if total_value else 0

        if ratio > 0.5:
            level = "HIGH"
        elif ratio > 0.2:
            level = "MEDIUM"
        else:
            level = "LOW"

        return {
            "high_risk_ratio": round(ratio, 4),
            "risk_level": level
        }