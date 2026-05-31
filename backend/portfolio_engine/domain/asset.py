STABLES = {"USDT", "USDC", "DAI"}
MAJORS = {"BTC", "ETH"}


class AssetClassifier:
    def classify(self, symbols: list[str]) -> str:
        if all(s in STABLES for s in symbols):
            return "stable"
        if any(s in MAJORS for s in symbols):
            return "major"
        return "volatile"