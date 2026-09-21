"use client";

import {useEffect, useMemo, useState} from "react";
import Link from "next/link";
import {useSearchParams} from "next/navigation";
import { cn } from "@/utils/cn";
import { ui } from "@/styles/ui";
import { useDeFiRankings } from "@/hooks/useDeFiRankings";
import { formatMoney } from "@/utils/format";
import {
    Coins,
    LayoutDashboard,
    AlertTriangle,
    ArrowUpRight,
    SlidersHorizontal,
    ExternalLink,
    Minus,
    Plus
} from "lucide-react";
import {Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis} from "recharts";
import {TokenIcon} from "@/components/icon/TokenIcon";
import {TokenPairIcon} from "@/components/icon/TokenPairIcon";
import Skeleton from "@/components/common/Skeleton";
import {useTokenPriceHistory} from "@/hooks/useTokenPriceHistory";
import {useAgentFocus} from "@/components/assistant/AgentFocusContext";

type TabType = "assets" | "pools";
type MarketMode = "market" | "scoring";
type ProfileType = "safe" | "balanced" | "degen";
type AhpMode = ProfileType | "custom";
type AhpWeights = { yield: number; safety: number; efficiency: number };
type MarketDataState = {
    pools: any[];
    isLoading: boolean;
    isRefetching?: boolean;
    error: string | null;
};

type AssetOverview = {
    symbol: string;
    name: string;
    totalTvl: number;
    bestApr: number;
    protocols: string[];
    poolCount: number;
};

const tokenFocusKeys = (symbol?: string | null) => {
    const normalized = String(symbol || "").toUpperCase();
    if (!normalized) return ["token:unknown"];
    if (normalized === "ETH") return ["token:ETH", "token:WETH"];
    if (normalized === "WETH") return ["token:WETH", "token:ETH"];
    return [`token:${normalized}`];
};

const resolveAssetSymbol = (symbol: string, assets: AssetOverview[]) => {
    const normalized = symbol.toUpperCase();
    if (assets.some((asset) => asset.symbol === normalized)) return normalized;
    if (normalized === "ETH" && assets.some((asset) => asset.symbol === "WETH")) return "WETH";
    if (normalized === "WETH" && assets.some((asset) => asset.symbol === "ETH")) return "ETH";
    return normalized;
};

const formatCompactPrice = (value: number) => {
    if (value >= 1000) return `$${value.toLocaleString(undefined, {maximumFractionDigits: 0})}`;
    if (value >= 1) return `$${value.toLocaleString(undefined, {maximumFractionDigits: 2})}`;
    return `$${value.toLocaleString(undefined, {maximumFractionDigits: 6})}`;
};

function TokenPriceChart({symbol}: { symbol?: string }) {
    const {focusClass} = useAgentFocus();
    const {data, isPending, error} = useTokenPriceHistory(symbol, 30);
    const chartData = (data?.history ?? []).map((row) => ({
        ...row,
        label: row.timestamp ? new Date(row.timestamp * 1000).toLocaleDateString("en-US", {month: "short", day: "numeric"}) : "",
    }));
    const isUp = (data?.change30dPct ?? 0) >= 0;

    return (
        <div className={focusClass(tokenFocusKeys(symbol), "flex h-full flex-col transition-all duration-200")}>
            <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
                <div className="rounded-lg border border-violet-100 bg-violet-50/45 p-3 dark:border-violet-900/35 dark:bg-violet-950/15">
                    <p className="text-[10px] uppercase tracking-wider text-zinc-500">Price</p>
                    {isPending ? <Skeleton className="mt-1 h-5 w-20"/> : (
                        <p className={cn("mt-1 text-sm font-semibold tabular-nums", ui.text.heading)}>
                            {formatCompactPrice(data?.currentPrice ?? 0)}
                        </p>
                    )}
                </div>
                <div className="rounded-lg border border-violet-100 bg-violet-50/45 p-3 dark:border-violet-900/35 dark:bg-violet-950/15">
                    <p className="text-[10px] uppercase tracking-wider text-zinc-500">7D</p>
                    {isPending ? <Skeleton className="mt-1 h-5 w-16"/> : (
                        <p className={cn("mt-1 text-sm font-semibold tabular-nums", (data?.change7dPct ?? 0) >= 0 ? ui.text.up : ui.text.down)}>
                            {(data?.change7dPct ?? 0).toFixed(2)}%
                        </p>
                    )}
                </div>
                <div className="rounded-lg border border-violet-100 bg-violet-50/45 p-3 dark:border-violet-900/35 dark:bg-violet-950/15">
                    <p className="text-[10px] uppercase tracking-wider text-zinc-500">30D</p>
                    {isPending ? <Skeleton className="mt-1 h-5 w-16"/> : (
                        <p className={cn("mt-1 text-sm font-semibold tabular-nums", isUp ? ui.text.up : ui.text.down)}>
                            {(data?.change30dPct ?? 0).toFixed(2)}%
                        </p>
                    )}
                </div>
                <div className="rounded-lg border border-violet-100 bg-violet-50/45 p-3 dark:border-violet-900/35 dark:bg-violet-950/15">
                    <p className="text-[10px] uppercase tracking-wider text-zinc-500">Range</p>
                    {isPending ? <Skeleton className="mt-1 h-5 w-24"/> : (
                        <p className={cn("mt-1 text-sm font-semibold tabular-nums", ui.text.heading)}>
                            {formatCompactPrice(data?.low ?? 0)} - {formatCompactPrice(data?.high ?? 0)}
                        </p>
                    )}
                </div>
            </div>

            <div className="min-h-[260px] flex-1">
                {isPending ? (
                    <Skeleton className="h-[260px] w-full"/>
                ) : error || chartData.length < 2 ? (
                    <div className="flex h-[260px] items-center justify-center rounded-lg border border-dashed border-violet-100 text-sm text-zinc-500 dark:border-violet-900/40">
                        No price history available for {symbol}
                    </div>
                ) : (
                    <ResponsiveContainer width="100%" height={260}>
                        <AreaChart data={chartData} margin={{top: 10, right: 12, left: -18, bottom: 0}}>
                            <defs>
                                <linearGradient id="tokenPriceGrad" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#7c3aed" stopOpacity={0.2}/>
                                    <stop offset="95%" stopColor="#7c3aed" stopOpacity={0}/>
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(124,58,237,0.12)"/>
                            <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{fontSize: 10, fill: "#71717a"}}/>
                            <YAxis
                                tickFormatter={(value) => formatCompactPrice(Number(value)).replace("$", "")}
                                tickLine={false}
                                axisLine={false}
                                tick={{fontSize: 10, fill: "#71717a"}}
                                domain={["auto", "auto"]}
                            />
                            <Tooltip
                                contentStyle={{
                                    backgroundColor: "rgba(24,24,27,0.96)",
                                    border: "1px solid rgba(124,58,237,0.25)",
                                    borderRadius: "8px",
                                    color: "#f4f4f5",
                                }}
                                formatter={(value: any) => [formatCompactPrice(Number(value)), "Price"]}
                                labelStyle={{color: "#c4b5fd", fontWeight: 600}}
                            />
                            <Area
                                type="monotone"
                                dataKey="price"
                                stroke="#7c3aed"
                                strokeWidth={2}
                                fill="url(#tokenPriceGrad)"
                                activeDot={{r: 4}}
                            />
                        </AreaChart>
                    </ResponsiveContainer>
                )}
            </div>
        </div>
    );
}

