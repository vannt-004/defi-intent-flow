import json
import re
from dataclasses import dataclass
from typing import Callable

import httpx

from config import AIConfig


@dataclass
class IntentSpec:
    intent_type: str
    keywords: tuple[str, ...]
    builder: Callable[[str], dict | None]


class NLPIntentExtractor:
    """
    Extracts simulation intents from natural language.

    Primary path: AI provider returning structured JSON.
    Fallback path: declarative intent specs, used when AI is not configured or fails.
    """

    def __init__(self):
        self.specs = (
            IntentSpec("loop_lending", ("loop", "leverage", "xoay vòng", "vòng", "recursive", "folding"), self._loop_lending),
            IntentSpec("provide_liquidity", ("provide liquidity", "add liquidity", "lp", "liquidity pool", "cung cấp thanh khoản"), self._provide_liquidity),
            IntentSpec("price_shock", ("drop", "fall", "decrease", "down", "giảm", "tăng", "increase", "up", "rise"), self._price_shock),
            IntentSpec("buy", ("buy", "purchase", "mua"), self._buy),
            IntentSpec("swap", ("swap", "exchange", "convert", "đổi", "hoán đổi"), self._swap),
            IntentSpec("borrow", ("borrow", "vay"), self._borrow),
            IntentSpec("lend", ("lend", "supply", "deposit", "stake", "staking", "gửi", "cung cấp"), self._lend),
        )

    def extract(self, text: str) -> dict:
        text = (text or "").strip()
        if not text:
            return self._unknown("Empty input")

        ai_result = self._extract_with_ai(text)
        if ai_result and ai_result.get("type") != "unknown":
            ai_result.setdefault("parser", "ai_structured")
            return ai_result

        fallback = self._extract_with_specs(text)
        fallback.setdefault("parser", "intent_specs")
        return fallback

    def _extract_with_ai(self, text: str) -> dict | None:
        if AIConfig.INTENT_PROVIDER == "rules":
            return None
        if not AIConfig.OPENAI_API_KEY or not AIConfig.OPENAI_MODEL:
            return None

        prompt = {
            "role": "system",
            "content": (
                "Extract a DeFi portfolio simulation intent. Return only compact JSON. "
                "Allowed type values: price_shock, buy, swap, lend, stake, borrow, loop_lending, provide_liquidity, unknown. "
                "For price_shock return {type, shocks:{SYMBOL: pct}, confidence}. "
                "For buy return {type, symbol, fromSymbol, amount, confidence}. "
                "For swap return {type, fromSymbol, toSymbol, amount, confidence}. "
                "For lend/stake return {type, symbol, amount, confidence}. "
                "For borrow return {type, symbol, amount, confidence}. "
                "For loop_lending return {type, collateralSymbol, borrowSymbol, amount, loops, confidence}. "
                "For provide_liquidity return {type, token0, token1, amount0, amount1, shockPct, confidence}. "
                "Do not provide investment advice."
            ),
        }
        try:
            response = httpx.post(
                f"{AIConfig.OPENAI_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {AIConfig.OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": AIConfig.OPENAI_MODEL,
                    "temperature": 0,
                    "messages": [prompt, {"role": "user", "content": text}],
                    "response_format": {"type": "json_object"},
                },
                timeout=8,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return self._normalize(parsed)
        except Exception:
            return None

    def _extract_with_specs(self, text: str) -> dict:
        lowered = text.lower()
        candidates = []
        for spec in self.specs:
            keyword_hits = sum(1 for keyword in spec.keywords if keyword in lowered)
            if keyword_hits <= 0:
                continue
            built = spec.builder(text)
            if built:
                built["confidence"] = min(0.9, 0.45 + keyword_hits * 0.15 + built.pop("_confidence_boost", 0))
                candidates.append(built)

        if not candidates:
            return self._unknown("Could not parse a supported simulation intent.")

        return max(candidates, key=lambda item: item.get("confidence", 0))

    def _price_shock(self, text: str) -> dict | None:
        pattern = re.compile(
            r"(?P<symbol>[a-zA-Z][a-zA-Z0-9.]*)\D{0,40}"
            r"(?P<direction>drop|fall|decrease|down|giảm|tăng|increase|up|rise)\D{0,20}"
            r"(?P<pct>\d+(?:\.\d+)?)\s*%",
            re.IGNORECASE,
        )
        match = pattern.search(text)
        if not match:
            return None

        pct = float(match.group("pct"))
        direction = match.group("direction").lower()
        signed_pct = -pct if direction in ("drop", "fall", "decrease", "down", "giảm") else pct
        return {
            "type": "price_shock",
            "shocks": {match.group("symbol").upper(): signed_pct},
            "_confidence_boost": 0.2,
        }

    def _loop_lending(self, text: str) -> dict | None:
        amount = self._amount_symbol(text)
        if not amount:
            return None

        loops = re.search(r"(?P<loops>\d+)\s*(?:loops?|vòng|times?)", text, re.IGNORECASE)
        borrow = re.search(r"(?:borrow|vay)\s+(?P<borrow>[a-zA-Z][a-zA-Z0-9.]*)", text, re.IGNORECASE)
        return {
            "type": "loop_lending",
            "collateralSymbol": amount["symbol"],
            "borrowSymbol": borrow.group("borrow").upper() if borrow else "USDC",
            "amount": amount["amount"],
            "loops": int(loops.group("loops")) if loops else 3,
            "_confidence_boost": 0.25,
        }

    def _swap(self, text: str) -> dict | None:
        amount = self._amount_symbol(text)
        if not amount:
            return None

        target = re.search(r"\b(?:to|for|into|sang|ra)\s+(?P<target>[a-zA-Z][a-zA-Z0-9.]*)\b", text, re.IGNORECASE)
        return {
            "type": "swap",
            "fromSymbol": amount["symbol"],
            "amount": amount["amount"],
            "toSymbol": target.group("target").upper() if target else "USDC",
            "_confidence_boost": 0.15 if target else 0,
        }

    def _buy(self, text: str) -> dict | None:
        target = re.search(
            r"(?:buy|purchase|mua)\s+(?:(?P<amount>\d+(?:\.\d+)?)\s*)?(?P<symbol>[a-zA-Z][a-zA-Z0-9.]*)",
            text,
            re.IGNORECASE,
        )
        amount = self._amount_symbol(text)
        if not target and not amount:
            return None

        funding = re.search(r"(?:with|using|bằng|bang|dùng|dung)\s+(?P<funding>[a-zA-Z][a-zA-Z0-9.]*)", text, re.IGNORECASE)
        symbol = target.group("symbol").upper() if target else amount["symbol"]
        parsed_amount = target.group("amount") if target else None

        return {
            "type": "buy",
            "symbol": symbol,
            "toSymbol": symbol,
            "fromSymbol": funding.group("funding").upper() if funding else "USDC",
            "amount": float(parsed_amount) if parsed_amount else (amount["amount"] if amount else 1),
            "_confidence_boost": 0.2,
        }

    def _provide_liquidity(self, text: str) -> dict | None:
        pair = re.search(
            r"(?P<token0>[a-zA-Z][a-zA-Z0-9.]*)\s*[/\-]\s*(?P<token1>[a-zA-Z][a-zA-Z0-9.]*)",
            text,
            re.IGNORECASE,
        )
        amount = self._amount_symbol(text)
        if not pair and not amount:
            return None

        shock = re.search(r"(?P<pct>-?\d+(?:\.\d+)?)\s*%", text, re.IGNORECASE)
        token0 = pair.group("token0").upper() if pair else amount["symbol"]
        token1 = pair.group("token1").upper() if pair else "USDC"
        return {
            "type": "provide_liquidity",
            "token0": token0,
            "token1": token1,
            "amount0": amount["amount"] if amount and amount["symbol"] == token0 else 0,
            "shockPct": float(shock.group("pct")) if shock else -20,
            "_confidence_boost": 0.2,
        }

    def _lend(self, text: str) -> dict | None:
        amount = self._amount_symbol(text)
        if not amount:
            return None

        lowered = text.lower()
        action = "stake" if "stake" in lowered or "staking" in lowered else "lend"
        return {
            "type": action,
            "symbol": amount["symbol"],
            "amount": amount["amount"],
            "_confidence_boost": 0.1,
        }

    def _borrow(self, text: str) -> dict | None:
        amount = self._amount_symbol(text)
        if not amount:
            return None

        return {
            "type": "borrow",
            "symbol": amount["symbol"],
            "amount": amount["amount"],
            "_confidence_boost": 0.15,
        }

    def _amount_symbol(self, text: str) -> dict | None:
        match = re.search(r"(?P<amount>\d+(?:\.\d+)?)\s*(?P<symbol>[a-zA-Z][a-zA-Z0-9.]*)", text)
        if not match:
            return None

        return {
            "amount": float(match.group("amount")),
            "symbol": match.group("symbol").upper(),
        }

    def _normalize(self, payload: dict) -> dict:
        intent_type = payload.get("type") or "unknown"
        payload["type"] = intent_type
        payload["confidence"] = float(payload.get("confidence") or 0.0)

        if "symbol" in payload:
            payload["symbol"] = str(payload["symbol"]).upper()
        if "fromSymbol" in payload:
            payload["fromSymbol"] = str(payload["fromSymbol"]).upper()
        if "toSymbol" in payload:
            payload["toSymbol"] = str(payload["toSymbol"]).upper()
        if "shocks" in payload and isinstance(payload["shocks"], dict):
            payload["shocks"] = {str(k).upper(): float(v) for k, v in payload["shocks"].items()}
        if "amount" in payload:
            payload["amount"] = float(payload["amount"])
        for key in ("collateralSymbol", "borrowSymbol", "token0", "token1"):
            if key in payload:
                payload[key] = str(payload[key]).upper()
        for key in ("amount0", "amount1", "loops", "targetLtv", "shockPct"):
            if key in payload and payload[key] is not None:
                payload[key] = float(payload[key])

        return payload

    def _unknown(self, message: str) -> dict:
        return {
            "type": "unknown",
            "confidence": 0.0,
            "message": message,
        }
