import {AlertTriangle, ShieldCheck} from "lucide-react";

import Div from "@/components/ui/Div";
import Skeleton from "@/components/common/Skeleton";
import {cn} from "@/utils/cn";
import {formatMoney} from "@/utils/format";
import {ui} from "@/styles/ui";
import {TAlert, TPositionPnL, TPositionSummary} from "@/types/portfolio";

type Props = {
    summary?: TPositionSummary;
    positions: TPositionPnL[];
    alerts: TAlert[];
    isPending: boolean;
};

function riskLevel(healthFactor: number, borrowRatio: number) {
    if (healthFactor && healthFactor < 1.1) return {label: "High Risk", color: "text-red-600 dark:text-red-400"};
    if (borrowRatio > 75 || (healthFactor && healthFactor < 1.5)) {
        return {label: "Watch", color: "text-amber-600 dark:text-amber-400"};
    }
    return {label: "Healthy", color: "text-emerald-600 dark:text-emerald-400"};
}

export default function RiskEnginePanel({summary, positions, alerts, isPending}: Props) {
    const grossAssets = (summary?.totalWalletUsd ?? 0) + (summary?.totalSupplyUsd ?? 0) + (summary?.totalAmmUsd ?? 0);
    const debtUsd = summary?.totalBorrowUsd ?? 0;
    const borrowRatio = grossAssets > 0 ? (debtUsd / grossAssets) * 100 : 0;
    const healthFactor = summary?.healthFactor ?? 0;
    const level = riskLevel(healthFactor, borrowRatio);
    const weakPositions = positions
        .filter((p) => p.healthFactor < 50 || p.type === "borrow")
        .slice(0, 3);

    return (
        <Div>
            <div className="mb-4 flex items-start justify-between gap-3">
                <div>
                    <p className={cn("text-sm font-semibold", ui.text.heading)}>Risk Engine</p>
                    <p className={cn("mt-1 text-xs", ui.text.muted)}>Debt, collateral, and liquidation signals</p>
                </div>
                <ShieldCheck size={18} className="text-violet-500"/>
            </div>

            {isPending ? (
                <div className="space-y-3">
                    <Skeleton className="h-16"/>
                    <Skeleton className="h-16"/>
                    <Skeleton className="h-20"/>
                </div>
            ) : (
                <>
                    <div className="grid grid-cols-2 gap-3">
                        <div className="rounded-lg border border-violet-100 bg-violet-50/45 p-3 dark:border-violet-900/35 dark:bg-violet-950/15">
                            <p className="text-[10px] uppercase tracking-wider text-zinc-500">Status</p>
                            <p className={cn("mt-1 text-base font-semibold", level.color)}>{level.label}</p>
                        </div>
                        <div className="rounded-lg border border-violet-100 bg-violet-50/45 p-3 dark:border-violet-900/35 dark:bg-violet-950/15">
                            <p className="text-[10px] uppercase tracking-wider text-zinc-500">Health Factor</p>
                            <p className={cn("mt-1 text-base font-semibold tabular-nums", ui.text.heading)}>
                                {!healthFactor || healthFactor === 999 ? "∞" : healthFactor.toFixed(2)}
                            </p>
                        </div>
                    </div>

                    <div className="mt-4">
                        <div className="mb-2 flex justify-between text-[11px]">
                            <span className="font-medium text-zinc-500">Borrow Utilization</span>
                            <span className={cn("font-semibold tabular-nums", borrowRatio > 75 ? ui.text.down : ui.text.heading)}>
                                {borrowRatio.toFixed(1)}%
                            </span>
                        </div>
                        <div className="h-2 overflow-hidden rounded-full bg-violet-100 dark:bg-violet-950/50">
                            <div
                                className={cn("h-full rounded-full transition-all", borrowRatio > 75 ? "bg-red-500" : "bg-violet-500")}
                                style={{width: `${Math.min(borrowRatio, 100)}%`}}
                            />
                        </div>
                    </div>

                    <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
                        <div>
                            <p className="text-zinc-500">Collateral</p>
                            <p className={cn("mt-0.5 font-semibold tabular-nums", ui.text.heading)}>
                                {formatMoney(summary?.collateralUsd ?? 0)}
                            </p>
                        </div>
                        <div>
                            <p className="text-zinc-500">Borrowed</p>
                            <p className={cn("mt-0.5 font-semibold tabular-nums", debtUsd > 0 ? ui.text.down : ui.text.heading)}>
                                {formatMoney(debtUsd)}
                            </p>
                        </div>
                    </div>

                    <div className="mt-4 border-t border-violet-100 pt-4 dark:border-violet-900/40">
                        <p className={cn("mb-2 text-xs font-semibold", ui.text.heading)}>Risk Signals</p>
                        <div className="space-y-2">
                            {alerts.slice(0, 2).map((alert) => (
                                <div key={alert.id} className="flex gap-2 rounded-lg bg-amber-50 p-2 dark:bg-amber-950/25">
                                    <AlertTriangle size={13} className="mt-0.5 shrink-0 text-amber-500"/>
                                    <div>
                                        <p className="text-[11px] font-semibold text-amber-700 dark:text-amber-300">{alert.title}</p>
                                        <p className="mt-0.5 text-[10px] text-zinc-500 dark:text-zinc-400">{alert.message}</p>
                                    </div>
                                </div>
                            ))}
                            {!alerts.length && !weakPositions.length && (
                                <p className="rounded-lg bg-violet-50 p-2 text-[11px] text-zinc-500 dark:bg-violet-950/20">
                                    No critical risk signal for supported positions.
                                </p>
                            )}
                            {weakPositions.map((position) => (
                                <div key={position.positionId} className="flex items-center justify-between gap-3 rounded-lg bg-violet-50 p-2 text-[11px] dark:bg-violet-950/20">
                                    <span className="truncate text-zinc-500">{position.name}</span>
                                    <span className={cn("font-semibold", position.healthFactor < 50 ? ui.text.down : ui.text.heading)}>
                                        {position.type === "borrow" ? "Borrow" : `${position.healthFactor}%`}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>
                </>
            )}
        </Div>
    );
}
