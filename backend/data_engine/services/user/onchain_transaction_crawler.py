from datetime import datetime, timezone

from data_engine.providers.etherscan.etherscan import EtherscanClient
from data_engine.services.user.onchain_transaction_filter_service import OnchainTransactionFilterService
from shared.databases.mongo_client import MongoConnection
from shared.repositories.wallet_repository import WalletRepository
from shared.utils.logger_utils import get_logger


class OnchainTransactionCrawler:

    def __init__(self, etherscan: EtherscanClient | None = None):
        self.logger = get_logger(self.__class__.__name__)
        self.db = MongoConnection.get_database()
        self.wallet_repository = WalletRepository(self.db)
        self.filter_service = OnchainTransactionFilterService(self.db)
        self.etherscan = etherscan or EtherscanClient()

    async def close(self):
        await self.etherscan.close()

    async def crawl_wallet(
        self,
        wallet: str,
        start_block: int | None = None,
        end_block: int = 99999999,
        offset: int = 1000,
        from_ts: int | None = None,
        to_ts: int | None = None,
    ) -> dict:
        wallet = wallet.lower().strip()
        self.wallet_repository.add_wallet(wallet)

        if start_block is None:
            start_block = await self._start_block_for_timestamp(from_ts) if from_ts else 0

        rows, stats = await self.fetch_wallet_transactions(
            wallet=wallet,
            start_block=start_block,
            end_block=end_block,
            offset=offset,
            from_ts=from_ts,
            to_ts=to_ts,
        )

        self.logger.info(
            "[OnchainTransactionCrawler] wallet=%s start_block=%s from_ts=%s normal=%s erc20=%s supported=%s",
            wallet,
            start_block,
            from_ts,
            stats["normal_tx_count"],
            stats["erc20_transfer_count"],
            len(rows),
        )

        return {
            "wallet": wallet,
            "start_block": start_block,
            "end_block": end_block,
            "from_ts": from_ts,
            "to_ts": to_ts,
            "normal_tx_count": stats["normal_tx_count"],
            "erc20_transfer_count": stats["erc20_transfer_count"],
            "supported_count": len(rows),
        }

    async def fetch_wallet_transactions(
        self,
        wallet: str,
        start_block: int | None = 0,
        end_block: int = 99999999,
        offset: int = 1000,
        from_ts: int | None = None,
        to_ts: int | None = None,
    ) -> tuple[list[dict], dict]:
        wallet = wallet.lower().strip()
        if start_block is None:
            start_block = await self._start_block_for_timestamp(from_ts) if from_ts else 0

        normal_txs = await self._fetch_all(
            fetcher=self.etherscan.get_normal_transactions,
            wallet=wallet,
            start_block=start_block,
            end_block=end_block,
            offset=offset,
        )
        normal_txs = self._filter_by_timestamp(normal_txs, from_ts=from_ts, to_ts=to_ts)
        token_txs = await self._fetch_all(
            fetcher=self.etherscan.get_erc20_transfers,
            wallet=wallet,
            start_block=start_block,
            end_block=end_block,
            offset=offset,
        )
        token_txs = self._filter_by_timestamp(token_txs, from_ts=from_ts, to_ts=to_ts)

        gas_by_hash = {
            tx.get("hash"): self._gas_cost_eth(tx)
            for tx in normal_txs
            if tx.get("hash")
        }

        rows = self._normalize_native_transactions(wallet, normal_txs)
        rows.extend(self._normalize_erc20_transfers(wallet, token_txs, gas_by_hash))
        rows = self.filter_service.filter_and_label(rows)

        return rows, {
            "normal_tx_count": len(normal_txs),
            "erc20_transfer_count": len(token_txs),
        }

    async def crawl_active_wallets(self, limit: int = 1000) -> list[dict]:
        wallets = self.wallet_repository.get_active_wallets(limit=limit)
        results = []

        for wallet in wallets:
            try:
                results.append(await self.crawl_wallet(wallet))
            except Exception as exc:
                self.logger.exception("[OnchainTransactionCrawler] wallet=%s error=%s", wallet, exc)

        return results

    async def _fetch_all(self, fetcher, wallet: str, start_block: int, end_block: int, offset: int) -> list[dict]:
        page = 1
        rows = []

        while True:
            batch = await fetcher(
                address=wallet,
                start_block=start_block,
                end_block=end_block,
                page=page,
                offset=offset,
                sort="asc",
            )
            if not batch:
                break

            rows.extend(batch)
            if len(batch) < offset:
                break

            page += 1

        return rows

    async def _start_block_for_timestamp(self, from_ts: int | None) -> int:
        if not from_ts:
            return 0

        try:
            return await self.etherscan.get_block_number_by_timestamp(from_ts, closest="before")
        except Exception as exc:
            self.logger.warning(
                "[OnchainTransactionCrawler] block lookup failed from_ts=%s, falling back to timestamp filter from genesis: %s",
                from_ts,
                exc,
            )
            return 0

    def _filter_by_timestamp(
        self,
        rows: list[dict],
        from_ts: int | None = None,
        to_ts: int | None = None,
    ) -> list[dict]:
        if from_ts is None and to_ts is None:
            return rows

        filtered = []
        for row in rows:
            timestamp = int(row.get("timeStamp") or 0)
            if from_ts is not None and timestamp < from_ts:
                continue
            if to_ts is not None and timestamp > to_ts:
                continue
            filtered.append(row)
        return filtered

    def _normalize_native_transactions(self, wallet: str, transactions: list[dict]) -> list[dict]:
        rows = []

        for tx in transactions:
            value_raw = int(tx.get("value") or 0)
            if value_raw <= 0:
                continue

            direction = "in" if (tx.get("to") or "").lower() == wallet else "out"
            amount = value_raw / 1e18
            gas_cost_eth = self._gas_cost_eth(tx) if direction == "out" else 0.0

            rows.append({
                "wallet": wallet,
                "tx_hash": tx.get("hash"),
                "log_index": -1,
                "block_number": int(tx.get("blockNumber") or 0),
                "timestamp": int(tx.get("timeStamp") or 0),
                "asset_type": "native",
                "contract_address": None,
                "symbol": "ETH",
                "name": "Ethereum",
                "decimals": 18,
                "direction": direction,
                "action": "transfer_in" if direction == "in" else "transfer_out",
                "amount": amount,
                "amount_raw": str(value_raw),
                "from": (tx.get("from") or "").lower(),
                "to": (tx.get("to") or "").lower(),
                "gas_cost_eth": gas_cost_eth,
                "method_id": tx.get("methodId"),
                "function_name": tx.get("functionName"),
                "source": "etherscan",
                "updated_at": datetime.now(timezone.utc),
            })

        return rows

    def _normalize_erc20_transfers(self, wallet: str, transfers: list[dict], gas_by_hash: dict[str, float]) -> list[dict]:
        rows = []

        for tx in transfers:
            decimals = int(tx.get("tokenDecimal") or 18)
            value_raw = int(tx.get("value") or 0)
            if value_raw <= 0:
                continue

            direction = "in" if (tx.get("to") or "").lower() == wallet else "out"
            amount = value_raw / (10 ** decimals)
            gas_cost_eth = gas_by_hash.get(tx.get("hash"), 0.0) if direction == "out" else 0.0

            rows.append({
                "wallet": wallet,
                "tx_hash": tx.get("hash"),
                "log_index": int(tx.get("logIndex") or 0),
                "block_number": int(tx.get("blockNumber") or 0),
                "timestamp": int(tx.get("timeStamp") or 0),
                "asset_type": "erc20",
                "contract_address": (tx.get("contractAddress") or "").lower(),
                "symbol": (tx.get("tokenSymbol") or "").upper(),
                "name": tx.get("tokenName"),
                "decimals": decimals,
                "direction": direction,
                "action": "transfer_in" if direction == "in" else "transfer_out",
                "amount": amount,
                "amount_raw": str(value_raw),
                "from": (tx.get("from") or "").lower(),
                "to": (tx.get("to") or "").lower(),
                "gas_cost_eth": gas_cost_eth,
                "method_id": tx.get("methodId"),
                "function_name": tx.get("functionName"),
                "source": "etherscan",
                "updated_at": datetime.now(timezone.utc),
            })

        return rows

    def _gas_cost_eth(self, tx: dict) -> float:
        gas_used = int(tx.get("gasUsed") or 0)
        gas_price = int(tx.get("gasPrice") or 0)
        return (gas_used * gas_price) / 1e18
