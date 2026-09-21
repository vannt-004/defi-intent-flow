"use client";

import {createContext, useContext, useEffect, useMemo, useState} from "react";
import {X} from "lucide-react";
import {usePathname, useRouter, useSearchParams} from "next/navigation";

import {cn} from "@/utils/cn";

type AgentFocusContextValue = {
    focusKey: string | null;
    focusLabel: string | null;
    hasFocus: boolean;
    focusTargetFound: boolean;
    focusTargetMissing: boolean;
    isFocused: (keys: string | string[]) => boolean;
    focusClass: (keys: string | string[], className?: string) => string;
    clearFocus: () => void;
};

const AgentFocusContext = createContext<AgentFocusContextValue | null>(null);

const FOCUS_TARGET_CLASS = "agent-focus-target";
const FOCUSED_CLASS = `${FOCUS_TARGET_CLASS} relative z-20 scroll-mt-24 opacity-100 ring-2 ring-violet-400/80 ring-offset-2 ring-offset-violet-50 shadow-[0_0_0_1px_rgba(139,92,246,0.18),0_18px_55px_rgba(139,92,246,0.22)] dark:ring-violet-500/80 dark:ring-offset-[#09070f]`;
const DIMMED_CLASS = "opacity-35 saturate-50 transition-all duration-200";
type FocusTargetState = { focusKey: string | null; status: "idle" | "found" | "missing" };

export function AgentFocusProvider({children}: { children: React.ReactNode }) {
    const router = useRouter();
    const pathname = usePathname();
    const searchParams = useSearchParams();
    const focusKey = searchParams.get("agentFocus");
    const focusLabel = searchParams.get("focusLabel") || focusKey;
    const [targetState, setTargetState] = useState<FocusTargetState>({focusKey: null, status: "idle"});

    useEffect(() => {
        if (!focusKey) {
            return;
        }

        let cancelled = false;
        let found = false;
        let observer: MutationObserver | null = null;
        const timers: number[] = [];

        const findTarget = (shouldScroll: boolean) => {
            const target = document.querySelector<HTMLElement>(`.${FOCUS_TARGET_CLASS}`);
            if (!target || cancelled) return false;

            found = true;
            setTargetState({focusKey, status: "found"});
            observer?.disconnect();
            if (shouldScroll) {
                target.scrollIntoView({behavior: "smooth", block: "center", inline: "nearest"});
            }
            return true;
        };

        timers.push(window.setTimeout(() => findTarget(true), 40));
        timers.push(window.setTimeout(() => findTarget(true), 180));
        timers.push(window.setTimeout(() => findTarget(true), 420));
        timers.push(window.setTimeout(() => findTarget(true), 900));
        timers.push(window.setTimeout(() => findTarget(true), 1600));
        timers.push(window.setTimeout(() => findTarget(true), 2400));

        observer = new MutationObserver(() => {
            findTarget(true);
        });
        observer.observe(document.body, {childList: true, subtree: true});

        timers.push(window.setTimeout(() => {
            if (!found && !cancelled) {
                setTargetState({focusKey, status: "missing"});
            }
        }, 3200));

        timers.push(window.setTimeout(() => {
            observer?.disconnect();
        }, 8000));

        return () => {
            cancelled = true;
            observer?.disconnect();
            timers.forEach((timer) => window.clearTimeout(timer));
        };
    }, [focusKey, pathname]);
    const currentTargetStatus = targetState.focusKey === focusKey ? targetState.status : "idle";

    const value = useMemo<AgentFocusContextValue>(() => {
        const normalize = (keys: string | string[]) => Array.isArray(keys) ? keys : [keys];
        const matches = (keys: string | string[]) => {
            if (!focusKey) return false;
            return normalize(keys).some((key) => key === focusKey);
        };

        return {
            focusKey,
            focusLabel,
            hasFocus: Boolean(focusKey),
            focusTargetFound: currentTargetStatus === "found",
            focusTargetMissing: currentTargetStatus === "missing",
            isFocused: matches,
            focusClass: (keys, className) => {
                if (!focusKey) return className || "";
                if (matches(keys)) return cn(className, FOCUSED_CLASS);
                if (currentTargetStatus !== "found") return className || "";
                return cn(className, DIMMED_CLASS);
            },
            clearFocus: () => {
                const params = new URLSearchParams(searchParams.toString());
                params.delete("agentFocus");
                params.delete("focusLabel");
                params.delete("focusKind");
                const query = params.toString();
                router.replace(query ? `${pathname}?${query}` : pathname, {scroll: false});
            },
        };
    }, [currentTargetStatus, focusKey, focusLabel, pathname, router, searchParams]);

    return (
        <AgentFocusContext.Provider value={value}>
            {children}
        </AgentFocusContext.Provider>
    );
}

export function useAgentFocus() {
    const value = useContext(AgentFocusContext);
    if (!value) {
        throw new Error("useAgentFocus must be used within AgentFocusProvider");
    }
    return value;
}

export function AgentFocusBanner() {
    const {hasFocus, focusLabel, focusKey, focusTargetMissing, clearFocus} = useAgentFocus();

    if (!hasFocus) return null;

    return (
        <div className={cn(
            "shrink-0 border-b px-4 py-2",
            focusTargetMissing
                ? "border-amber-200 bg-amber-50/80 dark:border-amber-900/40 dark:bg-amber-950/20"
                : "border-violet-100 bg-violet-50/80 dark:border-violet-900/40 dark:bg-violet-950/25"
        )}>
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                <div className="min-w-0">
                    <span className={cn(
                        "font-semibold",
                        focusTargetMissing ? "text-amber-700 dark:text-amber-300" : "text-violet-700 dark:text-violet-300"
                    )}>
                        Agent focus
                    </span>
                    <span className="mx-2 text-zinc-400">/</span>
                    <span className="text-zinc-600 dark:text-zinc-300">{focusLabel || focusKey}</span>
                    {focusTargetMissing && (
                        <span className="ml-2 text-amber-700 dark:text-amber-300">
                            Khong thay muc nay tren man hinh hien tai
                        </span>
                    )}
                </div>
                <button
                    type="button"
                    onClick={clearFocus}
                    className={cn(
                        "inline-flex items-center gap-1 rounded-lg border bg-white px-2 py-1 font-semibold text-zinc-600 transition-colors dark:bg-zinc-950 dark:text-zinc-300",
                        focusTargetMissing
                            ? "border-amber-200 hover:border-amber-300 hover:bg-amber-50 hover:text-amber-700 dark:border-amber-900/50 dark:hover:bg-amber-950/30 dark:hover:text-amber-300"
                            : "border-violet-100 hover:border-violet-200 hover:bg-violet-50 hover:text-violet-700 dark:border-violet-900/50 dark:hover:bg-violet-950/30 dark:hover:text-violet-300"
                    )}
                >
                    <X size={12}/>
                    Tat focus
                </button>
            </div>
        </div>
    );
}
