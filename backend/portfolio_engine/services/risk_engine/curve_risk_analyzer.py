class CurveRiskAnalyzer:
    def analyze(self, position):
        meta = position.metadata or {}

        tvl = meta.get("pool_tvl")
        exposure = position.exposure_type
        category = position.asset_category

        notes = []
        risk_level = "LOW"

        if tvl is None:
            return {
                "type": "curve_risk",
                "position_id": getattr(position, "position_id", None),
                "risk_level": "UNKNOWN",
                "notes": ["Missing TVL"]
            }

        if tvl < 1_000_000:
            risk_level = "HIGH"
            notes.append("Low TVL pool (high risk)")

        elif category == "volatile":
            risk_level = "MEDIUM"
            notes.append("Volatile asset exposure")

        if exposure == "staking" and risk_level != "HIGH":
            risk_level = "MEDIUM"
            notes.append("Staking introduces smart contract risk")

        return {
            "type": "curve_risk",
            "position_id": getattr(position, "position_id", None),
            "risk_level": risk_level,
            "notes": notes
        }