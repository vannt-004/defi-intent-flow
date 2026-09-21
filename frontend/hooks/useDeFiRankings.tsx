"use client";

import { useState, useEffect } from "react";
import { getRankedMarkets, MarketRankingPayload } from "@/services/market.api";

interface UseDeFiRankingsProps {
    profileOrMatrix: MarketRankingPayload["profile_or_matrix"];
    limit?: number;
    weights?: MarketRankingPayload["weights"];
}

const RANKING_CACHE_TTL_MS = 1000 * 60 * 5;
const rankingCache = new Map<string, { timestamp: number; pools: DeFiPool[] }>();


export interface DeFiPool {
    market_id: string;
    protocol: string;
    category: "yield" | "dex_liquidity" | "staking";
    symbol: string;
    tvl_usd: number;
    apr: number;
    feeApr24h?: number;
    feeApr7d?: number;
    rewardApr?: number;
    aprSource?: string;
    ahpMatchIndex: number;
    tier: string;
    flags: string[];
    raw_data: any;
}

const toUnifiedDeFiPool = (pool: any): DeFiPool => {
    const token0 = pool.token0?.symbol;
    const token1 = pool.token1?.symbol;
    const isPair = Boolean(token0 && token1);

    return {
        market_id: pool.market_id || pool.address || pool._id,
        protocol: pool.protocol || "unknown",
        category: pool.category || (pool.dex === "uniswap" ? "dex_liquidity" : "yield"),
        symbol: (isPair ? `${token0}/${token1}` : (pool.symbol || pool.asset || "UNKNOWN")).toUpperCase(),
        tvl_usd: Number(pool.tvl_usd ?? pool.tvl ?? 0),
        apr: Number(pool.apr ?? pool.total_apr ?? pool.supplyApr ?? pool.pool_apr ?? 0),
        feeApr24h: Number(pool.fee_apr_24h ?? pool.raw_data?.fee_apr_24h ?? 0),
        feeApr7d: Number(pool.fee_apr_7d ?? pool.raw_data?.fee_apr_7d ?? 0),
        rewardApr: Number(pool.reward_apr ?? pool.raw_data?.reward_apr ?? 0),
        aprSource: pool.apr_source ?? pool.raw_data?.apr_source,
        ahpMatchIndex: Number(pool.ahpMatchIndex ?? 0),
        tier: pool.tier || "Tier B",
        flags: Array.isArray(pool.flags) ? pool.flags : [],
        raw_data: pool.raw_data || pool
    };
};

export const useDeFiRankings = ({ profileOrMatrix, limit = 100, weights }: UseDeFiRankingsProps) => {
    const [pools, setPools] = useState<DeFiPool[]>([]);
    const [previousPools, setPreviousPools] = useState<DeFiPool[]>([]);
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const cacheKey = JSON.stringify({profileOrMatrix, limit, weights});
        const cached = rankingCache.get(cacheKey);
        if (cached && Date.now() - cached.timestamp < RANKING_CACHE_TTL_MS) {
            setPools(cached.pools);
            setPreviousPools(cached.pools);
            setIsLoading(false);
            setError(null);
            return;
        }

        const fetchRankings = async () => {
            setPreviousPools(pools);
            setIsLoading(true);
            setError(null);
            try {
                const rawData = await getRankedMarkets({
                    profile_or_matrix: profileOrMatrix,
                    limit: limit,
                    weights,
                });

                const normalizedPools = rawData.map(toUnifiedDeFiPool);
                rankingCache.set(cacheKey, {timestamp: Date.now(), pools: normalizedPools});
                setPools(normalizedPools);
            } catch (err: any) {
                console.error("Error in useDeFiRankings pipeline:", err);
                setError(err.message || "Failed to fetch DeFi rankings");
            } finally {
                setIsLoading(false);
            }
        };

        fetchRankings();
    }, [profileOrMatrix, limit, weights?.yield, weights?.safety, weights?.efficiency]);

    return { pools: isLoading && pools.length === 0 ? previousPools : pools, isLoading, error };
};
