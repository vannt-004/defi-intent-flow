"use client";

import {cn} from "@/utils/cn";
import {ui} from "@/styles/ui";
import {useWallet} from "@/hooks/useWallet";
import {
    TAllocation,
    TPnLPeriod,
} from "@/types/portfolio";
import {usePortfolioAnalyticsQuery, usePortfolioQuery, useWalletTrackingStatusQuery} from "@/hooks/usePortfolioQuery";
import {useState} from "react";
import SparklineChart from "@/components/dashboard/SparklineChart";
import PositionsPnLTable from "@/components/dashboard/PositionsPnLTable";
import TransactionFeed from "@/components/dashboard/TransactionFeed";
import AllocationBox from "@/components/dashboard/AllocationBox";
import PnLBreakdown from "@/components/dashboard/PnLBreakdown";
import Skeleton from "@/components/common/Skeleton";
import Div from "@/components/ui/Div";
import PortfolioOverview from "@/components/dashboard/PortfolioOverview";
import UpdatePlusPanel from "@/components/dashboard/UpdatePlusPanel";
import {useAgentFocus} from "@/components/assistant/AgentFocusContext";

function CardSkeleton({className}: { className?: string }) {
    return (
        <Div className={cn("space-y-4", className)}>
            <div className="flex items-start justify-between gap-4">
                <div className="space-y-2">
                    <Skeleton className="h-3 w-24"/>
                    <Skeleton className="h-8 w-44"/>
                </div>
                <Skeleton className="h-7 w-24"/>
            </div>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <Skeleton className="h-16"/>
                <Skeleton className="h-16"/>
                <Skeleton className="h-16"/>
                <Skeleton className="h-16"/>
            </div>
        </Div>
    );
}

function ChartSkeleton() {
    return (
        <Div className="lg:col-span-2">
            <div className="mb-5 flex items-start justify-between">
                <div className="space-y-2">
                    <Skeleton className="h-4 w-36"/>
                    <Skeleton className="h-3 w-52"/>
                </div>
                <div className="flex gap-1">
                    <Skeleton className="h-7 w-10"/>
                    <Skeleton className="h-7 w-10"/>
                    <Skeleton className="h-7 w-10"/>
                </div>
            </div>
            <Skeleton className="h-[210px] w-full"/>
        </Div>
    );
}

function TableSkeleton({rows = 5, className}: { rows?: number; className?: string }) {
    return (
        <Div className={className}>
            <div className="mb-4 flex items-start justify-between gap-4">
                <div className="space-y-2">
                    <Skeleton className="h-4 w-40"/>
                    <Skeleton className="h-3 w-72 max-w-full"/>
                </div>
                <Skeleton className="h-8 w-40"/>
            </div>
            <div className="space-y-3">
                {Array.from({length: rows}).map((_, index) => (
                    <div key={index} className="grid grid-cols-[1.3fr_0.7fr_0.7fr_0.7fr] gap-3">
                        <Skeleton className="h-10"/>
                        <Skeleton className="h-10"/>
                        <Skeleton className="h-10"/>
                        <Skeleton className="h-10"/>
                    </div>
                ))}
            </div>
        </Div>
    );
}

