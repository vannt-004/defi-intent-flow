import os

from web3 import Web3


class MongoDBConfig:
    CONNECTION_URL = os.getenv("CONNECTION_URL", 'mongodb://localhost:27017')
    DATABASE = os.getenv("DATABASE", 'defi-data')


class RedisConfig:
    CONNECTION_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    PORTFOLIO_STREAM = os.getenv("PORTFOLIO_STREAM", "portfolio:user-sync")
    PORTFOLIO_GROUP = os.getenv("PORTFOLIO_GROUP", "portfolio-sync-service")
    PORTFOLIO_CONSUMER = os.getenv("PORTFOLIO_CONSUMER", "portfolio-sync-1")
    GAS_FEE_STREAM = os.getenv("GAS_FEE_STREAM", "portfolio:gas-fee")
    GAS_FEE_GROUP = os.getenv("GAS_FEE_GROUP", "gas-fee-service")
    GAS_FEE_CONSUMER = os.getenv("GAS_FEE_CONSUMER", "gas-fee-1")


class CoinGeckoConfig:
    BASE_URL = os.getenv("COINGECKO_URL", "https://api.coingecko.com/api/v3")
    PRICE_CACHE_TTL_SECONDS = int(os.getenv("COINGECKO_PRICE_CACHE_TTL_SECONDS", "120"))
    PRICE_AT_TX_MAX_DELTA_SECONDS = int(os.getenv("PRICE_AT_TX_MAX_DELTA_SECONDS", "86400"))


class EtherscanConfig:
    BASE_URL = os.getenv("ETHERSCAN_URL", "https://api.etherscan.io/v2/api")
    API_KEY = os.getenv("ETHERSCAN_API_KEY", "")
    CHAIN_ID = os.getenv("ETHERSCAN_CHAIN_ID", "1")


class TheGraphConfig:
    BASE_URL = os.getenv("THE_GRAPH_URL")
    UNISWAP_GRAPH = os.getenv("UNISWAP_GRAPH")
    AAVE_GRAPH = os.getenv("AAVE_GRAPH")
    CURVE_GRAPH = os.getenv("CURVE_GRAPH")
    COMPOUND_GRAPH = os.getenv("COMPOUND_GRAPH")
    SPARK_GRAPH = os.getenv("SPARK_GRAPH")


class Web3Config:
    RPC_URL = os.getenv("RPC_URL", "https://ethereum-rpc.publicnode.com")
    W3 = Web3( Web3.HTTPProvider(RPC_URL))
    MULTICALL_ADDRESS = os.getenv("MULTICALL_ADDRESS", "0xcA11bde05977b3631167028862bE2a173976CA11")


class PortfolioSyncConfig:
    INITIAL_CASHFLOW_LOOKBACK_DAYS = int(os.getenv("INITIAL_CASHFLOW_LOOKBACK_DAYS", "180"))
    FULL_HISTORY_START_BLOCK = int(os.getenv("FULL_HISTORY_START_BLOCK", "0"))
    FULL_HISTORY_SYNTHETIC_BACKFILL_DAYS = int(os.getenv("FULL_HISTORY_SYNTHETIC_BACKFILL_DAYS", "180"))
    CASHFLOW_PROVIDER_EVENT_LIMIT = int(os.getenv("CASHFLOW_PROVIDER_EVENT_LIMIT", "1000"))


class AIConfig:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    INTENT_PROVIDER = os.getenv("INTENT_PROVIDER", "auto")
    GOOGLE_AI_STUDIO_API_KEY = os.getenv("GOOGLE_AI_STUDIO_API_KEY", "") or os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
    GOOGLE_AI_MODEL = os.getenv("GOOGLE_AI_MODEL", "gemini-2.5-flash")
    ASSISTANT_DEFAULT_LANGUAGE = os.getenv("ASSISTANT_DEFAULT_LANGUAGE", "English")
    ASSISTANT_PROVIDER_MODE = os.getenv("ASSISTANT_PROVIDER_MODE", "default").lower()
