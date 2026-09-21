"use client";

import { usePathname } from "next/navigation";
import { cn } from "@/utils/cn";
import { ui } from "@/styles/ui";
import WalletButton from "@/components/common/WalletButton";

const PAGE_TITLES: Record<string, { title: string; subtitle: string }> = {
    "/": {
        title: "Portfolio",
        subtitle: "Overview of your assets and performance"
    },
    "/dashboard": {
        title: "Portfolio",
        subtitle: "Overview of your assets and performance"
    },
    "/markets": {
        title: "Markets",
        subtitle: "Real-time token prices and analytics"
    },
    "/risk-engine": {
        title: "Risk Engine",
        subtitle: "Position risk, liquidation buffer, and LP range analysis"
    },
    "/simulator": {
        title: "Simulator",
        subtitle: "Backtest and simulate investment strategies"
    },
};

export default function TopBar() {
    const pathname = usePathname();
    const page = PAGE_TITLES[pathname] ?? PAGE_TITLES["/"];

    return (
        <header className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-violet-100 bg-white/90 px-5 backdrop-blur dark:border-violet-900/40 dark:bg-zinc-950/90">
            <div className="min-w-0">
                <h1 className={cn("truncate text-sm font-semibold leading-none", ui.text.heading)}>
                    {page.title}
                </h1>
                <p className={cn("mt-1 truncate text-xs leading-none", ui.text.muted)}>{page.subtitle}</p>
            </div>

            <WalletButton />
        </header>
    );
}
