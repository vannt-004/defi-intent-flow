import {cn} from "@/utils/cn";
import {ui} from "@/styles/ui";
import {formatMoney} from "@/utils/format";
import {TNetWorth, TPnLSummary} from "@/types/portfolio";
import Div from "@/components/ui/Div";
import PnLText from "@/components/dashboard/PnLText";

export default function NetWorthBanner({nw, pnl}: { nw: TNetWorth; pnl: TPnLSummary }) {
    return (
        <Div>
            <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                    <p className="text-xs font-semibold uppercase tracking-wider text-violet-500 dark:text-violet-400">Net Worth</p>
                    <p className="mt-1 text-3xl font-semibold tabular-nums text-zinc-950 dark:text-zinc-50">
                        {formatMoney(nw.totalUsd)}
                    </p>
                    <p className={cn("mt-1 text-xs", ui.text.muted)}>
                        Token hold + lending + interest + farming - debt
                    </p>
                </div>

                <div className="flex flex-wrap gap-3">
                    {[
                        {label: "Today", usd: pnl.todayUsd, pct: pnl.todayPct},
                        {label: "7 Days", usd: pnl.sevenDayUsd, pct: pnl.sevenDayPct},
                        {label: "All Time", usd: pnl.allTimeUsd, pct: pnl.allTimePct},
                    ].map((item) => (
                        <div key={item.label}
                             className="min-w-[108px] rounded-lg border border-violet-100 bg-violet-50/50 px-4 py-3 dark:border-violet-900/40 dark:bg-violet-950/20">
                            <p className="text-[11px] text-zinc-400">{item.label}</p>
                            <PnLText value={item.usd} pct={item.pct} size="md"/>
                        </div>
                    ))}
                </div>
            </div>

            <div
                className="mt-4 grid grid-cols-2 gap-2 border-t border-violet-100 pt-4 dark:border-violet-900/40 sm:grid-cols-4">
                {[
                    {label: "Token Hold", value: nw.tokenHoldUsd, sub: "Liquid assets"},
                    {
                        label: "Lending & Interest",
                        value: nw.lendingUsd + nw.interestEarnedUsd,
                        sub: `+$${nw.interestEarnedUsd.toLocaleString()} accrued interest`
                    },
                    {label: "Farming", value: nw.farmingUsd, sub: "LP + yield"},
                    {
                        label: "Net Debt",
                        value: -(nw.debtUsd + nw.debtInterestUsd),
                        sub: "Debt + borrow fee",
                        isNeg: true
                    },
                ].map((b) => (
                    <div key={b.label} className="rounded-lg bg-violet-50/50 px-3 py-2.5 dark:bg-violet-950/20">
                        <p className="text-[11px] text-zinc-400">{b.label}</p>
                        <p className={cn("text-sm font-semibold",
                            b.isNeg ? "text-red-500" : "text-zinc-800 dark:text-zinc-100")}>
                            {b.isNeg ? formatMoney(b.value) : `$${b.value.toLocaleString()}`}
                        </p>
                        <p className="text-[10px] text-zinc-400">{b.sub}</p>
                    </div>
                ))}
            </div>
        </Div>
    );
}
