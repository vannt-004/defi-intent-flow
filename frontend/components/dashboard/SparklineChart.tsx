"use client";

import {cn} from "@/utils/cn";
import {ui} from "@/styles/ui";
import {TChartPoint, TPnLPeriod} from "@/types/portfolio";
import {
    ResponsiveContainer,
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip
} from "recharts";
import Div from "@/components/ui/Div";

const formatCurrency = (value: number) => {
    if (value >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
    if (value >= 1e3) return `$${(value / 1e3).toFixed(1)}k`;
    return `$${value.toFixed(2)}`;
};

const chartPointDayKey = (point: TChartPoint) => {
    if (typeof point.timestamp === "number" && Number.isFinite(point.timestamp)) {
        return new Date(toTimestampMs(point.timestamp)).toISOString().slice(0, 10);
    }

    return point.label;
};

const toTimestampMs = (timestamp: number) =>
    timestamp > 1_000_000_000_000 ? timestamp : timestamp * 1000;

const toNumber = (value: unknown) => {
    const numericValue = Number(value || 0);
    return Number.isFinite(numericValue) ? numericValue : 0;
};

const dedupeChartDataByDay = (points: TChartPoint[]) => {
    const pointsByDay = new Map<string, TChartPoint>();

    points.forEach((point) => {
        const dayKey = chartPointDayKey(point);
        if (dayKey) {
            pointsByDay.set(dayKey, point);
        }
    });

    return Array.from(pointsByDay.values()).sort((a, b) => {
        if (typeof a.timestamp === "number" && typeof b.timestamp === "number") {
            return toTimestampMs(a.timestamp) - toTimestampMs(b.timestamp);
        }

        return 0;
    });
};

const periodDays: Partial<Record<TPnLPeriod, number>> = {
    "1D": 1,
    "7D": 7,
    "1M": 30,
    "3M": 90,
};

const fallbackPointCount: Record<TPnLPeriod, number> = {
    "1D": 2,
    "7D": 7,
    "1M": 30,
    "3M": 90,
    "ALL": Number.POSITIVE_INFINITY,
};

const filterChartDataByPeriod = (points: TChartPoint[], period: TPnLPeriod) => {
    if (period === "ALL" || points.length === 0) return points;

    const latestTimestamp = [...points]
        .reverse()
        .find((point) => typeof point.timestamp === "number" && Number.isFinite(point.timestamp))?.timestamp;

    if (typeof latestTimestamp === "number") {
        const cutoff = toTimestampMs(latestTimestamp) - (periodDays[period] ?? 0) * 24 * 60 * 60 * 1000;
        const filtered = points.filter((point) => (
            typeof point.timestamp === "number"
            && Number.isFinite(point.timestamp)
            && toTimestampMs(point.timestamp) >= cutoff
        ));

        return filtered.length > 0 ? filtered : points.slice(-1);
    }

    return points.slice(-fallbackPointCount[period]);
};

export default function SparklineChart({
                                           data,
                                           period,
                                           onPeriodChange
                                       }: {
    data: TChartPoint[];
    period: TPnLPeriod;
    onPeriodChange: (p: TPnLPeriod) => void;
}) {
    const periods: TPnLPeriod[] = ["1D", "7D", "1M", "3M", "ALL"];

    const dedupedData = data && data.length > 0 ? dedupeChartDataByDay(data) : [];
    const chartData = filterChartDataByPeriod(dedupedData, period);
    const safeData = chartData.length > 0 ? chartData : [
        {label: "N/A", tokenHold: 0, positions: 0, netWorth: 0}
    ];

    return (
        <Div>
            <div className="mb-4 flex items-start justify-between">
                <div>
                    <p className={cn("text-sm font-semibold", ui.text.heading)}>Net Worth History</p>
                    <p className={cn("mt-1 text-xs", ui.text.muted)}>Token Hold vs Positions vs Net Worth</p>
                </div>
                <div className="flex gap-1">
                    {periods.map((p) => (
                        <button
                            key={p}
                            type="button"
                            aria-pressed={p === period}
                            onClick={() => onPeriodChange(p)}
                            className={cn(
                                "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                                p === period
                                    ? "border border-violet-200 bg-violet-50 text-violet-800 hover:border-violet-300 hover:bg-violet-100 dark:border-violet-800/60 dark:bg-violet-950/35 dark:text-violet-200 dark:hover:bg-violet-900/25"
                                    : "text-zinc-500 hover:bg-violet-50 hover:text-violet-700 dark:hover:bg-violet-950/30 dark:hover:text-violet-300"
                            )}
                        >
                            {p}
                        </button>
                    ))}
                </div>
            </div>

            <div className="h-[220px] w-full text-[11px]">
                <ResponsiveContainer width="100%" height="100%">
                    <AreaChart
                        data={safeData}
                        margin={{top: 8, right: 8, left: 0, bottom: 0}}
                    >
                        <defs>
                            <linearGradient id="nwGrad" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#7c3aed" stopOpacity={0.18}/>
                                <stop offset="95%" stopColor="#7c3aed" stopOpacity={0}/>
                            </linearGradient>
                        </defs>

                        <CartesianGrid
                            strokeDasharray="3 3"
                            vertical={false}
                            stroke="rgba(128,128,128,0.15)"
                        />

                        <XAxis
                            dataKey="label"
                            tickLine={false}
                            axisLine={false}
                            stroke="#71717a"
                            dy={10}
                        />

                        <YAxis
                            tickFormatter={formatCurrency}
                            tickLine={false}
                            axisLine={false}
                            stroke="#71717a"
                            domain={['auto', 'auto']}
                            width={54}
                        />

                        <Tooltip
                            contentStyle={{
                                backgroundColor: "rgba(24, 24, 27, 0.95)",
                                border: "1px solid rgba(63, 63, 70, 0.4)",
                                borderRadius: "8px",
                                padding: "10px",
                                color: "#f4f4f5"
                            }}
                            itemStyle={{padding: "2px 0"}}
                            formatter={(value: unknown) => [formatCurrency(toNumber(value)), ""]}
                            labelStyle={{fontWeight: "bold", marginBottom: "4px", color: "#a1a1aa"}}
                        />

                        <Area
                            type="monotone"
                            dataKey="tokenHold"
                            name="Token Hold"
                            stroke="#8b5cf6"
                            strokeWidth={2}
                            fill="none"
                            activeDot={{r: 4}}
                        />

                        <Area
                            type="monotone"
                            dataKey="positions"
                            name="Positions (Lend+Farm)"
                            stroke="#c084fc"
                            strokeWidth={2}
                            fill="none"
                            activeDot={{r: 4}}
                        />

                        <Area
                            type="monotone"
                            dataKey="netWorth"
                            name="Net Worth"
                            stroke="#6d28d9"
                            strokeWidth={2.5}
                            fill="url(#nwGrad)"
                            activeDot={{r: 5, strokeWidth: 2}}
                        />
                    </AreaChart>
                </ResponsiveContainer>
            </div>

            <div
                className="mt-4 flex flex-wrap gap-4 border-t border-violet-100 pt-3 text-[11px] text-zinc-400 dark:border-violet-900/40">
                {[
                    {color: "#8b5cf6", label: "Token Hold"},
                    {color: "#c084fc", label: "Positions (Lend+Farm)"},
                    {color: "#6d28d9", label: "Net Worth"},
                ].map((l) => (
                    <span key={l.label} className="flex items-center gap-1.5">
                        <span
                            className="h-1.5 w-4 rounded-sm"
                            style={{backgroundColor: l.color}}
                        />
                        {l.label}
                    </span>
                ))}
            </div>
        </Div>
    );
}
