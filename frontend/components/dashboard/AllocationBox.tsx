import {TAllocation} from "@/types/portfolio";
import {cn} from "@/utils/cn";
import {ui} from "@/styles/ui";
import Div from "@/components/ui/Div";
import {Cell, Pie, PieChart, ResponsiveContainer, Tooltip} from "recharts";

const COLORS = ["#7c3aed", "#a855f7", "#c084fc", "#8b5cf6", "#6d28d9"];

export default function AllocationBox({allocations}: { allocations: TAllocation[] }) {
    const total = allocations.reduce((sum, item) => sum + item.valueUsd, 0);
    const chartData = allocations.map((item) => ({
        name: item.purpose,
        value: item.valueUsd,
        percentage: item.percentage,
    }));

    return (
        <Div className="h-[100%]">
            <div>
                <p className={cn("text-sm font-semibold", ui.text.heading)}>Asset Allocation</p>
                <p className={cn("mt-1 text-xs", ui.text.muted)}>Portfolio value by exposure type</p>
            </div>
            <div className="mt-8 grid min-w-0 flex-1 items-center gap-4 2xl:grid-cols-[180px_minmax(0,1fr)]">
                {!allocations.length ? (
                    <p className="text-xs text-zinc-500 2xl:col-span-2">No data available</p>
                ) : (
                    <>
                        <div className="relative h-[220px] min-w-0">
                            <ResponsiveContainer width="100%" height="100%">
                                <PieChart>
                                    <Tooltip
                                        contentStyle={{
                                            backgroundColor: "rgba(24,24,27,0.96)",
                                            border: "1px solid rgba(124,58,237,0.25)",
                                            borderRadius: "8px",
                                            color: "#f4f4f5",
                                        }}
                                        formatter={(value: unknown, _name: unknown, item: { payload?: { name?: string } }) => [
                                            `$${Number(value || 0).toLocaleString(undefined, {maximumFractionDigits: 2})}`,
                                            item.payload?.name ?? "Allocation",
                                        ]}
                                    />
                                    <Pie
                                        data={chartData}
                                        dataKey="value"
                                        nameKey="name"
                                        innerRadius={54}
                                        outerRadius={78}
                                        paddingAngle={2}
                                        stroke="transparent"
                                    >
                                        {chartData.map((entry, index) => (
                                            <Cell key={entry.name} fill={COLORS[index % COLORS.length]}/>
                                        ))}
                                    </Pie>
                                </PieChart>
                            </ResponsiveContainer>
                            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                                <p className="text-[10px] uppercase tracking-wider text-zinc-500">Total</p>
                                <p className={cn("text-sm font-semibold tabular-nums", ui.text.heading)}>
                                    ${total.toLocaleString(undefined, {maximumFractionDigits: 0})}
                                </p>
                            </div>
                        </div>

                        <div className="min-w-0 space-y-2">
                            {allocations.map((alloc, index) => (
                                <div key={alloc.purpose} className="flex min-w-0 flex-col items-start justify-between gap-2 rounded-lg bg-violet-50/45 px-3 py-2 text-xs dark:bg-violet-950/15">
                                    <div className="flex max-w-full min-w-0 items-center gap-2">
                                        <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{backgroundColor: COLORS[index % COLORS.length]}}/>
                                        <span className="truncate font-medium text-zinc-500 dark:text-zinc-400">{alloc.purpose}</span>
                                    </div>
                                    <span className={cn("max-w-full font-semibold tabular-nums", ui.text.heading)}>
                                        ${alloc.valueUsd.toLocaleString(undefined, {maximumFractionDigits: 0})}
                                        <span className="ml-1 font-normal text-zinc-400">({alloc.percentage}%)</span>
                                    </span>
                                </div>
                            ))}
                        </div>
                    </>
                )}
            </div>
        </Div>
    );
}
