import {cn} from "@/utils/cn";
import {ui} from "@/styles/ui";
import {TAlert} from "@/types/portfolio";
import Div from "@/components/ui/Div";

const ALERT_META = {
    danger: {bar: "bg-red-500", bg: "bg-red-50 dark:bg-red-950/40", title: "text-red-600 dark:text-red-400"},
    warning: {bar: "bg-amber-400", bg: "bg-amber-50 dark:bg-amber-950/40", title: "text-amber-600 dark:text-amber-400"},
    info: {bar: "bg-blue-400", bg: "bg-blue-50 dark:bg-blue-950/40", title: "text-blue-600 dark:text-blue-400"},
    success: {
        bar: "bg-emerald-500",
        bg: "bg-emerald-50 dark:bg-emerald-950/40",
        title: "text-emerald-600 dark:text-emerald-400"
    },
};

export default function AlertsPanel({alerts}: { alerts: TAlert[] }) {
    return (
        <Div>
            <p className={cn("mb-4 text-sm font-semibold", ui.text.heading)}>Alerts & Opportunities</p>
            <div className="flex flex-col gap-2.5">
                {alerts.map((a) => {
                    const m = ALERT_META[a.level];
                    return (
                        <div key={a.id} className={cn("flex gap-3 rounded-lg p-3", m.bg)}>
                            <div className={cn("mt-1 h-full w-0.5 rounded-full", m.bar)}/>
                            <div>
                                <p className={cn("text-xs font-semibold", m.title)}>{a.title}</p>
                                <p className="mt-0.5 text-[11px] text-zinc-500 dark:text-zinc-400">{a.message}</p>
                            </div>
                        </div>
                    );
                })}
            </div>
        </Div>
    );
}
