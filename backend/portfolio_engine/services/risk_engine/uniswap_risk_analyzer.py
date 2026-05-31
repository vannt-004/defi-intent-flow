class UniswapRiskAnalyzer:

    def analyze(self, position):
        md = position.metadata

        tick_lower = md.get("tick_lower")
        tick_upper = md.get("tick_upper")
        current_price = md.get("current_price")

        if tick_lower is None or tick_upper is None or current_price is None:
            return self._unknown(position)

        in_range = tick_lower <= current_price <= tick_upper

        range_width = tick_upper - tick_lower
        mid_price = (tick_lower + tick_upper) / 2

        price_deviation = abs(current_price - mid_price) / mid_price if mid_price else 0

        risk_level = self._classify_risk(in_range, range_width, price_deviation)

        return {
            "type": "uniswap_risk",
            "position_id": position.position_id,
            "in_range": in_range,
            "range_width": range_width,
            "price_deviation": round(price_deviation, 4),
            "risk_level": risk_level,
            "notes": self._build_notes(in_range, range_width, price_deviation),
        }

    def _classify_risk(self, in_range, range_width, deviation):
        if not in_range:
            return "HIGH"

        if range_width < 100:
            return "HIGH"

        if deviation > 0.3:
            return "MEDIUM"

        return "LOW"

    def _build_notes(self, in_range, range_width, deviation):
        notes = []

        if not in_range:
            notes.append("Position is out of range → no fee earning")

        if range_width < 100:
            notes.append("Very narrow range → high concentration risk")

        if deviation > 0.3:
            notes.append("Price far from center → IL risk increasing")

        return notes

    def _unknown(self, position):
        return {
            "type": "uniswap_risk",
            "position_id": position.position_id,
            "risk_level": "UNKNOWN",
            "notes": ["Missing required metadata"]
        }