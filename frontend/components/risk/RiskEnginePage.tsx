"use client";

import Link from "next/link";
import {AlertTriangle, ArrowUpRight, Wand2} from "lucide-react";

import Skeleton from "@/components/common/Skeleton";
import Div from "@/components/ui/Div";
import {TokenIcon} from "@/components/icon/TokenIcon";
import {TokenPairIcon} from "@/components/icon/TokenPairIcon";
import {usePortfolioRiskQuery} from "@/hooks/usePortfolioQuery";
import {useWallet} from "@/hooks/useWallet";
import {TPositionRisk, TPriceTrend} from "@/types/portfolio";
import {cn} from "@/utils/cn";
import {formatMoney} from "@/utils/format";
import {ui} from "@/styles/ui";
import {useAgentFocus} from "@/components/assistant/AgentFocusContext";

const LEVEL_CLASS = {
    LOW: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300",
    MEDIUM: "bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-300",
    HIGH: "bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-300",
    CRITICAL: "bg-red-100 text-red-800 dark:bg-red-950/50 dark:text-red-200",
};

type PriceTrendMap = Record<string, TPriceTrend>;

const isRecord = (value: unknown): value is Record<string, unknown> =>
    typeof value === "object" && value !== null && !Array.isArray(value);

const isFiniteNumber = (value: number | null | undefined): value is number =>
    typeof value === "number" && Number.isFinite(value);

const safeNumber = (value: number | null | undefined, fallback = 0) =>
    isFiniteNumber(value) ? value : fallback;

const formatScore = (value: number | null | undefined) => safeNumber(value).toFixed(1);

const formatOptionalPercent = (value: number | null | undefined, digits = 2) =>
    isFiniteNumber(value) ? `${value.toFixed(digits)}%` : "-";

const formatHealth = (value: number | null | undefined) => {
    if (!isFiniteNumber(value)) return "-";
    return value === 999 ? "∞" : value.toFixed(2);
};

const isSingleTrend = (value: TPositionRisk["priceTrend"]): value is TPriceTrend =>
    isRecord(value) && ("trend" in value || "forecast_7d_pct" in value || "change_7d_pct" in value);

const toPriceTrendMap = (value: TPositionRisk["priceTrend"]): PriceTrendMap => {
    if (!isRecord(value) || isSingleTrend(value)) return {};

    return Object.fromEntries(
        Object.entries(value).filter((entry): entry is [string, TPriceTrend] => isRecord(entry[1]))
    );
};

function RiskBar({score}: { score: number }) {
    const color = score >= 65 ? "bg-red-500" : score >= 40 ? "bg-amber-400" : "bg-violet-500";
    return (
        <div className="h-2 overflow-hidden rounded-full bg-violet-100 dark:bg-violet-950/40">
            <div className={cn("h-full rounded-full transition-all", color)} style={{width: `${Math.min(score, 100)}%`}}/>
        </div>
    );
}

