from config import TheGraphConfig
from data_engine.models.yield_model import LendingPosition
from data_engine.providers.the_graph.the_graph import TheGraph
from data_engine.services.prices.pricing_service import PricingService, \
    TokenNotFoundException


class CompoundGraph(TheGraph):
    CTOKEN_PREFIX_MAP = {
        "CUSDCV3": "USDC",
        "CUSDTV3": "USDT",
        "CWETHV3": "WETH",
        "CCOMPV3": "COMP"
    }

    RAY = 10 ** 27

    def __init__(self, pricing: PricingService):
        super().__init__()
        self.pricing = pricing
        self.url = TheGraphConfig.COMPOUND_GRAPH

    async def get_markets(self, min_tvl: float = 100_000) -> list[dict]:
        query = """
        query GetCompoundMarkets {
          markets {
            id
            name
            isActive
            maximumLTV
            liquidationThreshold
            liquidationPenalty
            totalValueLockedUSD
            totalDepositBalanceUSD
            totalBorrowBalanceUSD
            openPositionCount
            inputToken {
              id
              symbol
              decimals
            }
            rates {
              rate
              side
              type
            }
          }
        }
        """

        data = await self.query(url=self.url, query=query)

        raw_supported = self.pricing.get_supported_tokens() or []
        supported_tokens = {str(t).upper().strip() for t in raw_supported}

        markets = []

        for m in data.get("markets", []):

            if not m.get("isActive", False):
                continue

            tvl = float(m.get("totalValueLockedUSD") or 0)
            deposit_usd = float(m.get("totalDepositBalanceUSD") or 0)
            borrow_usd = float(m.get("totalBorrowBalanceUSD") or 0)

            open_positions = int(m.get("openPositionCount") or 0)

            if tvl < min_tvl:
                continue

            if open_positions < 5:
                continue

            input_token = m.get("inputToken") or {}
            raw_symbol = input_token.get("symbol", "")

            if hasattr(self, "_normalize_atoken"):
                symbol = self._normalize_atoken(raw_symbol).upper().strip()
            else:
                symbol = raw_symbol.upper().strip()

            if supported_tokens and symbol not in supported_tokens:
                continue

            supply_apr = 0.0
            borrow_apr = 0.0

            for r in m.get("rates", []):
                rate_value = float(r.get("rate") or 0) * 100

                if r.get("side") == "LENDER":
                    supply_apr = rate_value

                elif r.get("side") == "BORROWER":
                    borrow_apr = rate_value

            markets.append(
                {
                    "_id": f"compound:{m['id']}",
                    "address": m["id"],
                    "name": m.get("name", f"Compound {symbol}"),
                    "protocol": "compound",
                    "type": "lending",
                    "asset": symbol.lower(),
                    "tokenAddress": input_token.get("id"),
                    "decimals": int(input_token.get("decimals") or 18),
                    "tvl": round(tvl, 4),
                    "totalDepositUsd": round(deposit_usd, 4),
                    "totalBorrowUsd": round(borrow_usd, 4),
                    "supplyApr": round(supply_apr, 4),
                    "borrowApr": round(borrow_apr, 4),
                    "borrowStableApr": 0.0,
                    "maxLtv": round(float(m.get("maximumLTV") or 0) * 100, 4),
                    "liquidationThreshold": round(float(m.get("liquidationThreshold") or 0) * 100, 4),
                    "liquidationPenalty": round(float(m.get("liquidationPenalty") or 0) * 100, 4),
                    "isActive": True,
                    "canBorrow": True,
                }
            )

        return markets

    async def get_positions(self, wallet: str) -> list[LendingPosition]:
        query = f"""
        {{
          positions(where: {{ account: "{wallet.lower()}" }}) {{
            id
            balance
            side
            isCollateral
            asset {{
              symbol
              decimals
            }}
            market {{
              id
              maximumLTV
              liquidationThreshold
              rates {{
                rate
                side
                type
              }}
            }}
          }}
        }}
        """
        data = await self.query(self.url, query)
        positions = []
        seen = set()

        for p in data.get("positions", []):
            try:
                balance_raw = float(p.get("balance", "0"))
                decimals = int(p.get("asset", {}).get("decimals") or 18)
                balance = self._normalize_position_balance(balance_raw, decimals)
            except (ValueError, TypeError):
                continue
            if balance <= 0:
                continue

            raw_symbol = p["asset"]["symbol"]
            symbol = self._normalize_ctoken(raw_symbol)
            side = p["side"]

            key = (symbol, side)
            if key in seen:
                continue
            seen.add(key)

            try:
                price = self.pricing.get_price(symbol)
            except TokenNotFoundException:
                self.logger.warning(f"Compound: No price found for {symbol}, skipping")
                continue

            market = p.get("market") or {}
            supply_apr, borrow_apr = self._extract_rates(market.get("rates", []))

            positions.append(
                LendingPosition(
                    type="lending",
                    protocol="compound_v3",
                    position_id=p.get("id"),
                    market_id=market.get("id"),
                    asset=[symbol],
                    raw_symbol=raw_symbol,
                    balance=balance,
                    value_usd=round(balance * price, 4),
                    side=side,
                    is_collateral=bool(p.get("isCollateral", False)),
                    max_ltv=round(float(market.get("maximumLTV") or 0), 4),
                    liquidation_threshold=round(
                        float(market.get("liquidationThreshold") or 0), 4
                    ),
                    supply_apr=round(supply_apr, 4),
                    borrow_apr=round(borrow_apr, 4),
                    borrow_stable_apr=0.0
                )
            )
        return positions

    async def get_deposits(self,
                           wallet: str | None = None,
                           from_ts: int | None = None,
                           limit: int = 1000) -> list[dict]:
        return await self._get_actions(wallet, "deposit", "deposits", from_ts, limit)

    async def get_borrows(self,
                          wallet: str | None = None,
                          from_ts: int | None = None,
                          limit: int = 1000) -> list[dict]:
        return await self._get_actions(wallet, "borrow", "borrows", from_ts, limit)

    async def get_repays(self,
                         wallet: str | None = None,
                         from_ts: int | None = None,
                         limit: int = 1000) -> list[dict]:
        return await self._get_actions(wallet, "repay", "repays", from_ts, limit)

    async def get_withdraws(self,
                            wallet: str | None = None,
                            from_ts: int | None = None,
                            limit: int = 1000) -> list[dict]:
        return await self._get_actions(wallet, "withdraw", "withdraws", from_ts, limit)

    async def _get_actions(self,
                           wallet: str | None,
                           action_label: str,
                           entity_name: str,
                           from_ts: int | None,
                           limit: int) -> list[dict]:
        where_parts = []
        if wallet:
            where_parts.append(f'account: "{wallet.lower()}"')
        if from_ts:
            where_parts.append(f'timestamp_gte: {from_ts}')

        where_clause = f"where: {{ {', '.join(where_parts)} }}" if where_parts else ""

        query = f"""
        {{
          {entity_name}(
            first: {limit}
            orderBy: timestamp
            orderDirection: desc
            {where_clause}
          ) {{
            id
            timestamp
            amount
            amountUSD
            asset {{ symbol decimals }}
            market {{ id }}
          }}
        }}
        """
        data = await self.query(self.url, query)
        return [self._format_action(item, action_label) for item in
                data.get(entity_name, [])]

    def _normalize_ctoken(self, symbol: str) -> str:
        upper = symbol.upper().strip()
        if upper in self.CTOKEN_PREFIX_MAP:
            return self.CTOKEN_PREFIX_MAP[upper]
        if upper.startswith("C") and len(upper) > 3:  # Dự phòng dạng cUSDC, cDAI
            return upper[1:]
        return upper

    def _normalize_position_balance(self, balance: float, decimals: int) -> float:
        if balance <= 0:
            return 0.0
        return balance / (10 ** decimals)

    def _extract_rates(self, rates: list) -> tuple[float, float]:
        supply_apr = 0.0
        borrow_apr = 0.0
        for r in rates:
            try:
                raw = float(r.get("rate", 0))
            except (ValueError, TypeError):
                continue
            rate_pct = (raw / self.RAY * 100) if raw > 1000 else raw
            side = r.get("side", "")
            if side == "LENDER":
                supply_apr = rate_pct
            elif side == "BORROWER":
                borrow_apr = rate_pct
        return supply_apr, borrow_apr

    def _format_action(self, item: dict, action_type: str) -> dict:
        symbol = self._normalize_ctoken(item["asset"]["symbol"])
        decimals = int(item["asset"].get("decimals") or 18)
        amount_raw = float(item.get("amount") or 0)
        amount = amount_raw / (10 ** decimals) if amount_raw > 1e10 else amount_raw
        return {
            "tx_id": item["id"],
            "action": action_type,
            "timestamp": int(item.get("timestamp") or 0),
            "market_id": item["market"]["id"],
            "symbol": symbol,
            "amount": round(amount, 8),
            "amount_usd": round(float(item.get("amountUSD") or 0), 4),
        }
