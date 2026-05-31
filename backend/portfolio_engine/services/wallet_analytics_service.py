import math
from collections import defaultdict


class WalletAnalyticsService:

    # =========================================================
    # BASIC METRICS
    # =========================================================

    def calculate_asset_allocation(
        self,
        assets: list[dict]
    ):

        total = sum(
            (a.get("value_usd") or 0)
            for a in assets
        )

        grouped = {}

        for asset in assets:

            symbol = asset.get("symbol")

            value = asset.get("value_usd") or 0

            if symbol not in grouped:

                grouped[symbol] = {
                    "symbol": symbol,
                    "name": asset.get("name"),
                    "image": asset.get("image"),

                    "category": asset.get("category"),
                    "sector": asset.get("sector"),

                    "is_stablecoin": asset.get(
                        "is_stablecoin",
                        False
                    ),

                    "market_cap_tier": asset.get(
                        "market_cap_tier"
                    ),

                    "base_risk_score": asset.get(
                        "base_risk_score",
                        5
                    ),

                    "liquidity_score": asset.get(
                        "liquidity_score",
                        3
                    ),

                    "price_history": asset.get(
                        "price_history",
                        []
                    ),

                    "value_usd": 0
                }

            grouped[symbol]["value_usd"] += value

        result = []

        for symbol, item in grouped.items():

            allocation_pct = (
                item["value_usd"] / total * 100
            ) if total else 0

            item["value_usd"] = round(
                item["value_usd"],
                2
            )

            item["allocation_pct"] = round(
                allocation_pct,
                2
            )

            # ============================================
            # Volatility
            # ============================================

            volatility = self.calculate_volatility(
                item["price_history"]
            )

            item["volatility_pct"] = volatility

            # ============================================
            # Drawdown
            # ============================================

            drawdown = self.calculate_drawdown(
                item["price_history"]
            )

            item["max_drawdown_pct"] = drawdown

            # ============================================
            # Concentration
            # ============================================

            item["concentration_level"] = (
                self.get_concentration_level(
                    allocation_pct
                )
            )

            # ============================================
            # Asset risk level
            # ============================================

            item["risk_level"] = (
                self.calculate_asset_risk_level(
                    item,
                    allocation_pct,
                    volatility
                )
            )

            result.append(item)

        return sorted(
            result,
            key=lambda x: x["value_usd"],
            reverse=True
        )

    # =========================================================
    # VOLATILITY
    # =========================================================

    def calculate_volatility(
        self,
        price_history: list[dict]
    ) -> float:

        if not price_history:
            return 0.0

        prices = [
            p["price"]
            for p in price_history
            if p.get("price")
        ]

        if len(prices) < 2:
            return 0.0

        returns = []

        for i in range(1, len(prices)):

            prev = prices[i - 1]

            current = prices[i]

            if prev <= 0:
                continue

            returns.append(
                (current - prev) / prev
            )

        if not returns:
            return 0.0

        mean = sum(returns) / len(returns)

        variance = sum(
            (r - mean) ** 2
            for r in returns
        ) / len(returns)

        volatility = math.sqrt(variance)

        return round(volatility * 100, 2)

    # =========================================================
    # MAX DRAWDOWN
    # =========================================================

    def calculate_drawdown(
        self,
        price_history: list[dict]
    ) -> float:

        if not price_history:
            return 0.0

        prices = [
            p["price"]
            for p in price_history
            if p.get("price")
        ]

        if len(prices) < 2:
            return 0.0

        peak = prices[0]

        max_drawdown = 0

        for price in prices:

            if price > peak:
                peak = price

            drawdown = (
                (peak - price) / peak
            )

            max_drawdown = max(
                max_drawdown,
                drawdown
            )

        return round(max_drawdown * 100, 2)

    # =========================================================
    # CONCENTRATION
    # =========================================================

    def get_concentration_level(
        self,
        allocation_pct: float
    ) -> str:

        if allocation_pct >= 50:
            return "very_high"

        if allocation_pct >= 30:
            return "high"

        if allocation_pct >= 15:
            return "medium"

        return "low"

    def calculate_concentration_risk(
        self,
        allocations: list[dict]
    ):

        if not allocations:
            return {
                "score": 0,
                "level": "low"
            }

        largest = max(
            a["allocation_pct"]
            for a in allocations
        )

        # Herfindahl-Hirschman Index
        hhi = sum(
            (a["allocation_pct"] / 100) ** 2
            for a in allocations
        )

        hhi_score = hhi * 100

        if largest >= 60 or hhi_score >= 45:
            level = "very_high"

        elif largest >= 40 or hhi_score >= 30:
            level = "high"

        elif largest >= 20 or hhi_score >= 15:
            level = "medium"

        else:
            level = "low"

        return {
            "largest_position_pct": round(
                largest,
                2
            ),

            "hhi_score": round(
                hhi_score,
                2
            ),

            "level": level
        }

    # =========================================================
    # DIVERSIFICATION
    # =========================================================

    def calculate_diversification_score(
        self,
        allocations: list[dict]
    ):

        if not allocations:
            return 0

        hhi = sum(
            (a["allocation_pct"] / 100) ** 2
            for a in allocations
        )

        diversification = (1 - hhi) * 100

        return round(
            max(0, diversification),
            2
        )

    # =========================================================
    # PORTFOLIO RISK SCORE
    # =========================================================

    def calculate_portfolio_risk_score(
        self,
        allocations: list[dict]
    ):

        if not allocations:
            return {
                "score": 0,
                "level": "low"
            }

        total_weighted_risk = 0

        for asset in allocations:

            allocation_weight = (
                asset["allocation_pct"] / 100
            )

            base_risk = asset.get(
                "base_risk_score",
                5
            )

            volatility = asset.get(
                "volatility_pct",
                0
            )

            volatility_factor = min(
                volatility / 10,
                3
            )

            risk_score = (
                base_risk +
                volatility_factor
            )

            total_weighted_risk += (
                risk_score * allocation_weight
            )

        score = round(
            min(total_weighted_risk, 10),
            2
        )

        if score <= 2:
            level = "low"

        elif score <= 4:
            level = "medium"

        elif score <= 7:
            level = "high"

        else:
            level = "very_high"

        return {
            "score": score,
            "level": level
        }

    # =========================================================
    # ASSET RISK LEVEL
    # =========================================================

    def calculate_asset_risk_level(
        self,
        asset: dict,
        allocation_pct: float,
        volatility: float
    ):

        risk = asset.get(
            "base_risk_score",
            5
        )

        if allocation_pct >= 40:
            risk += 1

        if volatility >= 8:
            risk += 2

        elif volatility >= 4:
            risk += 1

        if asset.get("is_stablecoin"):
            risk -= 2

        risk = max(risk, 1)

        if risk <= 2:
            return "low"

        if risk <= 5:
            return "medium"

        if risk <= 7:
            return "high"

        return "very_high"

    # =========================================================
    # FULL ANALYTICS
    # =========================================================

    def analyze_portfolio(
        self,
        assets: list[dict]
    ):

        allocations = (
            self.calculate_asset_allocation(
                assets
            )
        )

        concentration = (
            self.calculate_concentration_risk(
                allocations
            )
        )

        diversification = (
            self.calculate_diversification_score(
                allocations
            )
        )

        portfolio_risk = (
            self.calculate_portfolio_risk_score(
                allocations
            )
        )

        total_value = round(
            sum(
                a.get("value_usd", 0)
                for a in allocations
            ),
            2
        )

        stablecoin_ratio = round(
            sum(
                a["allocation_pct"]
                for a in allocations
                if a.get("is_stablecoin")
            ),
            2
        )

        return {
            "total_value_usd": total_value,

            "stablecoin_ratio_pct": stablecoin_ratio,

            "diversification_score": diversification,

            "concentration_risk": concentration,

            "portfolio_risk": portfolio_risk,

            "allocations": allocations
        }