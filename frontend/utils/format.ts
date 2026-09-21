export const formatMoney = (n: number) =>
    n >= 1_000_000
        ? `$${(n / 1_000_000).toFixed(2)}M`
        : `$${n.toLocaleString("en-US", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        })}`;

export const formatPercent = (v: number) => {
    const sign = v >= 0 ? "+" : "−";
    return `${sign}${Math.abs(v).toFixed(2)}%`;
}

export const formatShortAddr = (addr: string) => `${addr.slice(0, 6)}…${addr.slice(-4)}`;