function MarketsSkeleton() {
    return (
        <div className="flex flex-1 flex-col gap-3 p-3 md:p-4">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                <Skeleton className="h-[92px]"/>
                <Skeleton className="h-[92px]"/>
                <Skeleton className="h-[92px]"/>
            </div>

            <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
                <div className="flex gap-2">
                    <Skeleton className="h-10 w-36"/>
                    <Skeleton className="h-10 w-36"/>
                </div>
                <div className="flex gap-2">
                    <Skeleton className="h-9 w-24"/>
                    <Skeleton className="h-9 w-24"/>
                    <Skeleton className="h-9 w-24"/>
                </div>
                <Skeleton className="h-10 w-full xl:w-80"/>
            </div>

            <div className={cn(ui.card.base, "overflow-hidden p-4")}>
                <div className="mb-4 grid grid-cols-[1.4fr_0.8fr_0.8fr_0.8fr_1fr] gap-3">
                    <Skeleton className="h-8"/>
                    <Skeleton className="h-8"/>
                    <Skeleton className="h-8"/>
                    <Skeleton className="h-8"/>
                    <Skeleton className="h-8"/>
                </div>
                <div className="space-y-3">
                    {Array.from({length: 7}).map((_, index) => (
                        <div key={index} className="grid grid-cols-[1.4fr_0.8fr_0.8fr_0.8fr_1fr] gap-3">
                            <Skeleton className="h-12"/>
                            <Skeleton className="h-12"/>
                            <Skeleton className="h-12"/>
                            <Skeleton className="h-12"/>
                            <Skeleton className="h-12"/>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}

const PRESET_WEIGHTS: Record<ProfileType, { yield: number; safety: number; efficiency: number }> = {
    safe: {yield: 0.18, safety: 0.58, efficiency: 0.24},
    balanced: {yield: 0.45, safety: 0.30, efficiency: 0.25},
    degen: {yield: 0.68, safety: 0.10, efficiency: 0.22},
};

function getPoolUrl(pool: any) {
    const protocol = String(pool.protocol || "").toLowerCase();
    const raw = pool.raw_data || {};
    const marketId = pool.market_id || raw.market_id || raw.address || raw.pool_id;
    const tokenAddress = raw.tokenAddress || raw.address || raw.underlyingAddress;
    const symbol = String(pool.symbol || raw.asset || "").toUpperCase().replace("/", "-");

    if (protocol.includes("uniswap")) {
        const poolId = raw.pool_id || raw.id || marketId;
        return poolId ? `https://app.uniswap.org/explore/pools/ethereum/${poolId}` : "https://app.uniswap.org/explore/pools";
    }
    if (protocol.includes("aave")) {
        return tokenAddress
            ? `https://app.aave.com/reserve-overview/?underlyingAsset=${tokenAddress}&marketName=proto_mainnet_v3`
            : "https://app.aave.com/markets/";
    }
    if (protocol.includes("compound")) {
        return tokenAddress
            ? `https://app.compound.finance/markets/${tokenAddress}`
            : "https://app.compound.finance/markets";
    }
    return symbol ? `https://defillama.com/yields?token=${symbol}` : "https://defillama.com/yields";
}

function AhpModelPanel({
                           mode,
                           setMode,
                           draftMode,
                           setDraftMode,
                           weights,
                           draftWeights,
                           customWeights,
                           setCustomWeights,
                           onApply,
                           onReset,
                       }: {
    mode: AhpMode;
    setMode: (mode: AhpMode) => void;
    draftMode: AhpMode;
    setDraftMode: (mode: AhpMode) => void;
    weights: AhpWeights;
    draftWeights: AhpWeights;
    customWeights: AhpWeights;
    setCustomWeights: (weights: AhpWeights) => void;
    onApply: () => void;
    onReset: () => void;
}) {
    const setWeight = (key: keyof typeof customWeights, value: number) => {
        setCustomWeights({...customWeights, [key]: Math.max(0.05, Math.min(0.9, value))});
        setDraftMode("custom");
    };
    const bumpWeight = (key: keyof typeof customWeights, delta: number) => {
        setWeight(key, customWeights[key] + delta);
    };
    const profileCards: {key: AhpMode; label: string; description: string; weights?: AhpWeights}[] = [
        {key: "safe", label: "Capital Protect", description: "Prioritize deeper, safer markets.", weights: PRESET_WEIGHTS.safe},
        {key: "balanced", label: "Balanced", description: "Mix yield, safety, and usage.", weights: PRESET_WEIGHTS.balanced},
        {key: "degen", label: "Yield Hunter", description: "Rank high APR first.", weights: PRESET_WEIGHTS.degen},
        {key: "custom", label: "Custom", description: "Use your own scoring mix.", weights: draftWeights},
    ];
    const hasChanges = mode !== draftMode ||
        Math.round(weights.yield * 100) !== Math.round(draftWeights.yield * 100) ||
        Math.round(weights.safety * 100) !== Math.round(draftWeights.safety * 100) ||
        Math.round(weights.efficiency * 100) !== Math.round(draftWeights.efficiency * 100);
    void setMode;
    const guideRows = [
        {
            label: "Return Potential",
            weight: draftWeights.yield,
            metric: "APR/APY, LP fee APR",
            plain: "How much income the pool may generate.",
        },
        {
            label: "Market Safety",
            weight: draftWeights.safety,
            metric: "TVL, deposit depth, risk flags",
            plain: "How deep and stable the market looks.",
        },
        {
            label: "Capital Quality",
            weight: draftWeights.efficiency,
            metric: "Utilization, volume / TVL",
            plain: "Whether liquidity is actually being used.",
        },
    ];

    return (
        <div className={cn(ui.card.base, "p-3")}>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                <div>
                    <div className="flex items-center gap-2">
                        <SlidersHorizontal size={15} className="text-violet-500"/>
                        <p className={cn("text-sm font-semibold", ui.text.heading)}>Investor Scoring Model</p>
                    </div>
                </div>
            </div>

            <div className="grid gap-2 md:grid-cols-4">
                {profileCards.map((profile) => (
                    <button
                        key={profile.key}
                        onClick={() => setDraftMode(profile.key)}
                        className={cn(
                            "rounded-lg border p-3 text-left transition-colors",
                            draftMode === profile.key
                                ? "border border-violet-200 bg-violet-50 text-violet-800 hover:border-violet-300 hover:bg-violet-100 dark:border-violet-800/60 dark:bg-violet-950/35 dark:text-violet-200 dark:hover:bg-violet-900/25"
                                : "border-violet-100 bg-violet-50/45 text-zinc-600 hover:border-violet-300 hover:bg-violet-50 dark:border-violet-900/35 dark:bg-violet-950/15 dark:text-zinc-300"
                        )}
                    >
                        <p className="text-xs font-semibold">{profile.label}</p>
                        <p className={cn("mt-1 min-h-8 text-[11px]", draftMode === profile.key ? "text-violet-100" : "text-zinc-500")}>
                            {profile.description}
                        </p>
                        <div className="mt-2 flex gap-1">
                            {(["yield", "safety", "efficiency"] as const).map((key) => (
                                <span
                                    key={key}
                                    className={cn(
                                        "h-1.5 rounded-full",
                                        draftMode === profile.key ? "bg-white/80" : "bg-violet-500"
                                    )}
                                    style={{width: `${Math.max(12, Math.round((profile.weights?.[key] ?? 0) * 100))}%`}}
                                />
                            ))}
                        </div>
                    </button>
                ))}
            </div>

            <div className="mt-3 grid gap-2 lg:grid-cols-3">
                {[
                    {key: "yield" as const, label: "Return Potential", description: "APR/APY and LP fee income", short: "Yield"},
                    {key: "safety" as const, label: "Market Safety", description: "TVL depth and warning flags", short: "Safety"},
                    {key: "efficiency" as const, label: "Capital Quality", description: "Utilization and volume turnover", short: "Quality"},
                ].map((item) => (
                    <div key={item.key} className="rounded-lg border border-violet-100 bg-violet-50/45 px-3 py-2 dark:border-violet-900/35 dark:bg-violet-950/15">
                        <div className="flex items-center justify-between gap-2">
                            <div>
                                <p className={cn("text-xs font-semibold", ui.text.heading)}>{item.label}</p>
                                <p className="mt-0.5 text-[10px] text-zinc-500">{item.description}</p>
                            </div>
                            <span className="text-sm font-semibold tabular-nums text-violet-700 dark:text-violet-300">
                                {Math.round(draftWeights[item.key] * 100)}%
                            </span>
                        </div>
                        <div className="mt-3 flex items-center gap-2">
                            <button
                                onClick={() => bumpWeight(item.key, -0.05)}
                                className="flex h-8 w-8 items-center justify-center rounded-lg border border-violet-100 bg-white text-violet-600 hover:bg-violet-50 dark:border-violet-900/40 dark:bg-zinc-950"
                                aria-label={`Decrease ${item.short}`}
                            >
                                <Minus size={14}/>
                            </button>
                            <div className="h-2 flex-1 overflow-hidden rounded-full bg-violet-100 dark:bg-violet-950/40">
                                <div
                                    className="h-full rounded-full bg-violet-500 transition-all"
                                    style={{width: `${Math.round(draftWeights[item.key] * 100)}%`}}
                                />
                            </div>
                            <button
                                onClick={() => bumpWeight(item.key, 0.05)}
                                className="flex h-8 w-8 items-center justify-center rounded-lg border border-violet-100 bg-white text-violet-600 hover:bg-violet-50 dark:border-violet-900/40 dark:bg-zinc-950"
                                aria-label={`Increase ${item.short}`}
                            >
                                <Plus size={14}/>
                            </button>
                        </div>
                    </div>
                ))}
            </div>

            <div className="mt-2 grid gap-2 text-[11px] md:grid-cols-3">
                {guideRows.map((row) => (
                    <div key={row.label} className="rounded-md bg-violet-50/50 px-2.5 py-1.5 text-zinc-500 dark:bg-violet-950/20">
                        <span className="font-semibold text-violet-700 dark:text-violet-300">{row.label}</span>
                        <span> · {row.metric}</span>
                    </div>
                ))}
            </div>

            <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-violet-100 pt-3 dark:border-violet-900/40">
                <p className="text-[11px] text-zinc-500">
                    Apply to refresh ranking. Weight changes are local until applied.
                </p>
                <div className="flex gap-2">
                    <button
                        onClick={onReset}
                        disabled={!hasChanges}
                        className="rounded-lg border border-violet-100 px-3 py-1.5 text-xs font-semibold text-zinc-500 transition-colors hover:bg-violet-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-violet-900/40 dark:hover:bg-violet-950/30"
                    >
                        Reset
                    </button>
                    <button
                        onClick={onApply}
                        disabled={!hasChanges}
                        className="rounded-lg border border-violet-200 bg-violet-50 px-4 py-1.5 text-xs font-semibold text-violet-800 transition-colors hover:border-violet-300 hover:bg-violet-100 dark:border-violet-800/60 dark:bg-violet-950/35 dark:text-violet-200 dark:hover:bg-violet-900/25 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        Apply model
                    </button>
                </div>
            </div>
        </div>
    );
}

function MarketPoolCard({pool}: { pool: any }) {
    const {focusClass} = useAgentFocus();
    const pairSymbols = [
        pool.raw_data?.token0?.symbol,
        pool.raw_data?.token1?.symbol,
    ].filter(Boolean);
    const displaySymbols = pairSymbols.length === 2 ? pairSymbols : String(pool.symbol || "").split("/");
    const primarySymbol = displaySymbols[0] || pool.symbol || "";
    const isLp = pool.category === "dex_liquidity";
    const hasFlags = pool.flags && pool.flags.length > 0;
    const focusKeys = [
        `pool:${pool.market_id || ""}`,
        ...displaySymbols.filter(Boolean).flatMap((symbol: string) => tokenFocusKeys(symbol)),
    ];

    return (
        <div className={focusClass(focusKeys, "rounded-xl border border-violet-100 bg-white/80 p-4 transition-all hover:border-violet-300 hover:shadow-sm dark:border-violet-900/40 dark:bg-zinc-950/40 dark:hover:bg-violet-950/15")}>
            <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 items-center gap-3">
                    {displaySymbols.length === 2 ? (
                        <TokenPairIcon symbols={displaySymbols} size={38}/>
                    ) : (
                        <TokenIcon symbol={pool.symbol || "LP"} size={36}/>
                    )}
                    <div className="min-w-0">
                        <p className={cn("truncate text-base font-semibold uppercase", ui.text.heading)}>{pool.symbol}</p>
                        <p className="mt-0.5 text-[11px] font-semibold uppercase tracking-wide text-violet-500 dark:text-violet-400">
                            {pool.protocol}
                        </p>
                    </div>
                </div>
                <span className={cn(
                    "shrink-0 rounded-md border px-2 py-1 text-[10px] font-semibold uppercase",
                    isLp
                        ? "border-violet-200 bg-violet-50 text-violet-700 dark:border-violet-900/50 dark:bg-violet-950/30 dark:text-violet-300"
                        : "border-purple-200 bg-purple-50 text-purple-700 dark:border-purple-900/50 dark:bg-purple-950/30 dark:text-purple-300"
                )}>
                    {isLp ? "AMM LP" : "Lending"}
                </span>
            </div>

            <div className="mt-4 grid grid-cols-3 gap-2">
                <MarketMetric label="TVL" value={formatMoney(pool.tvl_usd || 0)}/>
                <MarketMetric label="APR" value={`${Number(pool.apr || 0).toFixed(2)}%`} tone="up"/>
                <MarketMetric label="Fit" value={`${pool.ahpMatchIndex ?? 0}%`}/>
            </div>

            {isLp && (
                <p className="mt-3 text-[11px] text-zinc-500">
                    Fee 24h {pool.feeApr24h?.toFixed(2) ?? "0.00"}%
                    {(pool.rewardApr ?? 0) > 0 ? ` + reward ${pool.rewardApr?.toFixed(2)}%` : ""}
                </p>
            )}

            <div className="mt-3 flex min-h-6 flex-wrap gap-1">
                {hasFlags ? pool.flags.slice(0, 3).map((flag: string) => (
                    <span key={flag} className="rounded bg-red-50 px-1.5 py-0.5 text-[9px] font-semibold uppercase text-red-600 dark:bg-red-950/30 dark:text-red-300">
                        {flag.replace("_", " ")}
                    </span>
                )) : (
                    <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[9px] font-semibold uppercase text-emerald-600 dark:bg-emerald-950/30 dark:text-emerald-300">
                        Clear
                    </span>
                )}
            </div>

            <div className="mt-4 flex flex-wrap gap-2 border-t border-violet-100 pt-3 dark:border-violet-900/40">
                <Link
                    href={`/simulator?mode=${isLp ? "provide_liquidity" : "lend"}&symbol=${encodeURIComponent(primarySymbol)}&marketId=${encodeURIComponent(pool.market_id || "")}`}
                    className="inline-flex flex-1 items-center justify-center gap-1 rounded-lg border border-violet-200 bg-violet-50 px-3 py-2 text-xs font-semibold text-violet-800 transition-colors hover:border-violet-300 hover:bg-violet-100 dark:border-violet-800/60 dark:bg-violet-950/35 dark:text-violet-200 dark:hover:bg-violet-900/25"
                >
                    Simulate
                </Link>
                <a
                    href={getPoolUrl(pool)}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center justify-center gap-1 rounded-lg border border-violet-100 bg-white px-3 py-2 text-xs font-semibold text-violet-700 transition-colors hover:bg-violet-50 dark:border-violet-900/40 dark:bg-zinc-950 dark:text-violet-300 dark:hover:bg-violet-950/30"
                >
                    Market <ArrowUpRight size={12}/>
                </a>
            </div>
        </div>
    );
}

function MarketMetric({label, value, tone}: { label: string; value: string; tone?: "up" }) {
    return (
        <div className="rounded-lg border border-violet-100 bg-violet-50/45 px-2.5 py-2 dark:border-violet-900/35 dark:bg-violet-950/15">
            <p className="text-[9px] uppercase tracking-wider text-zinc-500">{label}</p>
            <p className={cn("mt-1 truncate text-xs font-semibold tabular-nums", tone === "up" ? ui.text.up : ui.text.heading)}>
                {value}
            </p>
        </div>
    );
}

export default function MarketsPage() {
    const searchParams = useSearchParams();
    const {focusClass} = useAgentFocus();
    const [ahpMode, setAhpMode] = useState<AhpMode>("balanced");
    const [draftAhpMode, setDraftAhpMode] = useState<AhpMode>("balanced");
    const [appliedCustomWeights, setAppliedCustomWeights] = useState<AhpWeights>({yield: 0.45, safety: 0.30, efficiency: 0.25});
    const [draftCustomWeights, setDraftCustomWeights] = useState<AhpWeights>({yield: 0.45, safety: 0.30, efficiency: 0.25});
    const [activeTab, setActiveTab] = useState<TabType>("pools");
    const [marketMode, setMarketMode] = useState<MarketMode>("market");
    const [search, setSearch] = useState("");
    const [selectedAssetSymbol, setSelectedAssetSymbol] = useState<string | undefined>();

    const normalizedAppliedWeights = useMemo(() => {
        const total = appliedCustomWeights.yield + appliedCustomWeights.safety + appliedCustomWeights.efficiency;
        return {
            yield: appliedCustomWeights.yield / total,
            safety: appliedCustomWeights.safety / total,
            efficiency: appliedCustomWeights.efficiency / total,
        };
    }, [appliedCustomWeights]);
    const normalizedDraftWeights = useMemo(() => {
        const total = draftCustomWeights.yield + draftCustomWeights.safety + draftCustomWeights.efficiency;
        return {
            yield: draftCustomWeights.yield / total,
            safety: draftCustomWeights.safety / total,
            efficiency: draftCustomWeights.efficiency / total,
        };
    }, [draftCustomWeights]);
    const effectiveWeights = ahpMode === "custom" ? normalizedAppliedWeights : PRESET_WEIGHTS[ahpMode];
    const draftEffectiveWeights = draftAhpMode === "custom" ? normalizedDraftWeights : PRESET_WEIGHTS[draftAhpMode];

    const marketData: MarketDataState = useDeFiRankings({
        profileOrMatrix: ahpMode === "custom" ? "balanced" : ahpMode,
        weights: ahpMode === "custom" ? effectiveWeights : undefined,
    });
    const pools = marketData.pools ?? [];
    const isInitialLoading = marketData.isLoading && pools.length === 0;
    const isRankingLoading = marketData.isLoading && pools.length > 0;
    const error = marketData.error;

    const applyAhpModel = () => {
        setAhpMode(draftAhpMode);
        setAppliedCustomWeights(draftCustomWeights);
    };

    const resetDraftAhpModel = () => {
        setDraftAhpMode(ahpMode);
        setDraftCustomWeights(appliedCustomWeights);
    };

    const assetsData = useMemo<AssetOverview[]>(() => {
        const bySymbol = new Map<string, AssetOverview>();

        pools.forEach((pool) => {
            const pairSymbols = [
                pool.raw_data?.token0?.symbol,
                pool.raw_data?.token1?.symbol,
            ].filter(Boolean).map((symbol: string) => symbol.toUpperCase());
            const tokenSymbols = pairSymbols.length === 2
                ? pairSymbols
                : [String(pool.symbol || "UNKNOWN").split("/")[0].toUpperCase()];
            const tvlShare = (pool.tvl_usd || 0) / Math.max(tokenSymbols.length, 1);

            tokenSymbols.forEach((symbol) => {
                const current: AssetOverview = bySymbol.get(symbol) ?? {
                    symbol,
                    name: pool.raw_data?.name || symbol,
                    totalTvl: 0,
                    bestApr: 0,
                    protocols: [],
                    poolCount: 0,
                };

                current.totalTvl += tvlShare;
                current.bestApr = Math.max(current.bestApr, pool.apr || 0);
                current.poolCount += 1;
                if (!current.protocols.includes(pool.protocol)) {
                    current.protocols.push(pool.protocol);
                }
                bySymbol.set(symbol, current);
            });
        });

        return Array.from(bySymbol.values()).sort((a, b) => b.totalTvl - a.totalTvl);
    }, [pools]);

    const filteredAssets = assetsData.filter((asset) =>
        asset.symbol.toLowerCase().includes(search.toLowerCase()) ||
        asset.protocols.some((protocol) => protocol.toLowerCase().includes(search.toLowerCase()))
    );

    const selectedAsset = filteredAssets.find((asset) => asset.symbol === selectedAssetSymbol) ?? filteredAssets[0];

    useEffect(() => {
        const focusFromUrl = searchParams.get("agentFocus");
        if (focusFromUrl?.startsWith("token:")) {
            const focusedSymbol = resolveAssetSymbol(focusFromUrl.replace("token:", ""), assetsData);
            setActiveTab("assets");
            setSelectedAssetSymbol(focusedSymbol);
            return;
        }
        if (focusFromUrl?.startsWith("pool:")) {
            setActiveTab("pools");
            setMarketMode("market");
            setSearch("");
            return;
        }
        if (focusFromUrl === "market:overview") {
            setActiveTab("pools");
            return;
        }

        const symbolFromUrl = searchParams.get("symbol")?.toUpperCase();
        if (symbolFromUrl) {
            setActiveTab("assets");
            setSelectedAssetSymbol(resolveAssetSymbol(symbolFromUrl, assetsData));
            return;
        }
        if (!selectedAssetSymbol && assetsData.length) {
            setSelectedAssetSymbol(assetsData[0].symbol);
        }
    }, [assetsData, searchParams, selectedAssetSymbol]);

    if (isInitialLoading) {
        return <MarketsSkeleton/>;
    }

    if (error) {
        return (
            <div className="flex flex-1 items-center justify-center p-8 text-sm font-medium text-red-500 gap-2">
                <AlertTriangle size={16} />
                <span>Error loading ranked market data: {String(error)}</span>
            </div>
        );
    }

    // 1. Tìm các thông số Global dựa trên mô hình dữ liệu chuẩn hóa
    const globalTvl = pools.reduce((s, p) => s + (p.tvl_usd || 0), 0);
    const topApr = pools.length > 0 ? Math.max(...pools.map(p => p.apr || 0)) : 0;

    // 3. Thực hiện bộ lọc tìm kiếm trên tập dữ liệu đã sắp xếp sẵn theo thuật toán AHP từ Backend
    const filteredPools = pools.filter(p =>
        (p.symbol || "").toLowerCase().includes(search.toLowerCase()) ||
        (p.protocol || "").toLowerCase().includes(search.toLowerCase())
    );

    return (
        <div className="flex flex-1 flex-col gap-4 p-4 md:p-5">
            {/* TOP STATISTICS CARDS */}
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                <div className={focusClass("market:overview", cn(ui.card.base, "border-l-4 border-l-violet-500 p-3 transition-all duration-200"))}>
                    <p className="text-[10px] font-semibold uppercase text-zinc-500 tracking-wider">Global Market TVL</p>
                    <p className={cn("mt-1 text-xl font-semibold tabular-nums", ui.text.heading)}>{formatMoney(globalTvl)}</p>
                </div>
                <div className={focusClass("market:overview", cn(ui.card.base, "border-l-4 border-l-violet-400 p-3 transition-all duration-200"))}>
                    <p className="text-[10px] font-semibold uppercase text-zinc-500 tracking-wider">Active Opportunities</p>
                    <p className={cn("mt-1 text-xl font-semibold tabular-nums", ui.text.heading)}>{pools.length} Pools</p>
                </div>
                <div className={focusClass("market:overview", cn(ui.card.base, "border-l-4 border-l-emerald-500 p-3 transition-all duration-200"))}>
                    <p className="text-[10px] font-semibold uppercase text-zinc-500 tracking-wider">Top Market APR</p>
                    <p className="mt-1 text-xl font-semibold tabular-nums text-emerald-600 dark:text-emerald-400">{topApr.toFixed(2)}%</p>
                </div>
            </div>

            {activeTab === "pools" && marketMode === "scoring" && (
                <AhpModelPanel
                    mode={ahpMode}
                    setMode={setAhpMode}
                    draftMode={draftAhpMode}
                    setDraftMode={setDraftAhpMode}
                    weights={effectiveWeights}
                    draftWeights={draftEffectiveWeights}
                    customWeights={draftCustomWeights}
                    setCustomWeights={setDraftCustomWeights}
                    onApply={applyAhpModel}
                    onReset={resetDraftAhpModel}
                />
            )}

            {/* CONTROL BAR: TABS, PROFILES & FILTERS */}
            <div className="flex flex-col gap-3">
                <div className="flex flex-col justify-between gap-3 xl:flex-row xl:items-center">
                    {/* View Tabs */}
                    <div className="flex w-fit rounded-lg border border-violet-100 bg-violet-50/60 p-1 dark:border-violet-900/40 dark:bg-violet-950/20">
                        <button
                            onClick={() => setActiveTab("pools")}
                            className={cn("flex items-center gap-2 rounded-md px-4 py-2 text-xs font-semibold transition-all",
                                activeTab === "pools" ? "border border-violet-200 bg-violet-50 text-violet-800 dark:border-violet-800/60 dark:bg-violet-950/35 dark:text-violet-200" : "text-zinc-500 hover:bg-violet-50/70 hover:text-violet-700 dark:hover:bg-violet-950/25 dark:hover:text-violet-300")}
                        >
                            <LayoutDashboard size={14} /> Markets & Pools
                        </button>
                        <button
                            onClick={() => setActiveTab("assets")}
                            className={cn("flex items-center gap-2 rounded-md px-4 py-2 text-xs font-semibold transition-all",
                                activeTab === "assets" ? "border border-violet-200 bg-violet-50 text-violet-800 dark:border-violet-800/60 dark:bg-violet-950/35 dark:text-violet-200" : "text-zinc-500 hover:bg-violet-50/70 hover:text-violet-700 dark:hover:bg-violet-950/25 dark:hover:text-violet-300")}
                        >
                            <Coins size={14} /> Assets Overview
                        </button>
                    </div>

                    {activeTab === "pools" && (
                        <div className="flex w-fit rounded-lg border border-violet-100 bg-violet-50/60 p-1 dark:border-violet-900/40 dark:bg-violet-950/20">
                            {[
                                {key: "market" as MarketMode, label: "Market Cards"},
                                {key: "scoring" as MarketMode, label: "Scoring"},
                            ].map((item) => (
                                <button
                                    key={item.key}
                                    onClick={() => setMarketMode(item.key)}
                                    className={cn("rounded-md px-3 py-2 text-xs font-semibold transition-all",
                                        marketMode === item.key ? "border border-violet-200 bg-violet-50 text-violet-800 dark:border-violet-800/60 dark:bg-violet-950/35 dark:text-violet-200" : "text-zinc-500 hover:bg-violet-50/70 hover:text-violet-700 dark:hover:bg-violet-950/25 dark:hover:text-violet-300")}
                                >
                                    {item.label}
                                </button>
                            ))}
                        </div>
                    )}

                    {/* Search Field */}
                    <div className="flex flex-1 items-center gap-2 xl:max-w-xs">
                        <div className={cn(ui.card.base, "flex flex-1 items-center gap-2 px-3 py-2")}>
                            <input
                                className="w-full bg-transparent text-xs text-zinc-900 outline-none placeholder:text-zinc-400 dark:text-zinc-100"
                                placeholder={`Filter by asset or protocol...`}
                                value={search}
                                onChange={e => setSearch(e.target.value)}
                            />
                        </div>
                    </div>
                </div>
            </div>

            {/* UNIFIED DATA TABLE CONTAINER */}
            <div className={cn(ui.card.base, "min-h-0 overflow-hidden")}>
                {activeTab === "pools" ? (
                    marketMode === "market" ? (
                        <div className="p-4">
                            {isRankingLoading && (
                                <div className="mb-3 rounded-lg border border-violet-100 bg-violet-50/70 px-4 py-3 text-xs font-semibold text-violet-700 dark:border-violet-900/40 dark:bg-violet-950/30 dark:text-violet-300">
                                    Updating market data...
                                </div>
                            )}
                            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                                <div>
                                    <p className={cn("text-sm font-semibold", ui.text.heading)}>Market Cards</p>
                                    <p className={cn("mt-1 text-xs", ui.text.muted)}>
                                        Browse investable lending and LP markets first. Use Scoring mode when you want to tune ranking weights.
                                    </p>
                                </div>
                                <span className="rounded-md bg-violet-50 px-2 py-1 text-[10px] font-semibold text-violet-700 dark:bg-violet-950/30 dark:text-violet-300">
                                    {filteredPools.length} markets
                                </span>
                            </div>
                            <div className="max-h-[640px] overflow-y-auto pr-1">
                                <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
                                    {filteredPools.map((pool) => (
                                        <MarketPoolCard key={pool.market_id} pool={pool}/>
                                    ))}
                                </div>
                            </div>
                        </div>
                    ) : (
                    <div className="overflow-x-auto">
                        {isRankingLoading && (
                            <div className="border-b border-violet-100 bg-violet-50/70 px-5 py-3 text-xs font-semibold text-violet-700 dark:border-violet-900/40 dark:bg-violet-950/30 dark:text-violet-300">
                                Updating ranking with applied model...
                            </div>
                        )}
                        <div className="max-h-[560px] overflow-y-auto">
                        <table className="w-full border-collapse text-left">
                            <thead className="sticky top-0 z-10 border-b border-violet-100 bg-violet-50 text-[10px] font-semibold uppercase tracking-wider text-zinc-500 dark:border-violet-900/40 dark:bg-violet-950">
                            <tr>
                                <th className="px-4 py-2.5">Rank / Asset</th>
                                <th className="px-4 py-2.5">Category</th>
                                <th className="px-4 py-2.5 text-right">TVL</th>
                                <th className="px-4 py-2.5 text-right text-emerald-600 dark:text-emerald-400">APR / APY</th>
                                <th className="px-4 py-2.5 text-center">Fit Score</th>
                                <th className="px-4 py-2.5 text-center">Market Notes</th>
                                <th className="px-4 py-2.5 text-center">Open</th>
                            </tr>
                            </thead>
                            <tbody className="divide-y divide-violet-50 dark:divide-violet-900/30">
                            {filteredPools.map((pool, index) => {
                                const hasFlags = pool.flags && pool.flags.length > 0;
                                const pairSymbols = [
                                    pool.raw_data?.token0?.symbol,
                                    pool.raw_data?.token1?.symbol,
                                ].filter(Boolean);
                                const displaySymbols = pairSymbols.length === 2 ? pairSymbols : String(pool.symbol || "").split("/");
                                const rowFocusKeys = [
                                    `pool:${pool.market_id || ""}`,
                                    ...displaySymbols.filter(Boolean).flatMap((symbol: string) => tokenFocusKeys(symbol)),
                                ];
                                return (
                                    <tr key={pool.market_id} className={focusClass(rowFocusKeys, cn("transition-all duration-200", hasFlags ? "bg-red-50/30 hover:bg-red-50 dark:bg-red-950/10 dark:hover:bg-red-950/20" : "hover:bg-violet-50/50 dark:hover:bg-violet-950/20"))}>
                                        {/* Rank & Asset info */}
                                        <td className="px-4 py-3">
                                            <div className="flex items-center gap-3">
                                                <span className="text-xs font-mono text-zinc-500 font-bold">#{index + 1}</span>
                                                {displaySymbols.length === 2 ? (
                                                    <TokenPairIcon symbols={displaySymbols} size={34}/>
                                                ) : (
                                                    <TokenIcon symbol={pool.symbol || "LP"} size={32} className="rounded-lg"/>
                                                )}
                                                <div>
                                                    <p className={cn("text-sm font-semibold uppercase", ui.text.heading)}>{pool.symbol}</p>
                                                    <p className="text-[10px] font-semibold uppercase tracking-wide text-violet-500 dark:text-violet-400">{pool.protocol}</p>
                                                </div>
                                            </div>
                                        </td>

                                        {/* Polymorphic Strategy Category Tag */}
                                        <td className="px-4 py-3">
                                            <span className={cn(
                                                "px-2 py-0.5 rounded text-[9px] font-extrabold uppercase tracking-wider",
                                                pool.category === "dex_liquidity"
                                                    ? "border border-violet-200 bg-violet-50 text-violet-700 dark:border-violet-900/50 dark:bg-violet-950/30 dark:text-violet-300"
                                                    : "border border-purple-200 bg-purple-50 text-purple-700 dark:border-purple-900/50 dark:bg-purple-950/30 dark:text-purple-300"
                                            )}>
                                                {pool.category === "dex_liquidity" ? "AMM LP" : "Lending Pool"}
                                            </span>
                                        </td>

                                        {/* Normalized TVL */}
                                        <td className="px-4 py-3 text-right text-sm font-medium text-zinc-600 dark:text-zinc-300">
                                            {formatMoney(pool.tvl_usd)}
                                        </td>

                                        {/* Normalized APR */}
                                        <td className="px-4 py-3 text-right text-sm font-semibold text-emerald-600 dark:text-emerald-400">
                                            {pool.apr.toFixed(2)}%
                                            {pool.category === "dex_liquidity" && (
                                                <p className="mt-0.5 text-[10px] font-medium text-zinc-400">
                                                    Fee 24h {pool.feeApr24h?.toFixed(2) ?? "0.00"}%
                                                    {(pool.rewardApr ?? 0) > 0 ? ` + reward ${pool.rewardApr?.toFixed(2)}%` : ""}
                                                </p>
                                            )}
                                        </td>

                                        {/* Matrix Match Score & Tier Badge */}
                                        <td className="px-4 py-3 text-center">
                                            <span className="rounded-md border border-violet-100 bg-violet-50 px-2 py-1 font-mono text-xs font-semibold text-violet-700 dark:border-violet-900/50 dark:bg-violet-950/30 dark:text-violet-300">
                                                {pool.ahpMatchIndex}%
                                            </span>
                                            <p className={cn(
                                                "text-[9px] font-bold mt-1.5 uppercase tracking-tight",
                                                pool.tier?.includes("A+") ? "text-amber-500 dark:text-amber-400" : pool.tier?.includes("A") ? "text-emerald-600 dark:text-emerald-400" : "text-zinc-500"
                                            )}>
                                                {pool.tier}
                                            </p>
                                        </td>

                                        {/* Dynamic Risk Flags Handling */}
                                        <td className="px-4 py-3">
                                            <div className="flex flex-wrap gap-1 justify-center max-w-[150px] mx-auto">
                                                {hasFlags ? (
                                                    pool.flags.map((flag: string) => (
                                                        <span key={flag} className="flex items-center gap-0.5 px-1.5 py-0.5 bg-red-950/50 border border-red-500/30 text-red-400 text-[8px] font-bold rounded uppercase tracking-tighter">
                                                            <AlertTriangle size={8} /> {flag.replace("_", " ")}
                                                        </span>
                                                    ))
                                                ) : (
                                                    <span className="text-[10px] font-medium text-zinc-400">Clear</span>
                                                )}
                                            </div>
                                        </td>

                                        <td className="px-4 py-3 text-center">
                                            <div className="flex justify-center gap-1.5">
                                                <Link
                                                    href={`/simulator?mode=${pool.category === "dex_liquidity" ? "provide_liquidity" : "lend"}&symbol=${encodeURIComponent(displaySymbols[0] || pool.symbol || "")}&marketId=${encodeURIComponent(pool.market_id || "")}`}
                                                    className="inline-flex items-center gap-1 rounded-md border border-violet-200 bg-violet-50 px-2.5 py-1 text-[10px] font-semibold text-violet-800 transition-colors hover:border-violet-300 hover:bg-violet-100 dark:border-violet-800/60 dark:bg-violet-950/35 dark:text-violet-200 dark:hover:bg-violet-900/25"
                                                >
                                                    Sim
                                                </Link>
                                                <a
                                                    href={getPoolUrl(pool)}
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    className="inline-flex items-center gap-1 rounded-md border border-violet-100 bg-white px-2.5 py-1 text-[10px] font-semibold text-violet-700 shadow-sm transition-colors hover:bg-violet-50 dark:border-violet-900/40 dark:bg-zinc-950 dark:text-violet-300 dark:hover:bg-violet-950/30"
                                                >
                                                    Pool <ExternalLink size={10}/>
                                                </a>
                                            </div>
                                        </td>
                                    </tr>
                                );
                            })}
                            </tbody>
                        </table>
                        </div>
                    </div>
                    )
                ) : (
                    <div className="grid min-h-[520px] grid-cols-1 lg:grid-cols-[360px_1fr]">
                        <div className="border-b border-violet-100 dark:border-violet-900/40 lg:border-b-0 lg:border-r">
                            <div className="border-b border-violet-100 bg-violet-50/60 px-4 py-3 dark:border-violet-900/40 dark:bg-violet-950/20">
                                <p className={cn("text-sm font-semibold", ui.text.heading)}>Token Overview</p>
                                <p className={cn("mt-1 text-xs", ui.text.muted)}>
                                    TVL is allocated from supported pools; LP pairs are split across underlying tokens.
                                </p>
                            </div>

                            <div className="max-h-[460px] overflow-y-auto">
                                {filteredAssets.map((asset) => {
                                    const isSelected = selectedAsset?.symbol === asset.symbol;
                                    return (
                                        <button
                                            key={asset.symbol}
                                            onClick={() => setSelectedAssetSymbol(asset.symbol)}
                                            className={focusClass(tokenFocusKeys(asset.symbol), cn(
                                                "flex w-full items-center gap-3 border-b border-violet-50 px-4 py-3 text-left transition-colors dark:border-violet-900/25",
                                                isSelected
                                                    ? "bg-violet-50 dark:bg-violet-950/30"
                                                    : "hover:bg-violet-50/50 dark:hover:bg-violet-950/15"
                                            ))}
                                        >
                                            <TokenIcon symbol={asset.symbol} size={30}/>
                                            <div className="min-w-0 flex-1">
                                                <div className="flex items-center justify-between gap-3">
                                                    <p className={cn("truncate text-sm font-semibold", ui.text.heading)}>{asset.symbol}</p>
                                                    <p className="shrink-0 text-xs font-semibold tabular-nums text-emerald-600 dark:text-emerald-400">
                                                        {asset.bestApr.toFixed(2)}%
                                                    </p>
                                                </div>
                                                <div className="mt-1 flex items-center justify-between gap-3">
                                                    <p className="truncate text-[11px] text-zinc-500">
                                                        {asset.poolCount} pools · {asset.protocols.slice(0, 2).join(", ")}
                                                    </p>
                                                    <p className="shrink-0 text-[11px] font-medium tabular-nums text-zinc-500">
                                                        {formatMoney(asset.totalTvl)}
                                                    </p>
                                                </div>
                                            </div>
                                        </button>
                                    );
                                })}
                            </div>
                        </div>

                        <div className="p-5">
                            {selectedAsset ? (
                                <div className={focusClass(tokenFocusKeys(selectedAsset.symbol), "flex h-full flex-col transition-all duration-200")}>
                                    <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
                                        <div className="flex items-center gap-3">
                                            <TokenIcon symbol={selectedAsset.symbol} size={42}/>
                                            <div>
                                                <p className={cn("text-xl font-semibold", ui.text.heading)}>{selectedAsset.symbol}</p>
                                                <p className={cn("mt-1 text-xs", ui.text.muted)}>
                                                    {selectedAsset.poolCount} supported markets across {selectedAsset.protocols.length} protocols
                                                </p>
                                            </div>
                                        </div>
                                        <div className="grid grid-cols-2 gap-3 text-right">
                                            <div>
                                                <p className="text-[10px] uppercase tracking-wider text-zinc-500">Market TVL</p>
                                                <p className={cn("mt-1 text-sm font-semibold tabular-nums", ui.text.heading)}>
                                                    {formatMoney(selectedAsset.totalTvl)}
                                                </p>
                                            </div>
                                            <div>
                                                <p className="text-[10px] uppercase tracking-wider text-zinc-500">Best APR</p>
                                                <p className="mt-1 text-sm font-semibold tabular-nums text-emerald-600 dark:text-emerald-400">
                                                    {selectedAsset.bestApr.toFixed(2)}%
                                                </p>
                                            </div>
                                        </div>
                                    </div>

                                    <TokenPriceChart symbol={selectedAsset.symbol}/>

                                    <div className="mt-4 flex flex-wrap gap-1.5">
                                        {selectedAsset.protocols.map((protocol) => (
                                            <span
                                                key={protocol}
                                                className="rounded border border-violet-100 bg-violet-50 px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-violet-600 dark:border-violet-900/40 dark:bg-violet-950/30 dark:text-violet-300"
                                            >
                                                {protocol}
                                            </span>
                                        ))}
                                    </div>
                                    <div className="mt-4 flex flex-wrap gap-2 border-t border-violet-100 pt-4 dark:border-violet-900/40">
                                        <Link
                                            href={`/simulator?mode=buy&symbol=${encodeURIComponent(selectedAsset.symbol)}`}
                                            className="rounded-lg border border-violet-200 bg-violet-50 px-3 py-2 text-xs font-semibold text-violet-800 transition-colors hover:border-violet-300 hover:bg-violet-100 dark:border-violet-800/60 dark:bg-violet-950/35 dark:text-violet-200 dark:hover:bg-violet-900/25"
                                        >
                                            Simulate buy
                                        </Link>
                                        <Link
                                            href={`/simulator?mode=lend&symbol=${encodeURIComponent(selectedAsset.symbol)}`}
                                            className="rounded-lg border border-violet-100 px-3 py-2 text-xs font-semibold text-violet-700 transition-colors hover:bg-violet-50 dark:border-violet-900/40 dark:text-violet-300 dark:hover:bg-violet-950/30"
                                        >
                                            Simulate lend
                                        </Link>
                                        <Link
                                            href="/risk-engine"
                                            className="rounded-lg border border-violet-100 px-3 py-2 text-xs font-semibold text-zinc-600 transition-colors hover:bg-violet-50 hover:text-violet-700 dark:border-violet-900/40 dark:text-zinc-300 dark:hover:bg-violet-950/30 dark:hover:text-violet-300"
                                        >
                                            Check portfolio risk
                                        </Link>
                                    </div>
                                </div>
                            ) : (
                                <div className="flex h-full items-center justify-center text-sm text-zinc-500">
                                    No token matches the current filter.
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
