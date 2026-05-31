from collections import defaultdict


class PortfolioCalculator:
    def summarize(self, positions):
        total_base = sum(p.base_value_usd for p in positions)
        total_net = sum(p.net_value_usd for p in positions)

        return {
            "total_value": total_base,
            "net_value": total_net,
            "health_ratio": total_net / total_base if total_base else 0,
        }

    def exposure(self, positions):
        result = defaultdict(float)

        for p in positions:
            result[p.exposure_type] += p.base_value_usd

        return dict(result)

    def category_allocation(self, positions):
        result = defaultdict(float)

        for p in positions:
            result[p.asset_category] += p.base_value_usd

        return dict(result)