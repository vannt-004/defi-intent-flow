"use client";

import {useMemo, useState} from "react";
import {Check, ChevronDown, Search} from "lucide-react";

import {cn} from "@/utils/cn";
import {ui} from "@/styles/ui";

export type SelectOption = {
    label: string;
    value: string;
    description?: string;
};

type Props = {
    label?: string;
    value: string;
    options: SelectOption[];
    onChange: (value: string) => void;
    placeholder?: string;
    className?: string;
};

export default function Select({label, value, options, onChange, placeholder = "Select option", className}: Props) {
    const [open, setOpen] = useState(false);
    const [query, setQuery] = useState("");
    const selected = useMemo(() => options.find((option) => option.value === value), [options, value]);
    const filteredOptions = useMemo(() => {
        const normalized = query.trim().toLowerCase();
        if (!normalized) return options;
        return options.filter((option) => {
            return `${option.label} ${option.value} ${option.description || ""}`.toLowerCase().includes(normalized);
        });
    }, [options, query]);

    return (
        <div
            className={cn("relative", className)}
            onBlur={(event) => {
                if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
                    setOpen(false);
                }
            }}
        >
            {label && (
                <span className="pointer-events-none absolute left-3 top-1.5 z-10 text-[9px] font-semibold uppercase tracking-wider text-violet-500 dark:text-violet-300">
                    {label}
                </span>
            )}
            <button
                type="button"
                onClick={() => {
                    setOpen((current) => !current);
                    setQuery("");
                }}
                className={cn(
                    "group flex h-12 w-full items-center justify-between gap-3 rounded-lg border border-violet-100 bg-violet-50/30 px-3 text-left text-xs font-semibold text-zinc-800 outline-none transition-all hover:border-violet-300 hover:bg-violet-50 focus:border-violet-400 focus:ring-2 focus:ring-violet-100 dark:border-violet-900/50 dark:bg-zinc-950 dark:text-zinc-100 dark:hover:border-violet-700 dark:hover:bg-violet-950/20 dark:focus:ring-violet-950/40",
                    label ? "pb-1.5 pt-5" : "py-2"
                )}
            >
                <span className={cn("min-w-0 truncate", selected ? ui.text.heading : "text-zinc-400")}>
                    {selected?.label || placeholder}
                </span>
                <ChevronDown
                    size={15}
                    className={cn("shrink-0 text-violet-500 transition-transform duration-200", open && "rotate-180")}
                />
            </button>

            {open && (
                <div
                    className="absolute left-0 right-0 top-[calc(100%+6px)] z-30 rounded-lg border border-violet-100 bg-white p-1.5 shadow-xl shadow-zinc-200/70 dark:border-violet-900/60 dark:bg-zinc-950 dark:shadow-black/30"
                    style={{animation: "dropdownIn 140ms ease-out"}}
                >
                    <div className="sticky top-0 z-10 mb-1 flex items-center gap-2 rounded-md border border-violet-100 bg-violet-50/70 px-2 py-1.5 dark:border-violet-900/50 dark:bg-violet-950/30">
                        <Search size={13} className="shrink-0 text-violet-500"/>
                        <input
                            value={query}
                            onChange={(event) => setQuery(event.target.value)}
                            onMouseDown={(event) => event.stopPropagation()}
                            placeholder="Search..."
                            className="min-w-0 flex-1 bg-transparent text-xs font-medium text-zinc-800 outline-none placeholder:text-zinc-400 dark:text-zinc-100"
                            autoFocus
                        />
                    </div>
                    <div className="max-h-64 overflow-y-auto">
                    {filteredOptions.map((option) => {
                        const active = option.value === value;
                        return (
                            <button
                                type="button"
                                key={option.value}
                                onMouseDown={(event) => event.preventDefault()}
                                onClick={() => {
                                    onChange(option.value);
                                    setOpen(false);
                                    setQuery("");
                                }}
                                className={cn(
                                    "flex w-full items-center justify-between gap-3 rounded-md px-2.5 py-2 text-left text-xs transition-colors",
                                    active
                                        ? "border border-violet-200 bg-violet-50 text-violet-800 shadow-sm dark:border-violet-800/60 dark:bg-violet-950/40 dark:text-violet-200"
                                        : "text-zinc-600 hover:bg-violet-50 hover:text-violet-700 dark:text-zinc-300 dark:hover:bg-violet-950/30 dark:hover:text-violet-200"
                                )}
                            >
                                <span className="min-w-0">
                                    <span className="block truncate font-semibold">{option.label}</span>
                                    {option.description && (
                                        <span className={cn("mt-0.5 block truncate text-[10px]", active ? "text-violet-100" : "text-zinc-400")}>
                                            {option.description}
                                        </span>
                                    )}
                                </span>
                                {active && <Check size={14} className="shrink-0"/>}
                            </button>
                        );
                    })}
                    {!filteredOptions.length && (
                        <div className="px-3 py-4 text-center text-xs text-zinc-500">No matching option</div>
                    )}
                    </div>
                </div>
            )}
        </div>
    );
}
