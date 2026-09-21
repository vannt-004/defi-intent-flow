"use client";

import Link from "next/link";
import {usePathname} from "next/navigation";
import {cn} from "@/utils/cn";
import {ui} from "@/styles/ui";
import {useWalletTrackingStatusQuery} from "@/hooks/usePortfolioQuery";
import {useWallet} from "@/hooks/useWallet";

const NAV_ITEMS = [
    {
        href: "/dashboard",
        label: "Dashboard",
        icon: (
            <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                <rect x="3" y="3" width="7" height="7" rx="1.5"/>
                <rect x="14" y="3" width="7" height="7" rx="1.5"/>
                <rect x="3" y="14" width="7" height="7" rx="1.5"/>
                <rect x="14" y="14" width="7" height="7" rx="1.5"/>
            </svg>
        ),
    },
    {
        href: "/markets",
        label: "Markets",
        icon: (
            <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                <polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/>
                <polyline points="16 7 22 7 22 13"/>
            </svg>
        ),
    },
    {
        href: "/risk-engine",
        label: "Risk Engine",
        fullOnly: true,
        icon: (
            <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                <path d="M12 3 4 6v5c0 5 3.4 8.6 8 10 4.6-1.4 8-5 8-10V6l-8-3z"/>
                <path d="M12 8v4"/>
                <path d="M12 16h.01"/>
            </svg>
        ),
    },
    {
        href: "/simulator",
        label: "Simulator",
        fullOnly: true,
        icon: (
            <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                <rect x="2" y="3" width="20" height="14" rx="2"/>
                <line x1="8" y1="21" x2="16" y2="21"/>
                <line x1="12" y1="17" x2="12" y2="21"/>
            </svg>
        ),
    },
];

export default function Sidebar({collapsed = false}: { collapsed?: boolean }) {
    const pathname = usePathname();
    const {address} = useWallet();
    const {data: walletStatus} = useWalletTrackingStatusQuery(address);
    const canUseFullFeatures = !!walletStatus?.canUseFullFeatures;

    return (
        <aside className={cn(
            "flex h-full shrink-0 flex-col border-r border-violet-100 bg-white/95 transition-[width] duration-200 dark:border-violet-900/40 dark:bg-zinc-950/95",
            collapsed ? "w-16" : "w-50"
        )}>
            <nav className={cn("flex flex-1 flex-col gap-1", collapsed ? "p-2" : "p-3")}>
                {NAV_ITEMS.map((item) => {
                    const isActive = pathname === item.href;
                    const isLocked = !!item.fullOnly && !canUseFullFeatures;
                    if (isLocked) {
                        return (
                            <button
                                key={item.href}
                                type="button"
                                title={collapsed ? item.label : undefined}
                                aria-label={collapsed ? item.label : undefined}
                                disabled
                                className={cn(
                                    ui.nav.item,
                                    "cursor-not-allowed opacity-40",
                                    collapsed && "h-11 justify-center px-0"
                                )}
                            >
                                <span className="shrink-0">{item.icon}</span>
                                {!collapsed && <span className="truncate">{item.label}</span>}
                            </button>
                        );
                    }
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            title={collapsed ? item.label : undefined}
                            aria-label={collapsed ? item.label : undefined}
                            className={cn(
                                isActive ? ui.nav.active : ui.nav.item,
                                collapsed && "h-11 justify-center px-0"
                            )}
                        >
                            <span className="shrink-0">{item.icon}</span>
                            {!collapsed && <span className="truncate">{item.label}</span>}
                        </Link>
                    );
                })}
            </nav>
        </aside>
    );
}
