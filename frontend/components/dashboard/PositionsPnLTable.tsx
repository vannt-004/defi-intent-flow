"use client";

import {cn} from "@/utils/cn";
import {ui} from "@/styles/ui";

import {useState} from "react";
import Link from "next/link";
import {ArrowUpRight, ShieldCheck, Wand2} from "lucide-react";

import {TAsset, TPositionPnL} from "@/types/portfolio";
import PnLText from "@/components/dashboard/PnLText";
import InfoTooltip from "@/components/ui/InfoTooltip";
import {TokenIcon} from "@/components/icon/TokenIcon";
import {TokenPairIcon} from "@/components/icon/TokenPairIcon";
import {formatPercent} from "@/utils/format";

type PosFilter = "all" | "hold" | "lend" | "farm" | "borrow";
const MIN_DISPLAY_VALUE_USD = 0.01;

const TYPE_META = {
    hold: {
        label: "Hold",
        bg: "bg-violet-50 dark:bg-violet-950/30",
        text: "text-violet-700 dark:text-violet-300",
        pnlLabel: "Unrealized"
    },
    lend: {
        label: "Lending",
        bg: "bg-blue-50 dark:bg-blue-950",
        text: "text-blue-700 dark:text-blue-300",
        pnlLabel: "Accrued Interest"
    },
    farm: {
        label: "Farming",
        bg: "bg-amber-50 dark:bg-amber-950",
        text: "text-amber-700 dark:text-amber-300",
        pnlLabel: "Yield + Fees"
    },
    borrow: {
        label: "Borrow",
        bg: "bg-red-50 dark:bg-red-950",
        text: "text-red-700 dark:text-red-300",
        pnlLabel: "Interest Owed"
    },
};

const TABLE_HEADERS = [
    {label: "Asset"},
    {label: "Type"},
    {label: "Value"},
    {label: "Balance"},
    {
        label: "Basis",
        tooltip:
            "Verified cost basis for wallet tokens; protocol cashflow capital base for lending/borrow when available.",
    },
    {label: "Current Price"},
    {label: "PnL"},
    {label: "ROI"},
    {label: "Next"},
];

