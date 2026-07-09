import re
import time

from data_engine.providers.the_graph.the_graph import TheGraph
from data_engine.services.prices.pricing_service import PricingService, TokenNotFoundException
from shared.utils.uniswap_utils import calculate_amounts
from config import TheGraphConfig
from shared.utils.case_utils import keys_to_camel


class UniswapGraph(TheGraph):
    MIN_POOL_TVL = 10_000  # USD
    MIN_POSITION_VALUE_USD = 0.01

    def __init__(self, pricing: PricingService = None):
        super().__init__()
        self.pricing = pricing
        self.url = TheGraphConfig.UNISWAP_GRAPH

    def _is_supported_pair(self, token0: str, token1: str) -> bool:
        if not self.pricing:
            return True

        try:
            self.pricing.get_token_info(token0)
            self.pricing.get_token_info(token1)
            return True
        except TokenNotFoundException:
            return False

    async def get_pools(self,
        batch_size: int = 100,
        last_id: str = "",
        min_tvl: float = None, ) -> list[dict]:
        min_tvl = min_tvl or self.MIN_POOL_TVL

        today_ts = int(time.time() // 86400 * 86400)

        query = """
        query GetPools($first: Int!, $last_id: String!, $min_tvl: String!, $today: Int!) {
          pools(
            first: $first
            where: { id_gt: $last_id, totalValueLockedUSD_gt: $min_tvl }
            orderBy: id
          ) {
            id
            feeTier
            liquidity
            sqrtPrice
            token0Price
            token1Price
            totalValueLockedUSD
            createdAtTimestamp
            token0 { id symbol name decimals }
            token1 { id symbol name decimals }
            poolDayData(first: 8, orderBy: date, orderDirection: desc) {
              date
              volumeUSD
              feesUSD
              tvlUSD
            }
            poolHourData(first: 24, orderBy: periodStartUnix, orderDirection: desc) {
              periodStartUnix
              volumeUSD
              feesUSD
              tvlUSD
            }
          }
        }
        """

        data = await self.query(url=self.url, query=query, variables={
            "first": batch_size,
            "last_id": last_id,
            "min_tvl": str(min_tvl),
            "today": today_ts,
        }, )

        pools = []
        for p in data.get("pools", []):
            tvl = float(p.get("totalValueLockedUSD") or 0)
            if tvl < min_tvl:
                continue

            token0_symbol = p["token0"]["symbol"].upper()
            token1_symbol = p["token1"]["symbol"].upper()
            if not self._is_supported_pair(token0_symbol, token1_symbol):
                continue

            day_data = p.get("poolDayData") or []
            hour_data = p.get("poolHourData") or []
            fee_tier = int(p.get("feeTier") or 0)

            volume_24h = sum(float(row.get("volumeUSD") or 0) for row in hour_data)
            fees_24h = sum(float(row.get("feesUSD") or 0) for row in hour_data)
            if fees_24h <= 0 and volume_24h > 0:
                fees_24h = self._calc_fees_from_volume(volume_24h, fee_tier)
            if volume_24h <= 0 and day_data:
                volume_24h = float(day_data[0].get("volumeUSD") or 0)
            if fees_24h <= 0 and day_data:
                fees_24h = float(day_data[0].get("feesUSD") or 0)
                if fees_24h <= 0:
                    fees_24h = self._calc_fees_from_volume(float(day_data[0].get("volumeUSD") or 0), fee_tier)

            tvl_24h = self._avg_tvl(hour_data) or (float(day_data[0].get("tvlUSD") or 0) if day_data else tvl) or tvl
            fees_7d = sum(float(row.get("feesUSD") or 0) for row in day_data[:7])
            if fees_7d <= 0:
                fees_7d = sum(self._calc_fees_from_volume(float(row.get("volumeUSD") or 0), fee_tier) for row in day_data[:7])
            tvl_7d = self._avg_tvl(day_data[:7]) or tvl_24h

            fee_apr_24h = self._calc_fee_apr(fees_usd=fees_24h, tvl=tvl_24h, days=1)
            fee_apr_7d = self._calc_fee_apr(fees_usd=fees_7d, tvl=tvl_7d, days=max(len(day_data[:7]), 1))
            reward_apr = 0.0
            total_apr = fee_apr_24h + reward_apr

            pools.append(keys_to_camel({
                "_id": p["id"],
                "pool_id": p["id"],
                "dex": "uniswap",
                "token0": {
                    "address": p["token0"]["id"],
                    "symbol": token0_symbol,
                    "name": self._clean_name(p["token0"]["name"]),
                    "decimals": int(p["token0"]["decimals"]),
                },
                "token1": {
                    "address": p["token1"]["id"],
                    "symbol": token1_symbol,
                    "name": self._clean_name(p["token1"]["name"]),
                    "decimals": int(p["token1"]["decimals"]),
                },
                "token0_price": float(p.get("token0Price") or 0),
                "token1_price": float(p.get("token1Price") or 0),
                "tvl": round(tvl, 4),
                "volume_usd_24h": round(volume_24h, 4),
                "fees_usd_24h": round(fees_24h, 4),
                "fee_tier": fee_tier,
                "fee_apr_24h": round(fee_apr_24h, 4),
                "fee_apr_7d": round(fee_apr_7d, 4),
                "reward_apr": round(reward_apr, 4),
                "total_apr": round(total_apr, 4),
                "pool_apr": round(total_apr, 4),
                "apr_source": "uniswap_pool_hour_data_24h",
                "liquidity": p.get("liquidity", "0"),
                "created_at": int(p.get("createdAtTimestamp") or 0),
            }))

        return pools

    async def get_positions(self, wallet: str) -> list[dict]:
        query = f"""
        {{
          positions(where: {{ owner: "{wallet.lower()}" }}) {{
            id
            liquidity
            collectedFeesToken0
            collectedFeesToken1
            depositedToken0
            depositedToken1
            withdrawnToken0
            withdrawnToken1
            feeGrowthInside0LastX128
            feeGrowthInside1LastX128
            tickLower {{ tickIdx }}
            tickUpper {{ tickIdx }}
            pool {{
              id
              sqrtPrice
              feeTier
              token0Price
              token1Price
              token0 {{ symbol decimals }}
              token1 {{ symbol decimals }}
            }}
          }}
        }}
        """

        data = await self.query(self.url, query)
        positions = []

        for p in data.get("positions", []):
            liquidity = int(p.get("liquidity") or 0)
            if liquidity == 0:
                continue

            try:
                amount0_raw, amount1_raw = calculate_amounts(p)
            except Exception as exc:
                self.logger.warning(f"calculate_amounts failed: {exc}")
                continue

            token0 = p["pool"]["token0"]["symbol"].upper()
            token1 = p["pool"]["token1"]["symbol"].upper()
            if not self._is_supported_pair(token0, token1):
                self.logger.info(
                    "Uniswap position skipped unsupported pair position=%s pair=%s/%s",
                    p.get("id"),
                    token0,
                    token1,
                )
                continue

            dec0 = int(p["pool"]["token0"]["decimals"])
            dec1 = int(p["pool"]["token1"]["decimals"])

            amount0 = float(amount0_raw / (10 ** dec0))
            amount1 = float(amount1_raw / (10 ** dec1))

            try:
                price0 = self.pricing.get_price(token0)
                price1 = self.pricing.get_price(token1)
            except TokenNotFoundException as exc:
                self.logger.warning(f"Uniswap position: {exc}, skipping")
                continue

            price0 = float(price0)
            price1 = float(price1)

            value_usd = amount0 * price0 + amount1 * price1
            if value_usd < self.MIN_POSITION_VALUE_USD:
                self.logger.warning(
                    "Uniswap position skipped dust value position=%s pair=%s/%s value_usd=%s amount0=%s amount1=%s price0=%s price1=%s",
                    p.get("id"),
                    token0,
                    token1,
                    value_usd,
                    amount0,
                    amount1,
                    price0,
                    price1,
                )
                continue

            collected_fee0 = float(p.get("collectedFeesToken0") or 0)
            collected_fee1 = float(p.get("collectedFeesToken1") or 0)
            fee_usd = collected_fee0 * price0 + collected_fee1 * price1

            deposited0 = float(p.get("depositedToken0") or 0)
            deposited1 = float(p.get("depositedToken1") or 0)
            withdrawn0 = float(p.get("withdrawnToken0") or 0)
            withdrawn1 = float(p.get("withdrawnToken1") or 0)

            meta0 = self.pricing.get_metadata(token0)
            meta1 = self.pricing.get_metadata(token1)

            positions.append(keys_to_camel({
                "type": "amm",
                "protocol": "uniswap_v3",
                "position_id": p.get("id"),
                "pool_id": p["pool"].get("id"),
                "asset": [token0, token1],
                "amount0": round(amount0, 8),
                "amount1": round(amount1, 8),
                "value_usd": round(value_usd, 4),
                "liquidity": p.get("liquidity", "0"),
                "fee_tier": int(p["pool"].get("feeTier") or 0),
                "token0_decimals": dec0,
                "token1_decimals": dec1,
                "tick_lower": int(p["tickLower"]["tickIdx"]),
                "tick_upper": int(p["tickUpper"]["tickIdx"]),
                "token0_price": float(p["pool"].get("token0Price") or 0),
                "token1_price": float(p["pool"].get("token1Price") or 0),
                "deposited_token0": round(deposited0, 8),
                "deposited_token1": round(deposited1, 8),
                "withdrawn_token0": round(withdrawn0, 8),
                "withdrawn_token1": round(withdrawn1, 8),
                "collected_fee_usd": round(fee_usd, 4),
                "assets_metadata": [
                    {
                        "symbol": token0,
                        "image": meta0.get("image"),
                        "name": meta0.get("name")
                    },
                    {
                        "symbol": token1,
                        "image": meta1.get("image"),
                        "name": meta1.get("name")
                    },
                ],
            }))

        return positions

    async def get_pool_day_data(self, pool_id: str, days: int = 30, ) -> list[dict]:
        query = f"""
        {{
          poolDayDatas(
            first: {days}
            orderBy: date
            orderDirection: desc
            where: {{ pool: "{pool_id.lower()}" }}
          ) {{
            date
            volumeUSD
            feesUSD
            tvlUSD
            liquidity
            open
            high
            low
            close
          }}
        }}
        """
        data = await self.query(self.url, query)
        result = []
        for d in data.get("poolDayDatas", []):
            result.append(keys_to_camel({
                "date": int(d.get("date") or 0),
                "volume_usd": round(float(d.get("volumeUSD") or 0), 4),
                "fees_usd": round(float(d.get("feesUSD") or 0), 4),
                "tvl_usd": round(float(d.get("tvlUSD") or 0), 4),
                "liquidity": d.get("liquidity", "0"),
                "open": float(d.get("open") or 0),
                "high": float(d.get("high") or 0),
                "low": float(d.get("low") or 0),
                "close": float(d.get("close") or 0),
            }))
        return result

    async def get_token_day_data(self, token_address: str, days: int = 30, ) -> list[dict]:
        query = f"""
        {{
          tokenDayDatas(
            first: {days}
            orderBy: date
            orderDirection: desc
            where: {{ token: "{token_address.lower()}" }}
          ) {{
            date
            volumeUSD
            totalValueLockedUSD
            priceUSD
            open
            high
            low
            close
          }}
        }}
        """
        data = await self.query(self.url, query)
        result = []
        for d in data.get("tokenDayDatas", []):
            result.append(keys_to_camel({
                "date": int(d.get("date") or 0),
                "volume_usd": round(float(d.get("volumeUSD") or 0), 4),
                "tvl_usd": round(float(d.get("totalValueLockedUSD") or 0), 4),
                "price_usd": float(d.get("priceUSD") or 0),
                "open": float(d.get("open") or 0),
                "high": float(d.get("high") or 0),
                "low": float(d.get("low") or 0),
                "close": float(d.get("close") or 0),
            }))
        return result

    async def get_swaps(
        self,
        pool_id: str = None,
        wallet: str = None,
        token_address: str = None,
        limit: int = 100,
    ) -> list[dict]:
        where_parts = []
        if pool_id:
            where_parts.append(f'pool: "{pool_id.lower()}"')
        if wallet:
            addr = wallet.lower()
            where_parts.append(f'or: [{{ sender: "{addr}" }}, {{ recipient: "{addr}" }}]')
        if token_address:
            addr = token_address.lower()
            where_parts.append(
                f'pool_: {{ or: [{{ token0: "{addr}" }}, {{ token1: "{addr}" }}] }}'
            )

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
            sender
            recipient
            amount0
            amount1
            amountUSD
            sqrtPriceX96
            pool {{
              id
              feeTier
              token0 {{ symbol decimals }}
              token1 {{ symbol decimals }}
            }}
          }}
        }}
        """
        data = await self.query(self.url, query)
        result = []
        for s in data.get("swaps", []):
            result.append(keys_to_camel({
                "tx_id": s["id"],
                "timestamp": int(s.get("timestamp") or 0),
                "pool_id": s["pool"]["id"],
                "fee_tier": int(s["pool"].get("feeTier") or 0),
                "sender": s.get("sender"),
                "recipient": s.get("recipient"),
                "token0": s["pool"]["token0"]["symbol"],
                "token1": s["pool"]["token1"]["symbol"],
                "amount0": float(s.get("amount0") or 0),
                "amount1": float(s.get("amount1") or 0),
                "amount_usd": round(float(s.get("amountUSD") or 0), 4),
                "sqrt_price_x96": s.get("sqrtPriceX96"),
            }))
        return result

    async def get_mints(
        self,
        pool_id: str = None,
        wallet: str = None,
        limit: int = 100,
    ) -> list[dict]:
        where_parts = []
        if pool_id:
            where_parts.append(f'pool: "{pool_id.lower()}"')
        if wallet:
            where_parts.append(f'owner: "{wallet.lower()}"')
        where_clause = ("where: { " + ", ".join(where_parts) + " }") if where_parts else ""

        query = f"""
        {{
          mints(
            first: {limit}
            orderBy: timestamp
            orderDirection: desc
            {where_clause}
          ) {{
            id
            timestamp
            owner
            amount0
            amount1
            amountUSD
            tickLower
            tickUpper
            pool {{
              id
              feeTier
              token0 {{ symbol decimals }}
              token1 {{ symbol decimals }}
            }}
          }}
        }}
        """
        data = await self.query(self.url, query)
        result = []
        for m in data.get("mints", []):
            result.append(keys_to_camel({
                "tx_id": m["id"],
                "timestamp": int(m.get("timestamp") or 0),
                "pool_id": m["pool"]["id"],
                "owner": m.get("owner"),
                "token0": m["pool"]["token0"]["symbol"],
                "token1": m["pool"]["token1"]["symbol"],
                "amount0": float(m.get("amount0") or 0),
                "amount1": float(m.get("amount1") or 0),
                "amount_usd": round(float(m.get("amountUSD") or 0), 4),
                "tick_lower": int(m.get("tickLower") or 0),
                "tick_upper": int(m.get("tickUpper") or 0),
            }))
        return result

    async def get_burns(
        self,
        pool_id: str = None,
        wallet: str = None,
        limit: int = 100,
    ) -> list[dict]:
        where_parts = []
        if pool_id:
            where_parts.append(f'pool: "{pool_id.lower()}"')
        if wallet:
            where_parts.append(f'owner: "{wallet.lower()}"')
        where_clause = ("where: { " + ", ".join(where_parts) + " }") if where_parts else ""

        query = f"""
        {{
          burns(
            first: {limit}
            orderBy: timestamp
            orderDirection: desc
            {where_clause}
          ) {{
            id
            timestamp
            owner
            amount0
            amount1
            amountUSD
            tickLower
            tickUpper
            pool {{
              id
              feeTier
              token0 {{ symbol decimals }}
              token1 {{ symbol decimals }}
            }}
          }}
        }}
        """
        data = await self.query(self.url, query)
        result = []
        for b in data.get("burns", []):
            result.append(keys_to_camel({
                "tx_id": b["id"],
                "timestamp": int(b.get("timestamp") or 0),
                "pool_id": b["pool"]["id"],
                "owner": b.get("owner"),
                "token0": b["pool"]["token0"]["symbol"],
                "token1": b["pool"]["token1"]["symbol"],
                "amount0": float(b.get("amount0") or 0),
                "amount1": float(b.get("amount1") or 0),
                "amount_usd": round(float(b.get("amountUSD") or 0), 4),
                "tick_lower": int(b.get("tickLower") or 0),
                "tick_upper": int(b.get("tickUpper") or 0),
            }))
        return result

    async def get_collects(
        self,
        pool_id: str = None,
        wallet: str = None,
        limit: int = 100,
    ) -> list[dict]:
        """Lấy sự kiện thu phí (collect). Lọc theo pool hoặc wallet (owner)."""
        where_parts = []
        if pool_id:
            where_parts.append(f'pool: "{pool_id.lower()}"')
        if wallet:
            where_parts.append(f'owner: "{wallet.lower()}"')
        where_clause = ("where: { " + ", ".join(where_parts) + " }") if where_parts else ""

        query = f"""
        {{
          collects(
            first: {limit}
            orderBy: timestamp
            orderDirection: desc
            {where_clause}
          ) {{
            id
            timestamp
            owner
            amount0
            amount1
            amountUSD
            pool {{
              id
              feeTier
              token0 {{ symbol decimals }}
              token1 {{ symbol decimals }}
            }}
          }}
        }}
        """
        data = await self.query(self.url, query)
        result = []
        for c in data.get("collects", []):
            result.append(keys_to_camel({
                "tx_id": c["id"],
                "timestamp": int(c.get("timestamp") or 0),
                "pool_id": c["pool"]["id"],
                "owner": c.get("owner"),
                "token0": c["pool"]["token0"]["symbol"],
                "token1": c["pool"]["token1"]["symbol"],
                "amount0": float(c.get("amount0") or 0),
                "amount1": float(c.get("amount1") or 0),
                "amount_usd": round(float(c.get("amountUSD") or 0), 4),
            }))
        return result

    async def get_ticks(
        self,
        pool_id: str,
        batch_size: int = 200,
        last_id: str = "",
    ) -> list[dict]:
        query = f"""
        {{
          ticks(
            first: {batch_size}
            where: {{ pool: "{pool_id.lower()}", id_gt: "{last_id}" }}
            orderBy: id
          ) {{
            id
            tickIdx
            liquidityGross
            liquidityNet
            price0
            price1
          }}
        }}
        """
        data = await self.query(self.url, query)
        result = []
        for t in data.get("ticks", []):
            result.append(keys_to_camel({
                "tick_id": t["id"],
                "tick_idx": int(t.get("tickIdx") or 0),
                "liquidity_gross": t.get("liquidityGross", "0"),
                "liquidity_net": t.get("liquidityNet", "0"),
                "price0": float(t.get("price0") or 0),
                "price1": float(t.get("price1") or 0),
            }))
        return result

    async def get_all_ticks(self, pool_id: str, batch_size: int = 200) -> list[dict]:
        all_ticks = []
        last_id = ""
        while True:
            batch = await self.get_ticks(pool_id, batch_size=batch_size, last_id=last_id)
            if not batch:
                break
            all_ticks.extend(batch)
            last_id = batch[-1].get("tickId") or batch[-1].get("tick_id")
            if len(batch) < batch_size:
                break
        return all_ticks

    def _calc_fees_from_volume(self, volume_usd: float, fee_tier: int) -> float:
        if volume_usd <= 0 or fee_tier <= 0:
            return 0.0
        fee_rate = fee_tier / 1_000_000
        return volume_usd * fee_rate

    def _calc_fee_apr(self, fees_usd: float, tvl: float, days: int = 1) -> float:
        if tvl <= 0 or fees_usd <= 0 or days <= 0:
            return 0.0
        return (fees_usd * (365 / days) / tvl) * 100

    def _avg_tvl(self, rows: list[dict]) -> float:
        values = [float(row.get("tvlUSD") or 0) for row in rows if float(row.get("tvlUSD") or 0) > 0]
        if not values:
            return 0.0
        return sum(values) / len(values)

    @staticmethod
    def _clean_name(name: str) -> str:
        if not name:
            return ""
        name = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', name)
        name = re.sub(r'https?://\S+', '', name)
        return name.strip()