function RiskCard({position}: { position: TPositionRisk }) {
    const {focusClass} = useAgentFocus();
    const isLp = position.type === "lp";
    const trend = !isLp && isSingleTrend(position.priceTrend) ? position.priceTrend : undefined;
    const pairTrend = isLp ? toPriceTrendMap(position.priceTrend) : {};
    const primarySymbol = String(isLp ? position.token0 || position.symbol : position.symbol || "").split("/")[0].toUpperCase();
    const simulatorMode = isLp ? "provide_liquidity" : position.side === "BORROWER" ? "borrow" : "lend";
    const displaySymbol = position.symbol || [position.token0, position.token1].filter(Boolean).join("/") || "Unknown";
    const protocol = position.protocol || "Unknown";
    const riskScore = safeNumber(position.riskScore);
    const signals = position.signals ?? [];

    const focusKeys = [
        "risk:portfolio",
        ...(primarySymbol ? [`risk:token:${primarySymbol}`, `token:${primarySymbol}`] : []),
        ...(position.positionId ? [`risk:position:${position.positionId}`] : []),
    ];

    return (
        <Div className={focusClass(focusKeys, "transition-all duration-200")}>
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex min-w-0 items-center gap-3">
                    {isLp ? (
                        <TokenPairIcon symbols={[position.token0, position.token1].filter(Boolean) as string[]} size={34}/>
                    ) : (
                        <TokenIcon symbol={position.symbol || "RISK"} size={32}/>
                    )}
                    <div className="min-w-0">
                        <p className={cn("truncate text-sm font-semibold", ui.text.heading)}>{displaySymbol}</p>
                        <p className="mt-0.5 text-xs text-zinc-500">{protocol} · {isLp ? "LP Range" : position.side || "Position"}</p>
                    </div>
                </div>
                <span className={cn("rounded-lg px-2.5 py-1 text-[10px] font-semibold", LEVEL_CLASS[position.riskLevel] ?? LEVEL_CLASS.LOW)}>
                    {position.riskLevel}
                </span>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
                <div>
                    <p className="text-[10px] uppercase tracking-wider text-zinc-500">Value</p>
                    <p className={cn("mt-1 text-sm font-semibold tabular-nums", ui.text.heading)}>
                        {formatMoney(safeNumber(position.valueUsd))}
                    </p>
                </div>
                <div>
                    <p className="text-[10px] uppercase tracking-wider text-zinc-500">Risk Score</p>
                    <p className={cn("mt-1 text-sm font-semibold tabular-nums", ui.text.heading)}>
                        {formatScore(riskScore)}
                    </p>
                </div>
                {isLp ? (
                    <>
                        <div>
                            <p className="text-[10px] uppercase tracking-wider text-zinc-500">Forecast IL</p>
                            <p className={cn("mt-1 text-sm font-semibold tabular-nums", safeNumber(position.forecastImpermanentLossUsd) < 0 ? ui.text.down : ui.text.up)}>
                                {formatMoney(safeNumber(position.forecastImpermanentLossUsd))}
                            </p>
                        </div>
                        <div>
                            <p className="text-[10px] uppercase tracking-wider text-zinc-500">Range Edge</p>
                            <p className={cn("mt-1 text-sm font-semibold tabular-nums", ui.text.heading)}>
                                {formatOptionalPercent(position.range?.distanceToRangeEdgePct, 1)}
                            </p>
                        </div>
                    </>
                ) : (
                    <>
                        <div>
                            <p className="text-[10px] uppercase tracking-wider text-zinc-500">Health</p>
                            <p className={cn("mt-1 text-sm font-semibold tabular-nums", ui.text.heading)}>
                                {formatHealth(position.healthFactor)}
                            </p>
                        </div>
                        <div>
                            <p className="text-[10px] uppercase tracking-wider text-zinc-500">Forecast Risk</p>
                            <p className={cn("mt-1 text-sm font-semibold tabular-nums", safeNumber(position.forecastLiquidationRiskPct) > 35 ? ui.text.down : ui.text.heading)}>
                                {formatOptionalPercent(position.forecastLiquidationRiskPct, 1)}
                            </p>
                        </div>
                    </>
                )}
            </div>

            <div className="mt-4">
                <RiskBar score={riskScore}/>
            </div>

            <div className="mt-4 grid gap-3 md:grid-cols-2">
                <div className="rounded-lg bg-violet-50/50 p-3 dark:bg-violet-950/20">
                    <p className={cn("mb-2 text-xs font-semibold", ui.text.heading)}>
                        {isLp ? "LP Risk Model" : "Lending Risk Model"}
                    </p>
                    {isLp ? (
                        <div className="space-y-1.5 text-[11px] text-zinc-500">
                            <p>In range: <span className={cn("font-semibold", position.range?.inRange ? ui.text.up : ui.text.down)}>{position.range?.inRange == null ? "Unknown" : position.range.inRange ? "Yes" : "No"}</span></p>
                            <p>7D forecast: <span className={cn("font-semibold", position.range?.forecastOutOfRange ? ui.text.down : ui.text.up)}>{position.range?.forecastOutOfRange ? "Out of range risk" : "Inside range"}</span></p>
                            <p>Hold value: <span className="font-semibold">{formatMoney(safeNumber(position.holdValueUsd))}</span></p>
                            <p>Current IL: <span className={cn("font-semibold", safeNumber(position.impermanentLossUsd) < 0 ? ui.text.down : ui.text.up)}>{formatMoney(safeNumber(position.impermanentLossUsd))}</span></p>
                        </div>
                    ) : (
                        <div className="space-y-1.5 text-[11px] text-zinc-500">
                            <p>Liquidation buffer: <span className="font-semibold">{formatMoney(safeNumber(position.liquidationBufferUsd))}</span></p>
                            <p>Move to liquidation: <span className={cn("font-semibold", safeNumber(position.priceMoveToLiquidationPct, 100) < 10 ? ui.text.down : ui.text.heading)}>{formatOptionalPercent(position.priceMoveToLiquidationPct)}</span></p>
                            <p>7D price: <span className={cn("font-semibold", safeNumber(trend?.change_7d_pct) < 0 ? ui.text.down : ui.text.up)}>{formatOptionalPercent(trend?.change_7d_pct)}</span></p>
                            <p>Forecast: <span className={cn("font-semibold", safeNumber(trend?.forecast_7d_pct) < 0 ? ui.text.down : ui.text.up)}>{trend?.trend ?? "UNKNOWN"} {formatOptionalPercent(trend?.forecast_7d_pct)}</span></p>
                        </div>
                    )}
                </div>

                <div className="rounded-lg bg-violet-50/50 p-3 dark:bg-violet-950/20">
                    <p className={cn("mb-2 text-xs font-semibold", ui.text.heading)}>Signals</p>
                    <div className="space-y-1.5">
                        {signals.length ? signals.map((signal) => (
                            <div key={signal} className="flex gap-1.5 text-[11px] text-zinc-500">
                                <AlertTriangle size={12} className="mt-0.5 shrink-0 text-amber-500"/>
                                <span>{signal}</span>
                            </div>
                        )) : (
                            <p className="text-[11px] text-zinc-500">No active risk signal.</p>
                        )}
                    </div>
                </div>
            </div>

            {isLp && (
                <div className="mt-3 flex flex-wrap gap-2 text-[10px] text-zinc-500">
                    {Object.entries(pairTrend).map(([symbol, item]) => (
                        <span key={symbol} className="rounded-md bg-white px-2 py-1 dark:bg-zinc-950">
                            {item.symbol ?? symbol}: 7D {formatOptionalPercent(item.change_7d_pct)}, vol {formatOptionalPercent(item.volatility_30d_pct)}
                        </span>
                    ))}
                </div>
            )}

            <div className="mt-4 flex flex-wrap gap-2 border-t border-violet-100 pt-3 dark:border-violet-900/40">
                <Link
                    href={`/markets?symbol=${encodeURIComponent(primarySymbol)}`}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-violet-100 px-3 py-1.5 text-[11px] font-semibold text-violet-700 transition-colors hover:bg-violet-50 dark:border-violet-900/40 dark:text-violet-300 dark:hover:bg-violet-950/30"
                >
                    Market <ArrowUpRight size={12}/>
                </Link>
                <Link
                    href={`/simulator?mode=${simulatorMode}&symbol=${encodeURIComponent(primarySymbol)}`}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-violet-200 bg-violet-50 px-3 py-1.5 text-[11px] font-semibold text-violet-800 transition-colors hover:border-violet-300 hover:bg-violet-100 dark:border-violet-800/60 dark:bg-violet-950/35 dark:text-violet-200 dark:hover:bg-violet-900/25"
                >
                    Simulate <Wand2 size={12}/>
                </Link>
            </div>
        </Div>
    );
}

