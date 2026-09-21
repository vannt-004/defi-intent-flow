import {formatMoney, formatPercent} from "@/utils/format";
import {cn} from "@/utils/cn";

export default function PnLText({ value, pct, size = "sm" }: { value: number; pct?: number | null; size?: "sm" | "md" | "lg" }) {
    const positive = value >= 0;
    const sizeClass = size === "lg" ? "text-xl font-semibold" : size === "md" ? "text-base font-semibold" : "text-sm font-medium";
    return (
        <span className={cn(sizeClass, positive ? "text-emerald-500 dark:text-emerald-400" : "text-red-500 dark:text-red-400")}>
      {formatMoney(value)}
            {pct != null && <span className="ml-1 text-xs opacity-75">{formatPercent(pct)}</span>}
    </span>
    );
}