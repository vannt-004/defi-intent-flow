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


class CoinGeckoConfig:
    BASE_URL = os.getenv("COINGECKO_URL", "https://api.coingecko.com/api/v3")


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
    W3 = Web3( Web3.HTTPProvider(os.getenv("RPC_URL", "https://ethereum-rpc.publicnode.com")))
    MULTICALL_ADDRESS = os.getenv("MULTICALL_ADDRESS", "0xcA11bde05977b3631167028862bE2a173976CA11")

    
    
