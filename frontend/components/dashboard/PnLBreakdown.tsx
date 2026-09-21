"use client";

import {cn} from "@/utils/cn";
import {ui} from "@/styles/ui";
import PnLText from "@/components/dashboard/PnLText";
import {TNetWorth, TPositionPnL} from "@/types/portfolio";
import Div from "@/components/ui/Div";
import {useAgentFocus} from "@/components/assistant/AgentFocusContext";
import InfoTooltip from "@/components/ui/InfoTooltip";

export default function PnLBreakdown({netWorth, positions}: { netWorth: TNetWorth; positions: TPositionPnL[] }) {
    const {focusClass} = useAgentFocus();
    const reliablePositions = positions.filter((p) => p.pnlReliable !== false);
    const tokenHoldPnl = reliablePositions
        .filter((p) => p.type === "hold")
        .reduce((sum, p) => sum + p.pnlUsd, 0);
    const lendingPnl = reliablePositions
        .filter((p) => p.type === "lend")
        .reduce((sum, p) => sum + p.pnlUsd, 0);
    const farmingPnl = reliablePositions
        .filter((p) => p.type === "farm")
        .reduce((sum, p) => sum + p.pnlUsd, 0);
    const borrowCost = reliablePositions
        .filter((p) => p.type === "borrow")
        .reduce((sum, p) => sum + p.pnlUsd, 0);
    const hasLendingRows = reliablePositions.some((p) => p.type === "lend");
    const hasTokenHoldRows = reliablePositions.some((p) => p.type === "hold");
    const hasFarmingRows = reliablePositions.some((p) => p.type === "farm");
    const hasBorrowRows = reliablePositions.some((p) => p.type === "borrow");
    const netPnl = tokenHoldPnl + lendingPnl + farmingPnl + borrowCost;

    const items = [
        {
            label: "Token Hold",
            value: tokenHoldPnl,
            sub: hasTokenHoldRows ? `$${netWorth.tokenHoldUsd.toLocaleString()} current value` : "Basis unknown",
            tooltip: "Wallet-token all-time PnL needs verified buy/sell average-cost basis. Tokens received by transfer, withdraw, or borrow stay visible by current value but are excluded from this PnL total.",
            color: "bg-emerald-500",
            focusKeys: ["dashboard:pnl:token-hold", "dashboard:pnl:wallet", "dashboard:token-hold"],
            skipped: !hasTokenHoldRows
        },
        {
            label: "Lending",
            value: lendingPnl,
            sub: hasLendingRows ? "Flow-based lending PnL" : "No verified flow",
            tooltip: "Lending PnL uses protocol cashflow when available: current supplied value + withdrawals - deposits - gas. Token cost basis is not required.",
            color: "bg-violet-500",
            focusKeys: ["dashboard:pnl:lending", "dashboard:pnl:supply"],
            skipped: !hasLendingRows
        },
        {
            label: "Farming / LP",
            value: farmingPnl,
            sub: hasFarmingRows ? "Flow-based LP PnL" : "Awaiting LP attribution",
            tooltip: "LP PnL is shown only when fee/yield and liquidity-flow attribution is reliable. Otherwise current LP value remains visible without PnL.",
            color: "bg-amber-400",
            focusKeys: ["dashboard:pnl:farming", "dashboard:pnl:lp"],
            skipped: !hasFarmingRows
        },
        {
            label: "Borrow Cost",
            value: borrowCost,
            sub: hasBorrowRows ? "Flow-based borrow cost" : "No verified debt flow",
            tooltip: "Borrow cost uses protocol cashflow when available: borrowed received - repaid - current debt - gas. Token cost basis is not required.",
            color: "bg-red-500",
            focusKeys: ["dashboard:pnl:borrow", "dashboard:pnl:borrow-cost"],
            skipped: !hasBorrowRows
        },
        {
            label: "Cost Basis",
            value: reliablePositions.reduce((sum, p) => sum + p.costBasisUsd, 0),
            sub: "Verified basis/capital",
            tooltip: "For wallet tokens this is verified remaining average-cost basis. For lending/borrow rows it is the protocol cashflow capital base used for ROI.",
            color: "bg-zinc-400",
            neutral: true,
            focusKeys: ["dashboard:pnl:cost-basis"]
        },
        {
            label: "Net PnL",
            value: netPnl,
            sub: "Estimated unrealized + realized",
            tooltip: "Sum of reliable rows only. Rows with unknown token basis or incomplete protocol flow are excluded instead of being treated as zero profit/loss.",
            color: "bg-violet-600",
            highlight: true,
            focusKeys: ["dashboard:pnl:net", "dashboard:pnl:net-pnl"],
            skipped: reliablePositions.length === 0
        },
    ];
    const pnlFocusKeys = ["dashboard:pnl", ...items.flatMap((item) => item.focusKeys)];

    return (
        <Div className={focusClass(pnlFocusKeys, "transition-all duration-200")}>
            <p className={cn("mb-1 text-sm font-semibold", ui.text.heading)}>PnL Analysis by Category</p>
            <p className={cn("mb-4 text-xs", ui.text.muted)}>Tracked from transaction history</p>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
                {items.map((item) => (
                    <div
                        key={item.label}
                        className={focusClass(item.focusKeys, cn(
                            "rounded-lg border px-3.5 py-3",
                            item.highlight
                                ? "border-violet-200 bg-violet-50 dark:border-violet-900/60 dark:bg-violet-950/30"
                                : "border-violet-100 bg-violet-50/40 dark:border-violet-900/30 dark:bg-violet-950/15"
                        ))}
                    >
                        <div className={cn("mb-1.5 h-0.5 w-6 rounded-full", item.color)}/>
                        <p className="flex items-center gap-1 text-[11px] text-zinc-500">
                            {item.label}
                            {item.tooltip ? <InfoTooltip text={item.tooltip}/> : null}
                        </p>
                        {item.skipped ? (
                            <p className={cn("text-sm font-semibold tabular-nums", ui.text.muted)}>—</p>
                        ) : item.neutral ? (
                            <p className={cn("text-sm font-semibold tabular-nums", ui.text.heading)}>
                                ${item.value.toLocaleString(undefined, {maximumFractionDigits: 0})}
                            </p>
                        ) : (
                            <PnLText value={item.value} size={item.highlight ? "md" : "sm"}/>
                        )}
                        <p className="mt-0.5 text-[10px] text-zinc-400">{item.sub}</p>
                    </div>
                ))}
            </div>
        </Div>
    );
}
