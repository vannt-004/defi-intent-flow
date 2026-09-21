import {Activity, ShieldCheck, TrendingUp, Wallet} from "lucide-react";

import Div from "@/components/ui/Div";
import PnLText from "@/components/dashboard/PnLText";
import Skeleton from "@/components/common/Skeleton";
import {cn} from "@/utils/cn";
import {formatMoney} from "@/utils/format";
import {ui} from "@/styles/ui";
import {TNetWorth, TPnLSummary, TPositionSummary} from "@/types/portfolio";

type Props = {
    summary?: TPositionSummary;
    netWorth?: TNetWorth;
    pnl?: TPnLSummary;
    isPending: boolean;
};

export default function PortfolioOverview({summary, netWorth, pnl, isPending}: Props) {
    const totalUsd = netWorth?.totalUsd ?? summary?.netWorthUsd ?? 0;
    const metricItems = [
        {
            label: "Wallet",
            value: summary?.totalWalletUsd ?? netWorth?.tokenHoldUsd ?? 0,
            icon: <Wallet size={13} className="text-violet-500"/>,
        },
        {
            label: "Lending",
            value: summary?.totalSupplyUsd ?? netWorth?.lendingUsd ?? 0,
            icon: <TrendingUp size={13} className="text-emerald-500"/>,
        },
        {
            label: "AMM / LP",
            value: summary?.totalAmmUsd ?? netWorth?.farmingUsd ?? 0,
            icon: <Activity size={13} className="text-violet-500"/>,
        },
        {
            label: "Collateral",
            value: summary?.collateralUsd ?? 0,
            icon: <ShieldCheck size={13} className="text-violet-500"/>,
        },
    ];

    const formulaItems = netWorth ? [
        {label: "Token Hold", value: netWorth.tokenHoldUsd},
        {label: "Supply", value: netWorth.supplyUsd ?? netWorth.lendingUsd + netWorth.interestEarnedUsd},
        {label: "LP / Farming", value: netWorth.lpUsd ?? netWorth.farmingUsd},
        {label: "Vault", value: netWorth.vaultUsd ?? 0},
        {label: "Borrow", value: -(netWorth.borrowUsd ?? netWorth.debtUsd + netWorth.debtInterestUsd), debt: true},
    ] : [];

    return (
        <Div>
            <div className="grid gap-5 xl:grid-cols-[1.1fr_1fr]">
                <div>
                    <p className="text-xs font-semibold uppercase tracking-wider text-violet-500 dark:text-violet-400">
                        Portfolio Net Worth
                    </p>
                    {isPending ? (
                        <Skeleton className="mt-2 h-10 w-64"/>
                    ) : (
                        <p className="mt-1 text-3xl font-semibold tracking-tight text-zinc-950 dark:text-zinc-50 md:text-4xl">
                            {formatMoney(totalUsd)}
                        </p>
                    )}
                    <p className={cn("mt-2 max-w-xl text-xs", ui.text.muted)}>
                        Net worth = token hold + supply + LP + vault - borrow.
                    </p>

                    <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
                        {metricItems.map((item) => (
                            <div
                                key={item.label}
                                className="rounded-lg border border-violet-100 bg-violet-50/45 px-3 py-2.5 dark:border-violet-900/35 dark:bg-violet-950/15"
                            >
                                <div className="mb-1 flex items-center justify-between gap-2">
                                    <p className="text-[10px] font-medium uppercase tracking-wider text-zinc-500">
                                        {item.label}
                                    </p>
                                    {item.icon}
                                </div>
                                {isPending ? (
                                    <Skeleton className="h-5 w-20"/>
                                ) : (
                                    <p className={cn("text-sm font-semibold tabular-nums", ui.text.heading)}>
                                        {formatMoney(item.value)}
                                    </p>
                                )}
                            </div>
                        ))}
                    </div>
                </div>

                <div className="space-y-3">
                    <div className="grid grid-cols-3 gap-2">
                        {[
                            {label: "Today", usd: pnl?.todayUsd ?? 0, pct: pnl?.todayPct},
                            {label: "7 Days", usd: pnl?.sevenDayUsd ?? 0, pct: pnl?.sevenDayPct},
                            {label: "All Time", usd: pnl?.allTimeUsd ?? 0, pct: pnl?.allTimePct},
                        ].map((item) => (
                            <div
                                key={item.label}
                                className="rounded-lg border border-violet-100 bg-white px-3 py-2.5 dark:border-violet-900/40 dark:bg-zinc-950"
                            >
                                <p className="text-[10px] text-zinc-500">{item.label}</p>
                                {pnl?.method === "net_worth_delta_minus_external_flow" && (
                                    <p className="mt-0.5 text-[9px] text-zinc-400">External-flow adjusted</p>
                                )}
                                {isPending ? (
                                    <Skeleton className="mt-1 h-5 w-20"/>
                                ) : (
                                    <PnLText value={item.usd} pct={item.pct} size="sm"/>
                                )}
                            </div>
                        ))}
                    </div>

                    <div className="rounded-lg border border-violet-100 bg-violet-50/45 p-3 dark:border-violet-900/35 dark:bg-violet-950/15">
                        <div className="mb-2 flex items-center justify-between">
                            <p className={cn("text-xs font-semibold", ui.text.heading)}>Net Worth Formula</p>
                            {summary?.positionCount != null && (
                                <span className="rounded-md bg-violet-100 px-2 py-1 text-[10px] font-semibold text-violet-700 dark:bg-violet-950/40 dark:text-violet-300">
                                    {summary.positionCount} positions
                                </span>
                            )}
                        </div>
                        <div className="space-y-2">
                            {isPending ? (
                                <>
                                    <Skeleton className="h-6"/>
                                    <Skeleton className="h-6"/>
                                    <Skeleton className="h-6"/>
                                </>
                            ) : formulaItems.map((item) => (
                                <div key={item.label} className="flex items-center justify-between gap-3 text-xs">
                                    <span className="text-zinc-500">{item.label}</span>
                                    <span className={cn("font-semibold tabular-nums", item.debt ? ui.text.down : ui.text.heading)}>
                                        {formatMoney(item.value)}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </Div>
    );
}
