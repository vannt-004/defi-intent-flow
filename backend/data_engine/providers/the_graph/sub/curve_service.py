
from config import TheGraphConfig
from data_engine.providers.the_graph.the_graph import TheGraph
from data_engine.services.prices.pricing_service import PricingService


class CurveService(TheGraph):

    MIN_POOL_TVL = 1_000
    MAX_APR_PCT  = 500.0

    def __init__(self, pricing: PricingService = None):
        super().__init__()
        self.pricing = pricing
        self.url = TheGraphConfig.CURVE_GRAPH

    async def get_positions(self, wallet: str) -> list[dict]:
        wallet = wallet.lower()

        query = f"""
        {{
          deposits(where: {{ from: "{wallet}" }}) {{
            id
            timestamp
            amountUSD
            inputTokenAmounts
            liquidityPool {{
              id
              name
              totalValueLockedUSD
              inputTokens {{ symbol decimals }}
            }}
          }}

          liquidityGauges(where: {{ account: "{wallet}" }}) {{
            balance
            gauge {{
              liquidityPool {{
                id
                name
                totalValueLockedUSD
                inputTokens {{ symbol decimals }}
              }}
            }}
          }}
        }}
        """

        data = await self.query(self.url, query)
        positions = []

        for d in data.get("deposits", []):
            amount_usd = float(d.get("amountUSD") or 0)
            if amount_usd <= 0:
                continue

            pool = d.get("liquidityPool", {})
            tvl = float(pool.get("totalValueLockedUSD") or 0)
            tokens = pool.get("inputTokens", [])
            symbols = [t["symbol"] for t in tokens]

            positions.append({
                "type": "lp",
                "protocol": "curve",
                "tx_id": d.get("id"),
                "timestamp": int(d.get("timestamp") or 0),
                "pool_id": pool.get("id"),
                "pool": pool.get("name"),
                "asset": symbols,
                "value_usd": round(amount_usd, 4),
                "pool_tvl": round(tvl, 4),
            })

        for g in data.get("liquidityGauges", []):
            balance = float(g.get("balance") or 0)
            if balance <= 0:
                continue

            pool = g.get("gauge", {}).get("liquidityPool", {})
            tvl = float(pool.get("totalValueLockedUSD") or 0)
            tokens = pool.get("inputTokens", [])
            symbols = [t["symbol"] for t in tokens]
            # ⚠️ tạm thời estimate value = balance (placeholder)
            # (sau này có thể tính chuẩn hơn bằng LP price)
            value_usd = balance  # 👉 MVP thôi

            positions.append({
                "position_id": f"{wallet}:{pool.get('id')}",
                "type": "gauge",
                "protocol": "curve",
                "pool_id": pool.get("id"),
                "pool": pool.get("name"),
                "asset": symbols,
                "lp_balance": round(balance, 8),
                "value_usd": round(value_usd, 4),  # fix
                "pool_tvl": round(tvl, 4),
            })

        return positions


    async def get_deposits(
        self,
        wallet: str = None,
        pool_id: str = None,
        limit: int = 100,
    ) -> list[dict]:
        where_parts = []
        if wallet:
            where_parts.append(f'from: "{wallet.lower()}"')
        if pool_id:
            where_parts.append(f'pool: "{pool_id.lower()}"')
        where_clause = ("where: { " + ", ".join(where_parts) + " }") if where_parts else ""

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
            from
            to
            amountUSD
            inputTokenAmounts
            liquidityPool {{
              id
              name
              inputTokens {{ symbol decimals }}
            }}
          }}
        }}
        """
        data = await self.query(self.url, query)
        return [self._format_lp_action(d, "deposit") for d in data.get("deposits", [])]

    async def get_withdraws(
        self,
        wallet: str = None,
        pool_id: str = None,
        limit: int = 100,
    ) -> list[dict]:
        """Lịch sử rút thanh khoản (Remove Liquidity). Lọc theo wallet hoặc pool."""
        where_parts = []
        if wallet:
            where_parts.append(f'from: "{wallet.lower()}"')
        if pool_id:
            where_parts.append(f'pool: "{pool_id.lower()}"')
        where_clause = ("where: { " + ", ".join(where_parts) + " }") if where_parts else ""

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
            from
            to
            amountUSD
            outputTokenAmounts
            liquidityPool {{
              id
              name
              inputTokens {{ symbol decimals }}
            }}
          }}
        }}
        """
        data = await self.query(self.url, query)
        return [self._format_lp_action(w, "withdraw") for w in data.get("withdraws", [])]

    async def get_swaps(
        self,
        wallet: str = None,
        pool_id: str = None,
        token_in: str = None,
        token_out: str = None,
        limit: int = 100,
    ) -> list[dict]:
        where_parts = []
        if wallet:
            where_parts.append(f'from: "{wallet.lower()}"')
        if pool_id:
            where_parts.append(f'pool: "{pool_id.lower()}"')
        if token_in:
            where_parts.append(f'tokenIn: "{token_in.lower()}"')
        if token_out:
            where_parts.append(f'tokenOut: "{token_out.lower()}"')
        where_clause = ("where: { " + ", ".join(where_parts) + " }") if where_parts else ""

        query = f"""
        {{
          swaps(
            first: {limit}
            orderBy: timestamp
            orderDirection: desc
            {where_clause}
          ) {{
            id
            timestamp
            from
            to
            tokenIn {{ symbol decimals id }}
            tokenOut {{ symbol decimals id }}
            amountIn
            amountOut
            amountInUSD
            amountOutUSD
            liquidityPool {{
              id
              name
            }}
          }}
        }}
        """
        data = await self.query(self.url, query)
        result = []
        for s in data.get("swaps", []):
            dec_in = int(s["tokenIn"].get("decimals") or 18)
            dec_out = int(s["tokenOut"].get("decimals") or 18)
            raw_in = float(s.get("amountIn") or 0)
            raw_out = float(s.get("amountOut") or 0)
            amount_in = raw_in / (10 ** dec_in) if raw_in > 1e10 else raw_in
            amount_out = raw_out / (10 ** dec_out) if raw_out > 1e10 else raw_out

            result.append({
                "tx_id": s["id"],
                "action": "swap",
                "timestamp": int(s.get("timestamp") or 0),
                "pool_id": s["liquidityPool"]["id"],
                "pool_name": s["liquidityPool"].get("name"),
                "from": s.get("from"),
                "to": s.get("to"),
                "token_in": s["tokenIn"]["symbol"],
                "token_in_address": s["tokenIn"]["id"],
                "token_out": s["tokenOut"]["symbol"],
                "token_out_address": s["tokenOut"]["id"],
                "amount_in": round(amount_in, 8),
                "amount_out": round(amount_out, 8),
                "amount_in_usd": round(float(s.get("amountInUSD") or 0), 4),
                "amount_out_usd": round(float(s.get("amountOutUSD") or 0), 4),
                # Volume = trung bình in/out để tránh double-count
                "volume_usd": round(
                    (float(s.get("amountInUSD") or 0) + float(s.get("amountOutUSD") or 0)) / 2, 4
                ),
            })
        return result

    # ─────────────────────────────────────────────
    # 3. POOLS
    # ─────────────────────────────────────────────

    async def get_pools(self, last_id: str = "", batch_size: int = 500) -> list[dict]:
        query = """
        query GetCurvePools($first: Int!, $last_id: ID!) {
          liquidityPools(
            first: $first
            where: { id_gt: $last_id }
            orderBy: id
            orderDirection: asc
          ) {
            id
            name
            totalValueLockedUSD
            cumulativeVolumeUSD
            inputTokens { id symbol decimals }
            rewardTokens { id symbol }
            dailySnapshots(
              first: 1
              orderBy: timestamp
              orderDirection: desc
            ) {
              timestamp
              dailyVolumeUSD
              dailySupplySideRevenueUSD
              totalValueLockedUSD
            }
          }
        }
        """
        data = await self.query(
            url=self.url,
            query=query,
            variables={"first": batch_size, "last_id": last_id},
        )

        pools = []
        for p in data.get("liquidityPools", []):
            tvl = float(p.get("totalValueLockedUSD") or 0)
            if tvl < self.MIN_POOL_TVL:
                continue

            staking_apr, apr_is_suspicious = self._calc_apr(p, tvl)
            symbols = [t["symbol"] for t in p.get("inputTokens", [])]
            reward_tokens = [
                {"id": r["id"], "symbol": r.get("symbol", "")}
                for r in p.get("rewardTokens", [])
            ]

            snapshots = p.get("dailySnapshots", [])
            volume_24h = float(snapshots[0].get("dailyVolumeUSD") or 0) if snapshots else 0.0

            pool_doc = {
                "_id": f"curve:{p['id']}",
                "address": p["id"],
                "protocol": "curve",
                "type": "staking",
                "name": p.get("name", ""),
                "token": symbols,
                "asset": symbols[0].lower() if symbols else "unknown",
                "tvl": round(tvl, 4),
                "volume_usd_all_time": round(float(p.get("cumulativeVolumeUSD") or 0), 4),
                "volume_usd_24h": round(volume_24h, 4),
                "staking_apr": round(staking_apr, 4),
                "reward_tokens": reward_tokens,
            }
            if apr_is_suspicious:
                pool_doc["apr_suspicious"] = True

            pools.append(pool_doc)

        return pools

    async def get_pool_detail(self, pool_id: str) -> dict:
        """Chi tiết đầy đủ của một pool cụ thể."""
        query = f"""
        {{
          liquidityPool(id: "{pool_id.lower()}") {{
            id
            name
            totalValueLockedUSD
            cumulativeVolumeUSD
            cumulativeSupplySideRevenueUSD
            cumulativeProtocolSideRevenueUSD
            inputTokens {{ id symbol decimals }}
            outputToken {{ id symbol decimals }}
            rewardTokens {{ id symbol }}
            fees {{
              feeType
              feePercentage
            }}
          }}
        }}
        """
        data = await self.query(self.url, query)
        p = data.get("liquidityPool")
        if not p:
            return {}

        return {
            "pool_id": p["id"],
            "name": p.get("name"),
            "tvl": round(float(p.get("totalValueLockedUSD") or 0), 4),
            "cumulative_volume_usd": round(float(p.get("cumulativeVolumeUSD") or 0), 4),
            "cumulative_supply_revenue_usd": round(float(p.get("cumulativeSupplySideRevenueUSD") or 0), 4),
            "cumulative_protocol_revenue_usd": round(float(p.get("cumulativeProtocolSideRevenueUSD") or 0), 4),
            "input_tokens": [
                {"address": t["id"], "symbol": t["symbol"], "decimals": int(t["decimals"])}
                for t in p.get("inputTokens", [])
            ],
            "lp_token": p.get("outputToken"),
            "reward_tokens": [{"id": r["id"], "symbol": r.get("symbol")} for r in p.get("rewardTokens", [])],
            "fees": [
                {"type": f.get("feeType"), "pct": round(float(f.get("feePercentage") or 0), 6)}
                for f in p.get("fees", [])
            ],
        }

    # ─────────────────────────────────────────────
    # 4. PROTOCOL STATS
    # ─────────────────────────────────────────────

    async def get_protocol_stats(self) -> dict:
        """Tổng quan toàn sàn Curve: TVL, volume, doanh thu tích lũy."""
        query = """
        {
          dexAmmProtocols(first: 1) {
            id
            name
            totalValueLockedUSD
            cumulativeVolumeUSD
            cumulativeSupplySideRevenueUSD
            cumulativeProtocolSideRevenueUSD
            cumulativeTotalRevenueUSD
            totalPoolCount
          }
        }
        """
        data = await self.query(self.url, query)
        protocols = data.get("dexAmmProtocols", [])
        if not protocols:
            return {}
        p = protocols[0]
        return {
            "protocol_id": p["id"],
            "name": p.get("name"),
            "total_pool_count": int(p.get("totalPoolCount") or 0),
            "total_tvl_usd": round(float(p.get("totalValueLockedUSD") or 0), 4),
            "cumulative_volume_usd": round(float(p.get("cumulativeVolumeUSD") or 0), 4),
            "cumulative_supply_revenue_usd": round(float(p.get("cumulativeSupplySideRevenueUSD") or 0), 4),
            "cumulative_protocol_revenue_usd": round(float(p.get("cumulativeProtocolSideRevenueUSD") or 0), 4),
            "cumulative_total_revenue_usd": round(float(p.get("cumulativeTotalRevenueUSD") or 0), 4),
        }

    async def get_subgraph_meta(self) -> dict:
        """Trạng thái sync của subgraph (block cuối cùng đã index)."""
        query = """
        {
          _meta {
            block { number hash }
            deployment
            hasIndexingErrors
          }
        }
        """
        data = await self.query(self.url, query)
        meta = data.get("_meta", {})
        block = meta.get("block", {})
        return {
            "block_number": block.get("number"),
            "block_hash": block.get("hash"),
            "deployment": meta.get("deployment"),
            "has_indexing_errors": meta.get("hasIndexingErrors", False),
        }

    # ─────────────────────────────────────────────
    # 5. SNAPSHOTS — Thống kê theo thời gian
    # ─────────────────────────────────────────────

    async def get_pool_daily_snapshots(
        self,
        pool_id: str,
        days: int = 30,
    ) -> list[dict]:
        """
        Dữ liệu theo ngày của một pool: TVL, volume 24h, phí, APR.
        Dùng để vẽ biểu đồ xu hướng.
        """
        query = f"""
        {{
          liquidityPoolDailySnapshots(
            first: {days}
            orderBy: timestamp
            orderDirection: desc
            where: {{ pool: "{pool_id.lower()}" }}
          ) {{
            timestamp
            totalValueLockedUSD
            dailyVolumeUSD
            dailySupplySideRevenueUSD
            dailyProtocolSideRevenueUSD
            dailyTotalRevenueUSD
            inputTokenBalances
            inputTokenWeights
          }}
        }}
        """
        data = await self.query(self.url, query)
        result = []
        for s in data.get("liquidityPoolDailySnapshots", []):
            tvl = float(s.get("totalValueLockedUSD") or 0)
            daily_rev = float(s.get("dailySupplySideRevenueUSD") or 0)
            apr = round((daily_rev * 365 / tvl) * 100, 4) if tvl > 0 else 0.0

            result.append({
                "timestamp": int(s.get("timestamp") or 0),
                "tvl_usd": round(tvl, 4),
                "volume_usd_24h": round(float(s.get("dailyVolumeUSD") or 0), 4),
                "supply_revenue_usd": round(daily_rev, 4),
                "protocol_revenue_usd": round(float(s.get("dailyProtocolSideRevenueUSD") or 0), 4),
                "total_revenue_usd": round(float(s.get("dailyTotalRevenueUSD") or 0), 4),
                "apr": apr,
                "input_token_balances": s.get("inputTokenBalances", []),
                "input_token_weights": s.get("inputTokenWeights", []),
            })
        return result

    async def get_pool_hourly_snapshots(
        self,
        pool_id: str,
        hours: int = 48,
    ) -> list[dict]:
        """Dữ liệu theo giờ của một pool (dùng cho chart ngắn hạn)."""
        query = f"""
        {{
          liquidityPoolHourlySnapshots(
            first: {hours}
            orderBy: timestamp
            orderDirection: desc
            where: {{ pool: "{pool_id.lower()}" }}
          ) {{
            timestamp
            totalValueLockedUSD
            hourlyVolumeUSD
            hourlySupplySideRevenueUSD
            hourlyProtocolSideRevenueUSD
          }}
        }}
        """
        data = await self.query(self.url, query)
        result = []
        for s in data.get("liquidityPoolHourlySnapshots", []):
            result.append({
                "timestamp": int(s.get("timestamp") or 0),
                "tvl_usd": round(float(s.get("totalValueLockedUSD") or 0), 4),
                "volume_usd_1h": round(float(s.get("hourlyVolumeUSD") or 0), 4),
                "supply_revenue_usd": round(float(s.get("hourlySupplySideRevenueUSD") or 0), 4),
                "protocol_revenue_usd": round(float(s.get("hourlyProtocolSideRevenueUSD") or 0), 4),
            })
        return result

    async def get_financials_daily(self, days: int = 30) -> list[dict]:
        """Chỉ số tài chính toàn sàn Curve theo ngày."""
        query = f"""
        {{
          financialsDailySnapshots(
            first: {days}
            orderBy: timestamp
            orderDirection: desc
          ) {{
            timestamp
            totalValueLockedUSD
            dailyVolumeUSD
            dailySupplySideRevenueUSD
            dailyProtocolSideRevenueUSD
            dailyTotalRevenueUSD
            cumulativeVolumeUSD
          }}
        }}
        """
        data = await self.query(self.url, query)
        result = []
        for s in data.get("financialsDailySnapshots", []):
            result.append({
                "timestamp": int(s.get("timestamp") or 0),
                "tvl_usd": round(float(s.get("totalValueLockedUSD") or 0), 4),
                "volume_usd_24h": round(float(s.get("dailyVolumeUSD") or 0), 4),
                "supply_revenue_usd": round(float(s.get("dailySupplySideRevenueUSD") or 0), 4),
                "protocol_revenue_usd": round(float(s.get("dailyProtocolSideRevenueUSD") or 0), 4),
                "total_revenue_usd": round(float(s.get("dailyTotalRevenueUSD") or 0), 4),
                "cumulative_volume_usd": round(float(s.get("cumulativeVolumeUSD") or 0), 4),
            })
        return result

    # ─────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────

    def _value_weighted(
        self,
        symbols: list[str],
        coin_balances: list[float],
        pool_tvl: float,
        lp_amount: float,
    ) -> float:
        if pool_tvl > 0 and lp_amount > 0:
            return lp_amount

        total_balance = sum(coin_balances)
        if total_balance == 0 or not symbols:
            return 0.0

        value = 0.0
        for symbol, balance in zip(symbols, coin_balances):
            if balance <= 0:
                continue
            price = self.pricing.get_price_safe(symbol, default=0.0)
            weight = balance / total_balance
            value += lp_amount * weight * price

        return round(value, 4)

    def _calc_apr(self, pool: dict, tvl: float) -> tuple[float, bool]:
        snapshots = pool.get("dailySnapshots", [])
        if not snapshots or tvl <= 0:
            return 0.0, False
        daily_revenue = float(snapshots[0].get("dailySupplySideRevenueUSD") or 0)
        apr = (daily_revenue * 365 / tvl) * 100
        is_suspicious = apr > self.MAX_APR_PCT
        return round(apr, 4), is_suspicious

    def _format_lp_action(self, item: dict, action_type: str) -> dict:
        """Chuẩn hoá output cho deposit / withdraw."""
        pool = item.get("liquidityPool", {})
        tokens = pool.get("inputTokens", [])
        symbols = [t["symbol"] for t in tokens]

        # inputTokenAmounts / outputTokenAmounts là list tương ứng với inputTokens
        amounts_raw = item.get("inputTokenAmounts") or item.get("outputTokenAmounts") or []
        amounts = []
        for i, t in enumerate(tokens):
            dec = int(t.get("decimals") or 18)
            raw = float(amounts_raw[i]) if i < len(amounts_raw) else 0.0
            amounts.append(round(raw / (10 ** dec) if raw > 1e10 else raw, 8))

        return {
            "tx_id": item["id"],
            "action": action_type,
            "timestamp": int(item.get("timestamp") or 0),
            "pool_id": pool.get("id"),
            "pool_name": pool.get("name"),
            "from": item.get("from"),
            "to": item.get("to"),
            "token": symbols,
            "amounts": amounts,
            "amount_usd": round(float(item.get("amountUSD") or 0), 4),
        }