export default function RiskEnginePage() {
    const {focusClass} = useAgentFocus();
    const {address} = useWallet();
    const {data, isPending, error} = usePortfolioRiskQuery(address);

    if (isPending) {
        return (
            <div className="flex flex-1 flex-col gap-4 p-4 md:p-5">
                <Skeleton className="h-32"/>
                <Skeleton className="h-64"/>
                <Skeleton className="h-64"/>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex flex-1 items-center justify-center p-8 text-sm text-red-500">
                Failed to load risk engine data.
            </div>
        );
    }

    const portfolio = data?.portfolio;
    const positions = data?.positions ?? [];
    const portfolioRiskScore = safeNumber(portfolio?.riskScore);

    return (
        <div className="flex flex-1 flex-col gap-4 p-4 md:p-5">
            <Div className={focusClass("risk:portfolio", "transition-all duration-200")}>
                <div className="grid gap-4 lg:grid-cols-[1fr_auto] lg:items-center">
                    <div>
                        <p className="text-xs font-semibold uppercase tracking-wider text-violet-500 dark:text-violet-400">
                            Portfolio Risk Engine
                        </p>
                        <p className={cn("mt-1 text-3xl font-semibold", ui.text.heading)}>
                            {portfolio?.riskLevel ?? "LOW"} · {formatScore(portfolioRiskScore)}
                        </p>
                        <p className={cn("mt-2 max-w-2xl text-xs", ui.text.muted)}>
                            Position-level risk model using price history, lending liquidation buffer, LP impermanent loss, and Uniswap V3 range distance.
                        </p>
                    </div>
                    <div className="grid grid-cols-3 gap-3 text-right">
                        <div>
                            <p className="text-[10px] uppercase tracking-wider text-zinc-500">Net Worth</p>
                            <p className={cn("mt-1 text-sm font-semibold", ui.text.heading)}>{formatMoney(portfolio?.netWorthUsd ?? 0)}</p>
                        </div>
                        <div>
                            <p className="text-[10px] uppercase tracking-wider text-zinc-500">High Risk</p>
                            <p className={cn("mt-1 text-sm font-semibold", ui.text.down)}>{formatMoney(portfolio?.highRiskValueUsd ?? 0)}</p>
                        </div>
                        <div>
                            <p className="text-[10px] uppercase tracking-wider text-zinc-500">Positions</p>
                            <p className={cn("mt-1 text-sm font-semibold", ui.text.heading)}>{portfolio?.positionCount ?? 0}</p>
                        </div>
                    </div>
                </div>
            </Div>

            <div className="grid gap-4 xl:grid-cols-2">
                {positions.map((position) => (
                    <RiskCard key={position.positionId} position={position}/>
                ))}
            </div>

            {!positions.length && (
                <Div className="flex items-center justify-center p-8 text-sm text-zinc-500">
                    No positions available for risk analysis.
                </Div>
            )}
        </div>
    );
}