export default function DashboardPage() {
    const {focusClass} = useAgentFocus();
    const {address, isConnected} = useWallet();
    const {data: walletStatus, isPending: isStatusPending} = useWalletTrackingStatusQuery(address);
    const canUseFullFeatures = !!walletStatus?.canUseFullFeatures;
    const canViewPortfolio = !!address && !isStatusPending;
    const isPreviewMode = canViewPortfolio && !canUseFullFeatures;
    const {data, isPending: isPortfolioPending} = usePortfolioQuery(address, canViewPortfolio, isPreviewMode);
    const {data: analytics, isPending: isAnalyticsPending} = usePortfolioAnalyticsQuery(address, canViewPortfolio, isPreviewMode);
    const [chartPeriod, setChartPeriod] = useState<TPnLPeriod>("3M");

    const isLoading = Boolean(canViewPortfolio && (isPortfolioPending || isAnalyticsPending));

    const netWorth = analytics?.netWorth;
    const pnlSummary = analytics?.pnlSummary;
    const positionsPnL = analytics?.positionsPnL ?? [];
    const chartData = analytics?.chartHistory ?? [];
    const transactions = analytics?.transactions ?? [];
    const pnlFlows = analytics?.pnlFlows ?? [];
    const allocations: TAllocation[] = data?.allocations ?? [];

    return (
        <div className="mb-5 flex min-w-0 flex-1 flex-col gap-4 p-4 transition-all duration-200 md:p-5">
            {!isConnected || !address ? (
                <Div className={focusClass(["dashboard:status", "dashboard:overview"], "flex min-h-[260px] flex-col items-center justify-center text-center transition-all duration-200")}>
                    <p className={cn("text-lg font-semibold", ui.text.heading)}>Connect wallet</p>
                    <p className={cn("mt-2 max-w-md text-sm", ui.text.muted)}>
                        Connect a wallet to preview the dashboard. Your address is not saved until you choose Update Plus.
                    </p>
                </Div>
            ) : isStatusPending ? (
                <CardSkeleton className={focusClass("dashboard:status", "transition-all duration-200")}/>
            ) : (
                <>
                    {!canUseFullFeatures && (
                        <div className={focusClass("dashboard:status", "transition-all duration-200")}>
                            <UpdatePlusPanel wallet={address} status={walletStatus}/>
                        </div>
                    )}

                    <div className={focusClass("dashboard:overview", "transition-all duration-200")}>
                        <PortfolioOverview
                            summary={data?.summary}
                            netWorth={netWorth}
                            pnl={pnlSummary}
                            isPending={isLoading}
                        />
                    </div>

                    {isLoading ? (
                        <CardSkeleton/>
                    ) : (
                        netWorth && canUseFullFeatures && <PnLBreakdown netWorth={netWorth} positions={positionsPnL}/>
                    )}

                    <div className="grid grid-cols-1 gap-4 lg:grid-cols-10">
                        {isLoading ? (
                            <>
                                <div className={focusClass("dashboard:chart", "transition-all duration-200 lg:col-span-7")}>
                                    <ChartSkeleton />
                                </div>
                                <div className={focusClass("dashboard:allocation", "transition-all duration-200 lg:col-span-3")}>
                                    <CardSkeleton className="h-[300px]" />
                                </div>
                            </>
                        ) : (
                            <>
                                {chartData.length > 0 ? (
                                    <div className={focusClass("dashboard:chart", "transition-all duration-200 lg:col-span-7")}>
                                        <SparklineChart data={chartData} period={chartPeriod} onPeriodChange={setChartPeriod} />
                                    </div>
                                ) : (
                                    /* Đổi từ col-span-2 thành col-span-10 để kéo dài hết hàng khi không có data */
                                    <Div className={focusClass("dashboard:chart", "flex items-center justify-center p-5 text-sm text-zinc-500 transition-all duration-200 lg:col-span-10")}>
                                        No chart history available
                                    </Div>
                                )}

                                {allocations.length > 0 ? (
                                    <div className={focusClass("dashboard:allocation", "transition-all duration-200 lg:col-span-3")}>
                                        <AllocationBox allocations={allocations} />
                                    </div>
                                ) : (
                                    <div className={focusClass("dashboard:allocation", cn(ui.card.base,
                                        "flex items-center justify-center p-5 text-sm text-zinc-500 lg:col-span-3"
                                    ))}>
                                        No allocation data available
                                    </div>
                                )}
                            </>
                        )}
                    </div>

                    {isLoading ? (
                        <TableSkeleton className={focusClass("dashboard:positions", "transition-all duration-200")}/>
                    ) : (
                        positionsPnL.length > 0 && (
                            <div className={focusClass(["dashboard:positions", "dashboard:pnl:positions"], "transition-all duration-200")}>
                                <PositionsPnLTable
                                    positions={positionsPnL}
                                    assets={data?.assets ?? []}
                                    canUseFullFeatures={canUseFullFeatures}
                                />
                            </div>
                        )
                    )}

                    {isLoading ? (
                        <div className={focusClass("dashboard:cashflow", "grid grid-cols-1 gap-4 transition-all duration-200 lg:grid-cols-2")}>
                            <TableSkeleton rows={4}/>
                            <CardSkeleton/>
                        </div>
                    ) : (
                        canUseFullFeatures && (
                            <div className={focusClass("dashboard:cashflow", "grid grid-cols-1 gap-4 transition-all duration-200")}>
                                <TransactionFeed transactions={transactions} pnlFlows={pnlFlows}/>
                            </div>
                        )
                    )}
                </>
            )}

        </div>
    );
}
