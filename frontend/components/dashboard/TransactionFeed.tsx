"use client";

import Link from "next/link";
import {cn} from "@/utils/cn";
import {ui} from "@/styles/ui";
import {TPnLFlow, TPnLFlowEvent, TTransaction} from "@/types/portfolio";
import Div from "@/components/ui/Div";
import {TokenIcon} from "@/components/icon/TokenIcon";
import {TokenPairIcon} from "@/components/icon/TokenPairIcon";
import {useMemo, useState} from "react";
import {ArrowUpRight, ExternalLink, Search, Wand2} from "lucide-react";
import Select from "@/components/ui/Select";

type TxTypeFilter = "all" | TTransaction["type"];
type TxActionFilter = "all" | "deposit" | "withdraw" | "borrow" | "repay" | "swap" | "transfer";
type ViewMode = "transactions" | "pools";
type PriceEvidence = {
    priceSource?: string | null;
    priceTimestamp?: number | null;
    priceDeltaSeconds?: number | null;
    priceMaxDeltaSeconds?: number | null;
    priceReliable?: boolean | null;
    priceNote?: string | null;
};

export default function TransactionFeed({
    transactions,
    pnlFlows = [],
}: {
    transactions: TTransaction[];
    pnlFlows?: TPnLFlow[];
}) {
    const dotColor = {earn: "bg-emerald-500", cost: "bg-red-500", transfer: "bg-violet-400"};
    const [viewMode, setViewMode] = useState<ViewMode>("transactions");
    const [typeFilter, setTypeFilter] = useState<TxTypeFilter>("all");
    const [actionFilter, setActionFilter] = useState<TxActionFilter>("all");
    const [query, setQuery] = useState("");
    const [selectedFlowKey, setSelectedFlowKey] = useState<string | null>(null);

    const actionLabel: Record<string, string> = {
        deposit: "Deposit",
        withdraw: "Withdraw",
        borrow: "Borrow",
        repay: "Repay",
        swap: "Swap",
        transfer: "Transfer",
    };
    const typeFilters: { key: TxTypeFilter; label: string }[] = [
        {key: "all", label: "All"},
        {key: "earn", label: "Inflow"},
        {key: "cost", label: "Outflow"},
        {key: "transfer", label: "Transfer"},
    ];
    const actionFilters: { key: TxActionFilter; label: string }[] = [
        {key: "all", label: "All actions"},
        {key: "deposit", label: "Deposit"},
        {key: "withdraw", label: "Withdraw"},
        {key: "borrow", label: "Borrow"},
        {key: "repay", label: "Repay"},
        {key: "swap", label: "Swap"},
        {key: "transfer", label: "Transfer"},
    ];

    const sortedPnlFlows = useMemo(() => {
        return [...pnlFlows].sort((a, b) =>
            Math.abs(b.currentValueUsd || b.estimatedPnlUsd || 0) - Math.abs(a.currentValueUsd || a.estimatedPnlUsd || 0)
        );
    }, [pnlFlows]);
    const selectedFlow = sortedPnlFlows.find((flow) => flow.flowKey === selectedFlowKey) || sortedPnlFlows[0];

    const filteredTransactions = useMemo(() => {
        const normalizedQuery = query.trim().toLowerCase();
        return transactions.filter((tx) => {
            const action = (tx.action ?? "").toLowerCase();
            const category = (tx.transactionCategory ?? "").toLowerCase();
            const matchesType = typeFilter === "all" || tx.type === typeFilter;
            const matchesAction = actionFilter === "all" ||
                action === actionFilter ||
                (actionFilter === "swap" && (category === "swap" || action === "buy" || action === "sell")) ||
                (actionFilter === "transfer" && (category === "transfer" || action === "transfer_in" || action === "transfer_out"));
            const matchesQuery = !normalizedQuery ||
                tx.symbol?.toLowerCase().includes(normalizedQuery) ||
                tx.source?.toLowerCase().includes(normalizedQuery) ||
                tx.poolLabel?.toLowerCase().includes(normalizedQuery) ||
                tx.description?.toLowerCase().includes(normalizedQuery) ||
                tx.txId?.toLowerCase().includes(normalizedQuery);
            return matchesType && matchesAction && matchesQuery;
        });
    }, [actionFilter, query, transactions, typeFilter]);
    const transactionCountLabel = transactions.length
        ? `${filteredTransactions.length}/${transactions.length} tx`
        : "0 tx";
    const emptyTransactionMessage = transactions.length
        ? "No transactions match the current filters."
        : "No supported cashflow transactions found.";

    return (
        <Div className="overflow-hidden">
            <div className="mb-4 flex flex-col gap-3">
                <div className="flex items-start justify-between gap-3">
                    <div>
                        <p className={cn("text-sm font-semibold", ui.text.heading)}>Transaction History</p>
                        <p className={cn("mt-1 text-xs", ui.text.muted)}>
                            Filtered cashflow from supported token transactions
                        </p>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="grid grid-cols-2 rounded-lg bg-violet-50 p-1 dark:bg-violet-950/25">
                            {[
                                {key: "transactions" as ViewMode, label: "Transactions"},
                                {key: "pools" as ViewMode, label: "PnL Flow"},
                            ].map((item) => (
                                <button
                                    key={item.key}
                                    onClick={() => setViewMode(item.key)}
                                    className={cn(
                                        "rounded-md px-3 py-1.5 text-[11px] font-semibold transition-all",
                                        viewMode === item.key
                                            ? "border border-violet-200 bg-violet-50 text-violet-800 hover:border-violet-300 hover:bg-violet-100 dark:border-violet-800/60 dark:bg-violet-950/35 dark:text-violet-200 dark:hover:bg-violet-900/25"
                                            : "text-zinc-500 hover:bg-violet-50/70 hover:text-violet-700 dark:hover:bg-violet-950/25 dark:hover:text-violet-300"
                                    )}
                                >
                                    {item.label}
                                </button>
                            ))}
                        </div>
                        <span
                            className="rounded-md bg-violet-50 px-2 py-1 text-[10px] font-medium text-violet-600 dark:bg-violet-950/30 dark:text-violet-300">
                            {viewMode === "pools" ? `${sortedPnlFlows.length} positions` : transactionCountLabel}
                        </span>
                    </div>
                </div>

                {viewMode === "transactions" && (
                <div className="flex flex-col gap-3 rounded-lg border border-violet-100 bg-violet-50/45 p-3 dark:border-violet-900/35 dark:bg-violet-950/15">
                    <div className="flex flex-wrap gap-1.5">
                        {typeFilters.map((filter) => (
                            <button
                                key={filter.key}
                                onClick={() => setTypeFilter(filter.key)}
                                className={cn(
                                    "rounded-lg border px-2.5 py-1 text-[11px] font-medium transition-colors",
                                    typeFilter === filter.key
                                        ? "border border-violet-200 bg-violet-50 text-violet-800 hover:border-violet-300 hover:bg-violet-100 dark:border-violet-800/60 dark:bg-violet-950/35 dark:text-violet-200 dark:hover:bg-violet-900/25"
                                        : "border-violet-100 text-zinc-500 hover:bg-violet-50 hover:text-violet-700 dark:border-violet-900/40 dark:hover:bg-violet-950/30 dark:hover:text-violet-300"
                                )}
                            >
                                {filter.label}
                            </button>
                        ))}
                    </div>

                    <div className="grid gap-2 md:grid-cols-[190px_1fr]">
                        <Select
                            label="Action"
                            value={actionFilter}
                            onChange={(next) => setActionFilter(next as TxActionFilter)}
                            options={actionFilters.map((filter) => ({label: filter.label, value: filter.key}))}
                        />

                        <label className="relative block">
                            <span className="pointer-events-none absolute left-3 top-1.5 text-[9px] font-semibold uppercase tracking-wider text-violet-500 dark:text-violet-300">
                                Search
                            </span>
                            <Search
                                size={14}
                                className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400"
                            />
                            <input
                                className="h-12 w-full rounded-lg border border-violet-100 bg-white px-3 pb-1.5 pr-9 pt-5 text-xs font-semibold text-zinc-800 outline-none transition-colors placeholder:font-medium placeholder:text-zinc-400 focus:border-violet-300 focus:ring-2 focus:ring-violet-100 dark:border-violet-900/50 dark:bg-zinc-950 dark:text-zinc-100 dark:focus:border-violet-700 dark:focus:ring-violet-950/40"
                                value={query}
                                onChange={(event) => setQuery(event.target.value)}
                                placeholder="Token, source, tx hash..."
                            />
                        </label>
                    </div>
                </div>
                )}
            </div>

            {viewMode === "pools" ? (
                !sortedPnlFlows.length ? (
                    <div className="rounded-lg border border-dashed border-violet-100 p-6 text-center text-xs text-zinc-500 dark:border-violet-900/40">
                        No protocol PnL flow available.
                    </div>
                ) : (
                    <PnLFlowView
                        flows={sortedPnlFlows}
                        selectedFlow={selectedFlow}
                        onSelect={setSelectedFlowKey}
                    />
                )
            ) : !filteredTransactions.length ? (
                <div className="rounded-lg border border-dashed border-violet-100 p-6 text-center text-xs text-zinc-500 dark:border-violet-900/40">
                    {emptyTransactionMessage}
                </div>
            ) : (
                <div className="max-h-[430px] overflow-y-auto pr-1">
                    {filteredTransactions.map((tx, i) => (
                        <div key={tx.id}>
                            <div className="grid gap-3 py-3 sm:grid-cols-[1fr_auto]">
                                <div className="flex min-w-0 items-start gap-2.5">
                                    <div className="relative shrink-0">
                                        {tx.symbol ? (
                                            <TokenIcon symbol={tx.symbol} size={28}/>
                                        ) : (
                                            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-violet-50 text-[10px] font-semibold text-violet-600 dark:bg-violet-950/30 dark:text-violet-300">
                                                TX
                                            </div>
                                        )}
                                        <div className={cn("absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-white dark:border-zinc-950", dotColor[tx.type])}/>
                                    </div>
                                    <div className="min-w-0">
                                        <div className="flex flex-wrap items-center gap-1.5">
                                            <p className="text-xs font-semibold text-zinc-800 dark:text-zinc-100">
                                                {tx.action ? actionLabel[tx.action] ?? tx.action : tx.description}
                                                {tx.symbol ? ` ${tx.symbol}` : ""}
                                            </p>
                                            {tx.action && (
                                                <span className="rounded bg-violet-50 px-1.5 py-0.5 text-[9px] font-semibold uppercase text-violet-600 dark:bg-violet-950/30 dark:text-violet-300">
                                                    {tx.action}
                                                </span>
                                            )}
                                        </div>
                                        <p className="mt-0.5 truncate text-[10px] text-zinc-400">
                                            {tx.timeAgo} · {tx.source}
                                            {tx.amount ? ` · ${tx.amount.toLocaleString(undefined,
                                                {maximumFractionDigits: 6})} ${tx.symbol ?? ""}` : ""}
                                        </p>
                                    </div>
                                </div>

                                <div className="flex items-start justify-between gap-5 sm:justify-end">
                                    <div className="grid grid-cols-2 gap-2 text-right">
                                        <div>
                                            <p className="text-[10px] text-zinc-400">Price</p>
                                            <p className={cn("text-[11px] font-semibold tabular-nums", ui.text.heading)}>
                                                {tx.estimatedExecutionPrice
                                                    ? `$${tx.estimatedExecutionPrice.toLocaleString(undefined,
                                                        {maximumFractionDigits: 6})}`
                                                    : "-"}
                                            </p>
                                            <p
                                                className={cn("mt-0.5 text-[9px]", tx.priceReliable === false ? "text-amber-600 dark:text-amber-300" : "text-zinc-400")}
                                                title={tx.priceNote || undefined}
                                            >
                                                {formatPriceEvidence(tx)}
                                            </p>
                                        </div>
                                        <div>
                                            <p className="text-[10px] text-zinc-400">Recorded</p>
                                            <p className={cn("text-[11px] font-semibold tabular-nums", ui.text.heading)}>
                                                {tx.recordedAmountUsd != null
                                                    ? `$${tx.recordedAmountUsd.toLocaleString(undefined,
                                                        {maximumFractionDigits: 2})}`
                                                    : "-"}
                                            </p>
                                        </div>
                                    </div>
                                    <span className={cn("w-24 shrink-0 text-right text-xs font-semibold tabular-nums",
                                        tx.type === "earn" ? "text-emerald-600 dark:text-emerald-400" : tx.type === "cost" ? "text-red-600 dark:text-red-400" : "text-violet-600 dark:text-violet-300"
                                    )}>
                                        {tx.type === "earn" ? "+" : tx.type === "cost" ? "-" : ""}
                                        ${Math.abs(tx.amountUsd)
                                        .toLocaleString(undefined,
                                            {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                                    </span>
                                </div>
                            </div>
                            {i < filteredTransactions.length - 1 &&
                                <div className="border-t border-dashed border-violet-100 dark:border-violet-900/40"/>}
                        </div>
                    ))}
                </div>
            )}
        </Div>
    );
}

function PnLFlowView({
    flows,
    selectedFlow,
    onSelect,
}: {
    flows: TPnLFlow[];
    selectedFlow?: TPnLFlow;
    onSelect: (flowKey: string) => void;
}) {
    return (
        <div className="grid min-h-[520px] gap-3 lg:grid-cols-[340px_1fr]">
            <div className="max-h-[560px] overflow-y-auto rounded-xl border border-violet-100 bg-violet-50/30 p-2 dark:border-violet-900/40 dark:bg-violet-950/10">
                <div className="px-2 pb-2">
                    <p className={cn("text-xs font-semibold uppercase tracking-wider", ui.text.heading)}>Positions</p>
                    <p className="mt-1 text-[11px] text-zinc-500">Open and historical protocol positions from Mongo snapshots.</p>
                </div>
                <div className="space-y-2">
                    {flows.map((flow) => {
                        const active = selectedFlow?.flowKey === flow.flowKey;
                        const pnlReliable = flow.pnlReliable !== false;
                        return (
                            <button
                                key={flow.flowKey}
                                onClick={() => onSelect(flow.flowKey)}
                                className={cn(
                                    "w-full rounded-lg border p-3 text-left transition-all",
                                    active
                                        ? "border border-violet-200 bg-violet-50 text-violet-800 hover:border-violet-300 hover:bg-violet-100 dark:border-violet-800/60 dark:bg-violet-950/35 dark:text-violet-200 dark:hover:bg-violet-900/25"
                                        : "border-violet-100 bg-violet-50/30 hover:border-violet-300 hover:bg-violet-50/60 dark:border-violet-900/40 dark:bg-zinc-950/35 dark:hover:bg-violet-950/20"
                                )}
                            >
                                <div className="flex items-start gap-2.5">
                                    {flow.symbols.length > 1 ? (
                                        <TokenPairIcon symbols={flow.symbols} size={30}/>
                                    ) : (
                                        <TokenIcon symbol={flow.symbols[0] || "POOL"} size={30}/>
                                    )}
                                    <div className="min-w-0 flex-1">
                                        <div className="flex items-center justify-between gap-2">
                                            <p className="truncate text-sm font-semibold">{flow.label}</p>
                                            <span className={cn("rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase", active ? "bg-white/15 text-white" : "bg-violet-50 text-violet-700 dark:bg-violet-950/30 dark:text-violet-300")}>
                                                {flow.status}
                                            </span>
                                        </div>
                                        <p className={cn("mt-1 truncate text-[11px]", active ? "text-violet-100" : "text-zinc-500")}>
                                            {normalizeProtocol(flow.protocol)} · {flow.type === "lp" ? "LP" : flow.side || "Lending"}
                                        </p>
                                        <div className="mt-2 flex items-end justify-between gap-3">
                                            <div>
                                                <p className={cn("text-[10px]", active ? "text-violet-100" : "text-zinc-400")}>Current</p>
                                                <p className="text-xs font-semibold tabular-nums">{formatMoney(flow.currentValueUsd)}</p>
                                            </div>
                                            <div className="text-right">
                                                <p className={cn("text-[10px]", active ? "text-violet-100" : "text-zinc-400")}>Est. PnL</p>
                                                {pnlReliable ? (
                                                    <p className={cn("text-xs font-semibold tabular-nums", active ? "text-white" : flow.estimatedPnlUsd >= 0 ? ui.text.up : ui.text.down)}>
                                                        {flow.estimatedPnlUsd >= 0 ? "+" : ""}{formatMoney(flow.estimatedPnlUsd)}
                                                    </p>
                                                ) : (
                                                    <p className={cn("text-xs font-semibold tabular-nums", active ? "text-violet-100" : "text-zinc-400")}>—</p>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </button>
                        );
                    })}
                </div>
            </div>

            {selectedFlow ? <PnLFlowDetail flow={selectedFlow}/> : null}
        </div>
    );
}

function PnLFlowDetail({flow}: { flow: TPnLFlow }) {
    const simulatorMode = flow.type === "lp" ? "provide_liquidity" : flow.side === "BORROWER" ? "borrow" : "lend";
    const primarySymbol = flow.marketLinkSymbol || flow.symbols[0] || "";
    const pnlReliable = flow.pnlReliable !== false;

    return (
        <div className="min-w-0 rounded-xl border border-violet-100 bg-white/75 p-4 dark:border-violet-900/40 dark:bg-zinc-950/35">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex min-w-0 items-center gap-3">
                    {flow.symbols.length > 1 ? (
                        <TokenPairIcon symbols={flow.symbols} size={36}/>
                    ) : (
                        <TokenIcon symbol={primarySymbol || "POOL"} size={34}/>
                    )}
                    <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-1.5">
                            <p className={cn("truncate text-base font-semibold", ui.text.heading)}>{flow.label}</p>
                            <span className="rounded bg-violet-100 px-1.5 py-0.5 text-[9px] font-semibold uppercase text-violet-700 dark:bg-violet-950/40 dark:text-violet-300">
                                {normalizeProtocol(flow.protocol)}
                            </span>
                        </div>
                        <p className="mt-1 truncate text-[11px] text-zinc-500">
                            {flow.symbols.join(" / ") || "Unknown token"} · {flow.transactionCount} pool transactions
                            {flow.lastTimestamp ? ` · last ${formatPoolDate(flow.lastTimestamp)}` : ""}
                        </p>
                    </div>
                </div>
                <div className="flex flex-wrap gap-2">
                    {primarySymbol && (
                        <Link
                            href={`/markets?symbol=${encodeURIComponent(primarySymbol)}${flow.marketId ? `&marketId=${encodeURIComponent(flow.marketId)}` : ""}`}
                            className="inline-flex items-center gap-1 rounded-md border border-violet-100 bg-white px-2.5 py-1.5 text-[10px] font-semibold text-violet-700 transition-colors hover:bg-violet-50 dark:border-violet-900/40 dark:bg-zinc-950 dark:text-violet-300 dark:hover:bg-violet-950/30"
                        >
                            View market <ArrowUpRight size={10}/>
                        </Link>
                    )}
                    {primarySymbol && (
                        <Link
                            href={`/simulator?mode=${simulatorMode}&symbol=${encodeURIComponent(primarySymbol)}${flow.marketId ? `&marketId=${encodeURIComponent(flow.marketId)}` : ""}`}
                            className="inline-flex items-center gap-1 rounded-md border border-violet-200 bg-violet-50 px-2.5 py-1.5 text-[10px] font-semibold text-violet-800 transition-colors hover:border-violet-300 hover:bg-violet-100 dark:border-violet-800/60 dark:bg-violet-950/35 dark:text-violet-200 dark:hover:bg-violet-900/25"
                        >
                            Simulate <Wand2 size={10}/>
                        </Link>
                    )}
                </div>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-2 xl:grid-cols-5">
                <Metric label="Current Value" value={flow.currentValueUsd}/>
                <Metric label="Supplied / Paid" value={flow.outflowUsd}/>
                <Metric label="Received" value={flow.inflowUsd}/>
                <Metric label="Gas" value={flow.gasUsd}/>
                <Metric
                    label="Est. PnL"
                    value={flow.estimatedPnlUsd}
                    signed
                    tone={flow.estimatedPnlUsd >= 0 ? "up" : "down"}
                    unavailable={!pnlReliable}
                />
            </div>

            <div className="mt-3 rounded-lg border border-violet-100 bg-violet-50/45 px-3 py-2 text-[11px] text-zinc-500 dark:border-violet-900/40 dark:bg-violet-950/15">
                {pnlReliable ? `Formula: ${flow.formula || "current value + received - supplied - gas"}.` : (flow.pnlNote || "PnL is not calculated for this flow yet.")}
                {" "}This view only includes protocol pool transactions, not plain wallet transfers.
            </div>

            <div className="mt-4">
                <p className={cn("mb-2 text-xs font-semibold uppercase tracking-wider", ui.text.heading)}>Pool transaction timeline</p>
                {flow.events.length ? (
                    <div className="space-y-2 overflow-y-auto pr-1">
                        {flow.events.map((event) => (
                            <div key={event.id} className="rounded-lg border border-violet-100 bg-violet-50/35 p-3 dark:border-violet-900/40 dark:bg-violet-950/15">
                                <div className="flex flex-wrap items-start justify-between gap-3">
                                    <div className="min-w-0">
                                        <div className="flex flex-wrap items-center gap-1.5">
                                            <span className={cn("rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase", event.direction === "in" ? "bg-emerald-50 text-emerald-600 dark:bg-emerald-950/30 dark:text-emerald-300" : "bg-red-50 text-red-600 dark:bg-red-950/30 dark:text-red-300")}>
                                                {event.actionLabel || formatActionName(event.action || "event")}
                                            </span>
                                            <p className={cn("truncate text-xs font-semibold", ui.text.heading)}>
                                                {formatFlowEventTitle(event)}
                                            </p>
                                        </div>
                                        <p className="mt-1 text-[10px] text-zinc-500">
                                            {event.timeAgo || formatPoolDate(event.timestamp)}
                                            {event.txHash ? ` · ${shortHash(event.txHash)}` : ""}
                                        </p>
                                    </div>
                                    {event.explorerUrl && (
                                        <a
                                            href={event.explorerUrl}
                                            target="_blank"
                                            rel="noreferrer"
                                            className="inline-flex items-center gap-1 rounded-md border border-violet-100 bg-white px-2 py-1 text-[10px] font-semibold text-violet-700 hover:bg-violet-50 dark:border-violet-900/40 dark:bg-zinc-950 dark:text-violet-300"
                                        >
                                            Tx <ExternalLink size={10}/>
                                        </a>
                                    )}
                                </div>
                                <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
                                    <SmallMetric label="Token Amount" value={`${formatAmount(event.amount || 0)} ${event.symbol || ""}`}/>
                                    <SmallMetric label="Price At Tx" value={event.priceAtTx ? `$${event.priceAtTx.toLocaleString(undefined, {maximumFractionDigits: 6})}` : "-"}/>
                                    {/*<SmallMetric label="Price Delta" value={formatPriceEvidence(event)}/>*/}
                                    <SmallMetric label="USD Value" value={formatMoney(event.amountUsd || event.recordedAmountUsd || 0)}/>
                                    <SmallMetric label="Gas" value={formatMoney(event.gasCostUsd || 0)}/>
                                </div>
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="rounded-lg border border-dashed border-violet-100 p-6 text-center text-xs text-zinc-500 dark:border-violet-900/40">
                        Position snapshot exists, but no pool transaction has been crawled yet.
                    </div>
                )}
            </div>
        </div>
    );
}

function normalizeProtocol(protocol?: string) {
    const value = String(protocol || "unknown").replace(/_/g, " ").trim();
    if (!value || value.toLowerCase() === "unknown") return "Unknown protocol";
    return value
        .split(" ")
        .map((part) => part ? part[0].toUpperCase() + part.slice(1) : part)
        .join(" ");
}

function formatActionName(action: string) {
    return action.replace(/_/g, " ");
}

function formatPoolDate(timestamp: number) {
    return new Date(timestamp * 1000).toLocaleDateString("en-US", {month: "short", day: "numeric"});
}

function formatMoney(value: number) {
    return `$${Number(value || 0).toLocaleString(undefined, {maximumFractionDigits: 2})}`;
}

function formatAmount(value: number) {
    return Number(value || 0).toLocaleString(undefined, {maximumFractionDigits: 6});
}

function formatUsdPrice(value?: number | null) {
    if (!value) return "";
    if (Math.abs(value) >= 1) {
        return `$${value.toLocaleString(undefined, {maximumFractionDigits: 2})}`;
    }
    return `$${value.toLocaleString(undefined, {maximumFractionDigits: 6})}`;
}

function formatPriceEvidence(row: PriceEvidence) {
    const source = formatPriceSource(row.priceSource);
    if (row.priceDeltaSeconds == null) {
        return row.priceReliable === false ? "Unverified price" : source;
    }
    const delta = `Δ ${formatPriceDelta(row.priceDeltaSeconds)}`;
    return row.priceReliable === false ? `Unverified · ${delta}` : delta;
}

function formatPriceSource(source?: string | null) {
    if (!source) return "No snapshot";
    return source.replace(/_/g, " ");
}

function formatPriceDelta(seconds: number) {
    const absolute = Math.abs(Number(seconds || 0));
    if (absolute < 60) return `${Math.round(absolute)}s`;
    if (absolute < 3600) return `${Math.round(absolute / 60)}m`;
    if (absolute < 86400) return `${Math.round(absolute / 3600)}h`;
    return `${Math.round(absolute / 86400)}d`;
}

function formatFlowEventTitle(event: TPnLFlowEvent) {
    const action = event.actionLabel || formatActionName(event.action || "Event");
    const amount = formatAmount(event.amount || 0);
    const symbol = event.symbol || "";
    const price = event.priceAtTx ? ` @ ${formatUsdPrice(event.priceAtTx)}` : "";
    const value = event.amountUsd || event.recordedAmountUsd
        ? ` · ${formatMoney(event.amountUsd || event.recordedAmountUsd || 0)}`
        : "";
    return `${action} ${amount} ${symbol}${price}${value}`.trim();
}

function shortHash(hash: string) {
    return hash.length > 12 ? `${hash.slice(0, 6)}...${hash.slice(-4)}` : hash;
}

function SmallMetric({label, value}: { label: string; value: string }) {
    return (
        <div>
            <p className="text-[10px] uppercase tracking-wider text-zinc-400">{label}</p>
            <p className={cn("mt-0.5 truncate text-[11px] font-semibold tabular-nums", ui.text.heading)}>{value}</p>
        </div>
    );
}

function Metric({
    label,
    value,
    signed = false,
    tone,
    unavailable = false,
}: {
    label: string;
    value: number;
    signed?: boolean;
    tone?: "up" | "down";
    unavailable?: boolean;
}) {
    const color = tone === "up" ? ui.text.up : tone === "down" ? ui.text.down : ui.text.heading;
    return (
        <div className="rounded-lg border border-violet-100 bg-white/70 px-3 py-2 dark:border-violet-900/40 dark:bg-zinc-950/30">
            <p className="text-[10px] uppercase tracking-wider text-zinc-400">{label}</p>
            <p className={cn("mt-1 text-xs font-semibold tabular-nums", unavailable ? "text-zinc-400" : color)}>
                {unavailable ? "—" : `${signed && value > 0 ? "+" : ""}$${value.toLocaleString(undefined, {maximumFractionDigits: 2})}`}
            </p>
        </div>
    );
}
