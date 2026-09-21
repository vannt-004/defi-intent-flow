import {ArrowUpRight} from "lucide-react";

import Card from "@/components/ui/Card";
import {cn} from "@/utils/cn";
import {formatMoney} from "@/utils/format";
import {ui} from "@/styles/ui";

import type {TPosition} from "@/types/portfolio";
import {TokenIcon} from "@/components/icon/TokenIcon";
import {TokenPairIcon} from "@/components/icon/TokenPairIcon";

interface Props {
    position: TPosition;
    onClick?: (p: TPosition) => void;
}


export function BasePositionCard({position, onClick}: Props) {
    const {
        type,
        protocol,
        rawSymbol,
        asset,
        balance,
        valueUsd,
        side,
        isCollateral,
        maxLtv,
        liquidationThreshold,
        supplyApr,
        borrowApr,
        borrowStableApr,
    } = position;

    const netApr = supplyApr - (borrowApr || borrowStableApr || 0);
    const isPositive = netApr >= 0;

    return (
        <Card
            onClick={() => onClick?.(position)}
            className={cn(
                "group relative cursor-pointer p-5",
                "transition-all duration-200",
                "border border-violet-100 bg-white hover:border-violet-200 hover:bg-violet-50/40 dark:border-violet-900/40 dark:bg-zinc-950 dark:hover:border-violet-800/70 dark:hover:bg-violet-950/20"
            )}
        >
            <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                    {type === "amm" ? (
                        <TokenPairIcon symbols={asset || rawSymbol.split("/")} size={30}/>
                    ) : (
                        <TokenIcon symbol={rawSymbol}/>
                    )}

                    <div>
                        <p className={cn(ui.text.title, "text-sm")}>
                            {rawSymbol}
                        </p>

                        <p className={cn(ui.text.muted, "text-xs mt-0.5")}>
                            {protocol} • {type} • {side}
                        </p>
                    </div>
                </div>

                {isCollateral && (
                    <span
                        className="rounded-md bg-violet-50 px-2 py-1 text-[10px] font-semibold text-violet-700 dark:bg-violet-950/30 dark:text-violet-300">
                        COLLATERAL
                    </span>
                )}
            </div>

            <div className="flex items-end justify-between mb-4">
                <div>
                    <p className={cn(ui.text.muted, "text-xs mb-1")}>
                        Position Value
                    </p>

                    <p className={cn(ui.text.title, "text-xl tabular-nums")}>
                        {formatMoney(valueUsd)}
                    </p>

                    <p className="text-xs text-zinc-500 mt-1">
                        Balance: {balance}
                    </p>
                </div>

                <ArrowUpRight
                    size={16}
                    className={cn(
                        "transition-transform duration-200 group-hover:translate-x-1 group-hover:-translate-y-1",
                        isPositive ? "text-emerald-500" : "text-red-400"
                    )}
                />
            </div>

            <div className="grid grid-cols-3 gap-3 text-xs">
                <div>
                    <p className="text-zinc-500">Supply APR</p>
                    <p className="font-medium text-emerald-500">
                        {supplyApr.toFixed(2)}%
                    </p>
                </div>

                <div>
                    <p className="text-zinc-500">Borrow APR</p>
                    <p className="font-medium text-red-400">
                        {borrowApr.toFixed(2)}%
                    </p>
                </div>

                <div>
                    <p className="text-zinc-500">Net APR</p>
                    <p
                        className={cn(
                            "font-semibold",
                            isPositive ? "text-emerald-500" : "text-red-400"
                        )}
                    >
                        {isPositive ? "+" : ""}
                        {netApr.toFixed(2)}%
                    </p>
                </div>
            </div>

            <div className="mt-4 flex justify-between text-[10px] text-zinc-500">
                <span>LTV: {(maxLtv).toFixed(0)}%</span>
                <span>Liquidation: {(liquidationThreshold).toFixed(0)}%</span>
            </div>

            <div
                className="absolute bottom-0 left-4 right-4 h-px bg-gradient-to-r from-transparent via-violet-300/50 to-transparent dark:via-violet-800/40"/>
        </Card>
    );
}
