from config import TheGraphConfig
from data_engine.models.yield_model import LendingPosition
from data_engine.providers.the_graph.the_graph import TheGraph
from data_engine.services.prices.pricing_service import PricingService, \
    TokenNotFoundException


class AaveGraph(TheGraph):
    ATOKEN_PREFIX_MAP = {
        "AETHWETH": "WETH",
        "AETHWBTC": "WBTC",
        "AETHUSDC": "USDC",
        "AETHUSDT": "USDT",
        "AETHDAI": "DAI",
        "AETHLINK": "LINK",
        "AETHAAVE": "AAVE",
        "AETHCBETH": "CBETH",
        "AETHRETH": "RETH",
        "AETHLUSD": "LUSD",
        "AETHCRV": "CRV",
        "AETHGHO": "GHO",
        "AWETH": "WETH",
        "AWBTC": "WBTC",
        "AUSDC": "USDC",
        "AUSDT": "USDT",
        "ADAI": "DAI",
        "ALINK": "LINK",
        "AUNI": "UNI",
        "ASNX": "SNX",
        "ABAL": "BAL",
        "ACRV": "CRV",
        "AMKR": "MKR",
        "AENS": "ENS",
    }

    RAY = 10 ** 27

    def __init__(self, pricing: PricingService):
        super().__init__()
        self.pricing = pricing
        self.url = TheGraphConfig.AAVE_GRAPH

    async def get_protocol_stats(self) -> dict:
        query = """
        {
          lendingProtocols(first: 1) {
            id
            totalValueLockedUSD
            cumulativeSupplySideRevenueUSD
            cumulativeProtocolSideRevenueUSD
            cumulativeTotalRevenueUSD
          }
        }
        """
        data = await self.query(self.url, query)
        protocols = data.get("lendingProtocols", [])
        if not protocols:
            return {}
        p = protocols[0]
        return {
            "address_provider": p["id"],
            "total_tvl_usd": round(float(p.get("totalValueLockedUSD") or 0), 4),
            "cumulative_supply_side_revenue_usd": round(
                float(p.get("cumulativeSupplySideRevenueUSD") or 0), 4
            ),
            "cumulative_protocol_revenue_usd": round(
                float(p.get("cumulativeProtocolSideRevenueUSD") or 0), 4
            ),
            "cumulative_total_revenue_usd": round(
                float(p.get("cumulativeTotalRevenueUSD") or 0), 4
            ),
        }

    async def get_markets(self, min_tvl: float = 10_000) -> list[dict]:
        query = """
        query GetMarkets {
          markets(
            orderBy: id
            orderDirection: asc
            where: { isActive: true }
          ) {
            id
            name
            inputToken {
              id
              symbol
              decimals
            }
            totalValueLockedUSD
            totalDepositBalanceUSD
            totalBorrowBalanceUSD
            maximumLTV
            liquidationThreshold
            liquidationPenalty
            isActive
            canBorrowFrom
            rates {
              rate
              side
              type
            }
          }
        }
        """
        data = await self.query(url=self.url, query=query)
        supported_tokens = set(self.pricing.get_supported_tokens())
        markets = []

        for m in data.get("markets", []):
            # Fallback check đề phòng Subgraph hoặc dữ liệu lỗi
            if not m.get("isActive", True):
                continue

            tvl = float(m.get("totalValueLockedUSD") or 0)
            if tvl < min_tvl:
                continue

            supply_apr, borrow_apr, borrow_stable_apr = self._extract_rates_full(
                m.get("rates", [])
            )
            symbol = self._normalize_atoken(m["inputToken"]["symbol"])

            if supported_tokens and symbol not in supported_tokens:
                continue

            markets.append(
                {
                    "_id": f"aave:{m['id']}",
                    "address": m["id"],
                    "name": m.get("name", ""),
                    "protocol": "aave",
                    "type": "lending",
                    "asset": symbol.lower(),
                    "tokenAddress": m["inputToken"]["id"],
                    "decimals": int(m["inputToken"].get("decimals") or 18),
                    "tvl": round(tvl, 4),
                    "totalDepositUsd": round(
                        float(m.get("totalDepositBalanceUSD") or 0), 4
                    ),
                    "totalBorrowUsd": round(
                        float(m.get("totalBorrowBalanceUSD") or 0), 4
                    ),
                    "supplyApr": round(supply_apr, 4),
                    "borrowApr": round(borrow_apr, 4),
                    "borrowStableApr": round(borrow_stable_apr, 4),
                    "maxLtv": round(float(m.get("maximumLTV") or 0), 4),
                    "liquidationThreshold": round(
                        float(m.get("liquidationThreshold") or 0), 4
                    ),
                    "liquidationPenalty": round(
                        float(m.get("liquidationPenalty") or 0), 4
                    ),
                    "isActive": True,
                    "canBorrow": bool(m.get("canBorrowFrom", False)),
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
                balance = float(p.get("balance", "0"))
            except (ValueError, TypeError):
                continue
            if balance <= 0:
                continue

            raw_symbol = p["asset"]["symbol"]
            symbol = self._normalize_atoken(raw_symbol)
            side = p["side"]

            key = (symbol, side)
            if key in seen:
                continue
            seen.add(key)

            try:
                price = self.pricing.get_price(symbol)
            except TokenNotFoundException:
                self.logger.warning(f"Aave: no price for {symbol}, skipping")
                continue

            market = p.get("market") or {}
            supply_apr, borrow_apr, borrow_stable_apr = self._extract_rates_full(
                market.get("rates", [])
            )

            positions.append(
                LendingPosition(
                    type="lending",
                    protocol="aave_v3",
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
                    borrow_stable_apr=round(borrow_stable_apr, 4)
                )
            )

        return positions

    async def get_position_snapshots(self, wallet: str, limit: int = 90) -> list[dict]:
        query = f"""
        {{
          positionSnapshots(
            first: {limit}
            orderBy: timestamp
            orderDirection: desc
            where: {{ account: "{wallet.lower()}" }}
          ) {{
            timestamp
            balance
            side
            asset {{
              symbol
            }}
          }}
        }}
        """
        data = await self.query(self.url, query)
        result = []
        for s in data.get("positionSnapshots", []):
            symbol = self._normalize_atoken(s["asset"]["symbol"])
            result.append(
                {
                    "timestamp": int(s.get("timestamp") or 0),
                    "symbol": symbol,
                    "balance": float(s.get("balance") or 0),
                    "side": s.get("side"),
                }
            )
        return result

    def _build_tx_where_clause(self,
                               wallet: str | None,
                               market_id: str | None,
                               from_ts: int | None,
                               to_ts: int | None,
                               wallet_key: str = "account") -> str:
        where_parts = []
        if wallet:
            where_parts.append(f'{wallet_key}: "{wallet.lower()}"')
        if market_id:
            where_parts.append(f'market: "{market_id.lower()}"')
        if from_ts:
            where_parts.append(f'timestamp_gte: {from_ts}')
        if to_ts:
            where_parts.append(f'timestamp_lt: {to_ts}')

        return f"where: {{ {', '.join(where_parts)} }}" if where_parts else ""

    async def get_deposits(self,
                           wallet: str | None = None,
                           market_id: str | None = None,
                           from_ts: int | None = None,
                           to_ts: int | None = None,
                           limit: int = 1000) -> list[dict]:
        where_clause = self._build_tx_where_clause(wallet, market_id, from_ts, to_ts)
        query = f"""
        {{
          deposits(
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
        return [self._format_action(d, "deposit") for d in data.get("deposits", [])]

    async def get_borrows(self,
                          wallet: str | None = None,
                          market_id: str | None = None,
                          from_ts: int | None = None,
                          to_ts: int | None = None,
                          limit: int = 100) -> list[dict]:
        where_clause = self._build_tx_where_clause(wallet, market_id, from_ts, to_ts)
        query = f"""
        {{
          borrows(
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
        return [self._format_action(b, "borrow") for b in data.get("borrows", [])]

    async def get_repays(self,
                         wallet: str | None = None,
                         market_id: str | None = None,
                         from_ts: int | None = None,
                         to_ts: int | None = None,
                         limit: int = 100) -> list[dict]:
        where_clause = self._build_tx_where_clause(wallet, market_id, from_ts, to_ts)
        query = f"""
        {{
          repays(
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
        return [self._format_action(r, "repay") for r in data.get("repays", [])]

    async def get_withdraws(self,
                            wallet: str | None = None,
                            market_id: str | None = None,
                            from_ts: int | None = None,
                            to_ts: int | None = None,
                            limit: int = 100) -> list[dict]:
        where_clause = self._build_tx_where_clause(wallet, market_id, from_ts, to_ts)
        query = f"""
        {{
          withdraws(
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
        return [self._format_action(w, "withdraw") for w in data.get("withdraws", [])]

    async def get_liquidations(self,
                               liquidatee: str | None = None,
                               liquidator: str | None = None,
                               market_id: str | None = None,
                               from_ts: int | None = None,
                               to_ts: int | None = None,
                               limit: int = 100) -> list[dict]:
        where_parts = []
        if liquidatee:
            where_parts.append(f'liquidatee: "{liquidatee.lower()}"')
        if liquidator:
            where_parts.append(f'liquidator: "{liquidator.lower()}"')
        if market_id:
            where_parts.append(f'market: "{market_id.lower()}"')
        if from_ts:
            where_parts.append(f'timestamp_gte: {from_ts}')
        if to_ts:
            where_parts.append(f'timestamp_lt: {to_ts}')

        where_clause = f"where: {{ {', '.join(where_parts)} }}" if where_parts else ""

        query = f"""
        {{
          liquidates(
            first: {limit}
            orderBy: timestamp
            orderDirection: desc
            {where_clause}
          ) {{
            id
            timestamp
            liquidator
            liquidatee
            amount
            amountUSD
            profitUSD
            asset {{ symbol decimals }}
            market {{ id }}
          }}
        }}
        """
        data = await self.query(self.url, query)
        result = []
        for liq in data.get("liquidates", []):
            symbol = self._normalize_atoken(liq["asset"]["symbol"])
            result.append(
                {
                    "tx_id": liq["id"],
                    "timestamp": int(liq.get("timestamp") or 0),
                    "market_id": liq["market"]["id"],
                    "symbol": symbol,
                    "liquidator": liq.get("liquidator"),
                    "liquidatee": liq.get("liquidatee"),
                    "amount": float(liq.get("amount") or 0),
                    "amount_usd": round(float(liq.get("amountUSD") or 0), 4),
                    "profit_usd": round(float(liq.get("profitUSD") or 0), 4),
                }
            )
        return result

    async def get_interest_rates(self, market_id: str) -> list[dict]:
        query = f"""
        {{
          market(id: "{market_id.lower()}") {{
            id
            inputToken {{ symbol }}
            rates {{
              rate
              side
              type
            }}
          }}
        }}
        """
        data = await self.query(self.url, query)
        market = data.get("market")
        if not market:
            return []

        symbol = self._normalize_atoken(market["inputToken"]["symbol"])
        result = []
        for r in market.get("rates", []):
            try:
                raw = float(r.get("rate", 0))
            except (ValueError, TypeError):
                continue
            rate_pct = (raw / self.RAY * 100) if raw > 1000 else raw
            result.append(
                {
                    "market_id": market_id,
                    "symbol": symbol,
                    "side": r.get("side"),
                    "type": r.get("type"),
                    "rate_pct": round(rate_pct, 6),
                }
            )
        return result

    async def get_oracles(self, limit: int = 50) -> list[dict]:
        query = f"""
        {{
          priceOracles(first: {limit}) {{
            id
            usdPriceEth
          }}
        }}
        """
        data = await self.query(self.url, query)
        result = []
        for o in data.get("priceOracles", []):
            result.append(
                {
                    "oracle_address": o["id"],
                    "usd_price_eth": float(o.get("usdPriceEth") or 0),
                }
            )
        return result

    async def get_financials_daily(self, days: int = 30) -> list[dict]:
        query = f"""
        {{
          financialsDailySnapshots(
            first: {days}
            orderBy: timestamp
            orderDirection: desc
          ) {{
            timestamp
            totalValueLockedUSD
            dailySupplySideRevenueUSD
            dailyProtocolSideRevenueUSD
            dailyTotalRevenueUSD
            cumulativeSupplySideRevenueUSD
            cumulativeProtocolSideRevenueUSD
          }}
        }}
        """
        data = await self.query(self.url, query)
        result = []
        for s in data.get("financialsDailySnapshots", []):
            result.append(
                {
                    "timestamp": int(s.get("timestamp") or 0),
                    "tvl_usd": round(float(s.get("totalValueLockedUSD") or 0), 4),
                    "daily_supply_revenue_usd": round(
                        float(s.get("dailySupplySideRevenueUSD") or 0), 4
                    ),
                    "daily_protocol_revenue_usd": round(
                        float(s.get("dailyProtocolSideRevenueUSD") or 0), 4
                    ),
                    "daily_total_revenue_usd": round(
                        float(s.get("dailyTotalRevenueUSD") or 0), 4
                    ),
                    "cumulative_supply_revenue_usd": round(
                        float(s.get("cumulativeSupplySideRevenueUSD") or 0), 4
                    ),
                    "cumulative_protocol_revenue_usd": round(
                        float(s.get("cumulativeProtocolSideRevenueUSD") or 0), 4
                    ),
                }
            )
        return result

    async def get_market_daily_snapshots(self, market_id: str, days: int = 30) -> list[
        dict]:
        query = f"""
        {{
          marketDailySnapshots(
            first: {days}
            orderBy: timestamp
            orderDirection: desc
            where: {{ market: "{market_id.lower()}" }}
          ) {{
            timestamp
            totalValueLockedUSD
            totalDepositBalanceUSD
            totalBorrowBalanceUSD
            dailyDepositUSD
            dailyBorrowUSD
            dailyRepayUSD
            dailyWithdrawUSD
            dailyLiquidateUSD
            rates {{
              rate
              side
              type
            }}
          }}
        }}
        """
        data = await self.query(self.url, query)
        result = []
        for s in data.get("marketDailySnapshots", []):
            supply_apr, borrow_apr, borrow_stable_apr = self._extract_rates_full(
                s.get("rates", [])
            )
            result.append(
                {
                    "timestamp": int(s.get("timestamp") or 0),
                    "tvl_usd": round(float(s.get("totalValueLockedUSD") or 0), 4),
                    "total_deposit_usd": round(
                        float(s.get("totalDepositBalanceUSD") or 0), 4
                    ),
                    "total_borrow_usd": round(
                        float(s.get("totalBorrowBalanceUSD") or 0), 4
                    ),
                    "daily_deposit_usd": round(float(s.get("dailyDepositUSD") or 0), 4),
                    "daily_borrow_usd": round(float(s.get("dailyBorrowUSD") or 0), 4),
                    "daily_repay_usd": round(float(s.get("dailyRepayUSD") or 0), 4),
                    "daily_withdraw_usd": round(
                        float(s.get("dailyWithdrawUSD") or 0), 4
                    ),
                    "daily_liquidate_usd": round(
                        float(s.get("dailyLiquidateUSD") or 0), 4
                    ),
                    "supply_apr": round(supply_apr, 4),
                    "borrow_apr": round(borrow_apr, 4),
                    "borrow_stable_apr": round(borrow_stable_apr, 4),
                }
            )
        return result

    async def get_market_hourly_snapshots(self, market_id: str, hours: int = 48) -> \
        list[dict]:
        query = f"""
        {{
          marketHourlySnapshots(
            first: {hours}
            orderBy: timestamp
            orderDirection: desc
            where: {{ market: "{market_id.lower()}" }}
          ) {{
            timestamp
            totalValueLockedUSD
            totalDepositBalanceUSD
            totalBorrowBalanceUSD
            hourlyDepositUSD
            hourlyBorrowUSD
            hourlyRepayUSD
            hourlyWithdrawUSD
            hourlyLiquidateUSD
            rates {{
              rate
              side
              type
            }}
          }}
        }}
        """
        data = await self.query(self.url, query)
        result = []
        for s in data.get("marketHourlySnapshots", []):
            supply_apr, borrow_apr, borrow_stable_apr = self._extract_rates_full(
                s.get("rates", [])
            )
            result.append(
                {
                    "timestamp": int(s.get("timestamp") or 0),
                    "tvl_usd": round(float(s.get("totalValueLockedUSD") or 0), 4),
                    "total_deposit_usd": round(
                        float(s.get("totalDepositBalanceUSD") or 0), 4
                    ),
                    "total_borrow_usd": round(
                        float(s.get("totalBorrowBalanceUSD") or 0), 4
                    ),
                    "hourly_deposit_usd": round(
                        float(s.get("hourlyDepositUSD") or 0), 4
                    ),
                    "hourly_borrow_usd": round(float(s.get("hourlyBorrowUSD") or 0), 4),
                    "hourly_repay_usd": round(float(s.get("hourlyRepayUSD") or 0), 4),
                    "hourly_withdraw_usd": round(
                        float(s.get("hourlyWithdrawUSD") or 0), 4
                    ),
                    "hourly_liquidate_usd": round(
                        float(s.get("hourlyLiquidateUSD") or 0), 4
                    ),
                    "supply_apr": round(supply_apr, 4),
                    "borrow_apr": round(borrow_apr, 4),
                    "borrow_stable_apr": round(borrow_stable_apr, 4),
                }
            )
        return result

    def _normalize_atoken(self, symbol: str) -> str:
        upper = symbol.upper().strip()
        if upper in self.ATOKEN_PREFIX_MAP:
            return self.ATOKEN_PREFIX_MAP[upper]
        return upper

    def _extract_rates(self, rates: list) -> tuple[float, float]:
        supply_apr, borrow_apr, _ = self._extract_rates_full(rates)
        return supply_apr, borrow_apr

    def _extract_rates_full(self, rates: list) -> tuple[float, float, float]:
        supply_apr = 0.0
        borrow_apr = 0.0
        borrow_stable_apr = 0.0

        for r in rates:
            try:
                raw = float(r.get("rate", 0))
            except (ValueError, TypeError):
                continue
            rate_pct = (raw / self.RAY * 100) if raw > 1000 else raw
            side = r.get("side", "")
            rtype = r.get("type", "")

            if side == "LENDER" and rtype == "VARIABLE":
                supply_apr = rate_pct
            elif side == "BORROWER" and rtype == "VARIABLE":
                borrow_apr = rate_pct
            elif side == "BORROWER" and rtype == "STABLE":
                borrow_stable_apr = rate_pct

        return supply_apr, borrow_apr, borrow_stable_apr

    def _format_action(self, item: dict, action_type: str) -> dict:
        symbol = self._normalize_atoken(item["asset"]["symbol"])
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
