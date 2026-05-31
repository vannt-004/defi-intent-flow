class AaveRiskAnalyzer:

    def analyze(self, aave_summary):
        if not aave_summary:
            return None

        hf = aave_summary.get("health_factor")

        if hf is None:
            return None

        if hf > 1.5:
            level = "SAFE"
        elif hf > 1.1:
            level = "WARNING"
        else:
            level = "DANGER"

        return {
            "type": "aave_risk",
            "health_factor": hf,
            "risk_level": level,
        }