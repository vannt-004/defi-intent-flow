"use client";

import {formatMoney} from "@/utils/format";
import {TrendingUp, Activity, Wallet, Percent, ShieldCheck} from "lucide-react";
import React from "react";
import Skeleton from "@/components/common/Skeleton";
import {TPositionSummary} from "@/types/portfolio";
import Div from "@/components/ui/Div";

type Props = {
    summary: TPositionSummary | undefined;
    isPending: boolean;
};

export default function Summary(props: Props) {
    const {summary, isPending} = props;

    const {
        healthFactor = 0,
        netWorthUsd = 0,
        collateralUsd = 0,
        totalBorrowUsd = 0,
        totalSupplyUsd = 0,
        totalWalletUsd = 0,
        totalAmmUsd = 0,
        positionCount = 0,
    } = summary ?? {};

    const getHealthColorClass = (hf: number) => {
        if (hf === 999 || hf === 0 || totalBorrowUsd === 0) return "text-emerald-600 dark:text-emerald-400";
        if (hf < 1.1) return "text-red-600 font-extrabold dark:text-red-400";
        if (hf < 1.5) return "text-amber-600 dark:text-amber-400";
        return "text-emerald-600 dark:text-emerald-400";
    };

    const totalGrossAssets = totalSupplyUsd + totalWalletUsd + totalAmmUsd;
    const borrowRatio = totalGrossAssets > 0 ? (totalBorrowUsd / totalGrossAssets) * 100 : 0;

    return (
        <Div>
            <div className="flex flex-wrap items-end justify-between gap-4">
                <div className="space-y-1">
                    <p className="text-xs font-semibold uppercase tracking-wider text-violet-500 dark:text-violet-400">
                        Net Worth
                    </p>
                    <div className="flex items-baseline gap-3">
                        {isPending ? (
                            <Skeleton className="h-12 w-64 rounded-lg"/>
                        ) : (
                            <span className="text-3xl font-semibold tracking-tight text-zinc-950 tabular-nums dark:text-zinc-50 md:text-4xl">
                                {formatMoney(netWorthUsd)}
                            </span>
                        )}
                    </div>
                </div>

                <span
                    className="mb-1 flex items-center gap-1.5 rounded-full border border-violet-100 bg-violet-50 px-3 py-1.5 text-xs font-semibold text-violet-700 dark:border-violet-900/50 dark:bg-violet-950/30 dark:text-violet-300">
                    <TrendingUp size={13}/>
                    {isPending ? (
                        <Skeleton className="h-4 w-24"/>
                    ) : (
                        `${positionCount} Active Positions`
                    )}
                </span>
            </div>

            <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
                {[
                    {
                        label: "Wallet Balance",
                        value: formatMoney(totalWalletUsd),
                        icon: <Wallet size={12} className="text-violet-500"/>,
                    },
                    {
                        label: "Lending Supply",
                        value: formatMoney(totalSupplyUsd),
                        icon: <Percent size={12} className="text-emerald-500"/>,
                    },
                    {
                        label: "AMM Liquidity",
                        value: formatMoney(totalAmmUsd),
                        icon: <Activity size={12} className="text-violet-500"/>,
                    },
                    {
                        label: "Total Borrow",
                        value: formatMoney(totalBorrowUsd),
                        icon: <Percent size={12} className="text-orange-400"/>,
                        isDebt: true,
                    },
                    {
                        label: "Collateral Value",
                        value: formatMoney(collateralUsd),
                        icon: <ShieldCheck size={12} className="text-purple-400"/>,
                    },
                    {
                        label: "Health Factor",
                        value: !healthFactor || healthFactor === 999 ? "∞" : healthFactor.toFixed(2),
                        isHealth: true,
                    },
                ].map((item) => (
                    <div
                        key={item.label}
                        className="rounded-lg border border-violet-100/70 bg-violet-50/40 p-3.5 transition-colors hover:border-violet-200 dark:border-violet-900/30 dark:bg-violet-950/15"
                    >
                        <div className="flex items-center justify-between gap-1">
                            <p className="truncate text-[10px] font-medium uppercase tracking-wider text-zinc-500">
                                {item.label}
                            </p>
                            {item.icon && item.icon}
                        </div>

                        {isPending ? (
                            <Skeleton className="mt-2 h-5 w-20"/>
                        ) : (
                            <p
                                className={`mt-1 text-base font-bold tabular-nums ${
                                    item.isHealth
                                        ? getHealthColorClass(healthFactor)
                                        : item.isDebt && totalBorrowUsd > 0
                                            ? "text-orange-500 dark:text-orange-400"
                                            : "text-zinc-950 dark:text-zinc-50"
                                }`}
                            >
                                {item.value}
                            </p>
                        )}
                    </div>
                ))}
            </div>

            <div className="mt-6">
                <div className="mb-2 flex justify-between text-[11px]">
                    <span className="font-medium text-zinc-500">Borrow Utilization</span>
                    {isPending ? (
                        <Skeleton className="h-3 w-10"/>
                    ) : (
                        <span
                            className={`font-bold ${
                            borrowRatio > 75 ? "text-red-600 dark:text-red-400" : "text-emerald-600 dark:text-emerald-400"
                            }`}
                        >
                            {borrowRatio.toFixed(1)}%
                        </span>
                    )}
                </div>

                <div className="h-1.5 overflow-hidden rounded-full bg-violet-100 dark:bg-violet-950/50">
                    <div
                        className={`h-full rounded-full transition-all duration-500 ${
                            borrowRatio > 75
                                ? "bg-gradient-to-r from-red-500 to-orange-400"
                                : "bg-gradient-to-r from-emerald-500 to-teal-400"
                        } ${isPending ? "w-1/4 animate-pulse" : ""}`}
                        style={
                            !isPending
                                ? {width: `${Math.min(borrowRatio, 100)}%`}
                                : undefined
                        }
                    />
                </div>
            </div>
        </Div>
    );
}