export default function PositionsPnLTable({
    positions,
    assets = [],
    canUseFullFeatures = true,
}: {
    positions: TPositionPnL[];
    assets?: TAsset[];
    canUseFullFeatures?: boolean;
}) {
    const [filter, setFilter] = useState<PosFilter>("all");
    const filters: { key: PosFilter; label: string }[] = [
        {key: "all", label: "All"},
        {key: "hold", label: "Hold"},
        {key: "lend", label: "Lending"},
        {key: "farm", label: "Farming"},
        {key: "borrow", label: "Borrow"},
    ];
    const displayPositions = dedupePositions(
        positions.filter((p) => Math.abs(p.valueUsd) >= MIN_DISPLAY_VALUE_USD)
    );
    const filtered = filter === "all" ? displayPositions : displayPositions.filter((p) => p.type === filter);
    const assetBySymbol = new Map(assets.map((asset) => [asset.symbol, asset]));

    return (
        <div className={cn(ui.card.base, "p-5")}>
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <div>
                    <p className={cn("text-sm font-semibold", ui.text.heading)}>
                        Portfolio Holdings ({displayPositions.length})
                    </p>
                    <p className={cn("mt-1 text-xs", ui.text.muted)}>
                        Token hold and DeFi positions in one view, including cost basis and P&L
                    </p>
                </div>
                <div className="flex flex-wrap gap-1.5">
                    {filters.map((f) => (
                        <button
                            key={f.key}
                            onClick={() => setFilter(f.key)}
                            className={cn(
                                "rounded-lg border px-3 py-1 text-xs font-medium transition-colors",
                                f.key === filter
                                    ? "border border-violet-200 bg-violet-50 text-violet-800 hover:border-violet-300 hover:bg-violet-100 dark:border-violet-800/60 dark:bg-violet-950/35 dark:text-violet-200 dark:hover:bg-violet-900/25"
                                    : "border-violet-100 text-zinc-500 hover:bg-violet-50 hover:text-violet-700 dark:border-violet-900/40 dark:hover:bg-violet-950/30 dark:hover:text-violet-300"
                            )}
                        >
                            {f.label}
                        </button>
                    ))}
                </div>
            </div>

            <div className="overflow-x-auto">
                <table className="w-full border-collapse text-left text-sm"
                       style={{tableLayout: "fixed", minWidth: 940}}>
                    <colgroup>
                        <col style={{width: 190}}/>
                        <col style={{width: 76}}/>
                        <col style={{width: 110}}/>
                        <col style={{width: 110}}/>
                        <col style={{width: 100}}/>
                        <col style={{width: 100}}/>
                        <col style={{width: 80}}/>
                        <col style={{width: 80}}/>
                        <col style={{width: 104}}/>
                    </colgroup>
                    <thead>
                    <tr className="border-b border-violet-100 dark:border-violet-900/40">
                        {TABLE_HEADERS.map((h, i) => (
                            <th
                                key={h.label}
                                className={cn("pb-3 text-xs font-semibold text-zinc-400",
                                    i > 1 ? "text-right" : "pl-1")}
                            >
                                <span className={cn("inline-flex items-center gap-1", i > 1 && "w-full justify-end")}>
                                    {h.label}
                                    {h.tooltip ? <InfoTooltip text={h.tooltip} side="bottom"/> : null}
                                </span>
                            </th>
                        ))}
                    </tr>
                    </thead>
                    <tbody className="divide-y divide-violet-50 dark:divide-violet-900/30">
                    {filtered.map((p) => {
                        const meta = TYPE_META[p.type];
                        const isBorrow = p.type === "borrow";
                        const asset = assetBySymbol.get(p.name);
                        const isFarm = p.type === "farm";
                        const balance = p.type === "hold" ? asset?.balance : p.balance;
                        const lpAmounts = getLpAmountRows(p);
                        const symbol = p.name.split("/")[0];
                        const simulatorMode = p.type === "borrow" ? "borrow" : p.type === "farm" ? "provide_liquidity" : "lend";
                        const pnlReliable = p.pnlReliable !== false;
                        const costBasisReliable = p.costBasisReliable !== false && p.costBasisUsd > 0;
                        const unavailableLabel = p.type === "hold" ? "Basis unknown" : "Flow unavailable";
                        return (
                            <tr key={p.positionId} className="group hover:bg-violet-50/50 dark:hover:bg-violet-950/20">
                                {/* Asset */}
                                <td className="py-3 pl-1">
                                    <div className="flex items-center gap-2">
                                        {p.name.includes("/") ? (
                                            <TokenPairIcon symbols={p.name.split("/")} size={30}/>
                                        ) : (
                                            <TokenIcon symbol={p.name} size={28}/>
                                        )}
                                        <div>
                                            <p className={cn("text-sm font-semibold", ui.text.heading)}>{p.name}</p>
                                            <p className="text-[11px] text-zinc-400">{p.protocol}</p>
                                        </div>
                                    </div>
                                </td>
                                {/* Type badge */}
                                <td className="py-3">
                                    <span className={cn("rounded px-2 py-0.5 text-[10px] font-semibold",
                                        meta.bg,
                                        meta.text)}>
                                        {meta.label}
                                    </span>
                                </td>
                                {/* Value */}
                                <td className="py-3 text-right">
                                    <span className={cn("font-semibold", isBorrow ? "text-red-500" : ui.text.heading)}>
                                        {isBorrow ? "−" : ""}${Math.abs(p.valueUsd).toLocaleString()}
                                    </span>
                                    {p.apy && <p className="text-[10px] text-zinc-400">APY {p.apy}%</p>}
                                </td>
                                <td className="py-3 text-right text-zinc-500 dark:text-zinc-400">
                                    {isFarm ? (
                                        lpAmounts.length > 0 ? (
                                            <div className="space-y-0.5">
                                                {lpAmounts.map((item) => (
                                                    <p key={item.symbol} className="text-[10px] font-semibold tabular-nums">
                                                        {formatTokenAmount(item.amount)} {item.symbol}
                                                    </p>
                                                ))}
                                            </div>
                                        ) : (
                                            <span className="text-zinc-400">—</span>
                                        )
                                    ) : balance != null && Math.abs(balance) > 0 ? (
                                        <>
                                            <p className="text-[11px] font-semibold tabular-nums">
                                                {balance.toLocaleString(undefined, {maximumFractionDigits: 6})}
                                            </p>
                                            <p className="text-[10px]">{p.name}</p>
                                        </>
                                    ) : (
                                        <span className="text-zinc-400">—</span>
                                    )}
                                </td>
                                {/* Cost basis / entry */}
                                <td className="py-3 text-right text-zinc-400">
                                    {costBasisReliable ? (
                                        <>
                                            <p className="text-[11px] font-semibold tabular-nums">
                                                ${p.costBasisUsd.toLocaleString(undefined, {maximumFractionDigits: 0})}
                                            </p>
                                            <p className="text-[10px]">
                                                {p.entryPrice ? `avg $${p.entryPrice.toLocaleString(undefined,
                                                    {maximumFractionDigits: 4})}` : "—"}
                                            </p>
                                        </>
                                    ) : (
                                        <span className="inline-flex items-center justify-end gap-1 text-zinc-400">
                                            —
                                            <InfoTooltip text={p.pnlNote || "Basis/capital base is not available for this row."}/>
                                        </span>
                                    )}
                                </td>
                                {/* Current price */}
                                <td className="py-3 text-right">
                                    {p.currentPrice ? (
                                        <span className={cn(ui.text.heading)}>${p.currentPrice.toLocaleString()}</span>
                                    ) : (
                                        <span className="text-zinc-400">—</span>
                                    )}
                                </td>
                                {/* PnL */}
                                <td className="py-3 text-right">
                                    {pnlReliable ? (
                                        <PnLText value={p.pnlUsd} size="sm"/>
                                    ) : (
                                        <span className="inline-flex items-center justify-end gap-1 text-zinc-400">
                                            —
                                            <InfoTooltip text={p.pnlNote || "PnL is not available for this row."}/>
                                        </span>
                                    )}
                                    <p className="text-[10px] text-zinc-400">
                                        {pnlReliable ? meta.pnlLabel : unavailableLabel}
                                    </p>
                                </td>
                                {/* ROI */}
                                <td className="py-3 text-right">
                                    {pnlReliable && p.pnlPct != null ? (
                                        <PercentText value={p.pnlPct}/>
                                    ) : (
                                        <span className="text-zinc-400">—</span>
                                    )}
                                </td>
                                <td className="py-3 text-right">
                                    <div className="flex justify-end gap-1">
                                        <Link
                                            href={`/markets?symbol=${encodeURIComponent(symbol)}`}
                                            className="rounded-md p-1.5 text-zinc-400 transition-colors hover:bg-violet-50 hover:text-violet-700 dark:hover:bg-violet-950/30 dark:hover:text-violet-300"
                                            title="Open market"
                                        >
                                            <ArrowUpRight size={14}/>
                                        </Link>
                                        {canUseFullFeatures && p.type !== "hold" && (
                                            <Link
                                                href="/risk-engine"
                                                className="rounded-md p-1.5 text-zinc-400 transition-colors hover:bg-violet-50 hover:text-violet-700 dark:hover:bg-violet-950/30 dark:hover:text-violet-300"
                                                title="Review risk"
                                            >
                                                <ShieldCheck size={14}/>
                                            </Link>
                                        )}
                                        {canUseFullFeatures && (
                                            <Link
                                                href={`/simulator?mode=${simulatorMode}&symbol=${encodeURIComponent(symbol)}`}
                                                className="rounded-md p-1.5 text-zinc-400 transition-colors hover:bg-violet-50 hover:text-violet-700 dark:hover:bg-violet-950/30 dark:hover:text-violet-300"
                                                title="Simulate action"
                                            >
                                                <Wand2 size={14}/>
                                            </Link>
                                        )}
                                    </div>
                                </td>
                            </tr>
                        );
                    })}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

function PercentText({value}: { value: number }) {
    return (
        <span className={cn(
            "text-sm font-medium",
            value >= 0 ? "text-emerald-500 dark:text-emerald-400" : "text-red-500 dark:text-red-400"
        )}>
            {formatPercent(value)}
        </span>
    );
}

function getLpAmountRows(position: TPositionPnL) {
    return [
        {symbol: position.token0 || position.name.split("/")[0], amount: position.amount0},
        {symbol: position.token1 || position.name.split("/")[1], amount: position.amount1},
    ].filter((item): item is { symbol: string; amount: number } => (
        !!item.symbol && item.amount != null && Math.abs(Number(item.amount)) >= 1e-8
    ));
}

function dedupePositions(positions: TPositionPnL[]) {
    const byId = new Map<string, TPositionPnL>();

    for (const position of positions) {
        const key = position.positionId || `${position.type}:${position.protocol}:${position.name}`;
        const current = byId.get(key);
        if (!current || Math.abs(position.valueUsd) > Math.abs(current.valueUsd)) {
            byId.set(key, position);
        }
    }

    return Array.from(byId.values());
}

function formatTokenAmount(value: number) {
    const abs = Math.abs(value);
    if (abs >= 1) {
        return value.toLocaleString(undefined, {maximumFractionDigits: 4});
    }
    return value.toLocaleString(undefined, {maximumFractionDigits: 8});
}
