export const ui = {
    badge: {
        live: "border border-violet-200 bg-violet-50 text-violet-700 dark:border-violet-800/70 dark:bg-violet-950/40 dark:text-violet-300",
        up: "bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-400",
        down: "bg-red-50 text-red-600 dark:bg-red-950/40 dark:text-red-400",
        neutral: "bg-violet-50 text-violet-600 dark:bg-violet-950/40 dark:text-violet-300",
    },

    card: {
        base: "rounded-lg border border-violet-100/80 bg-white/95 shadow-sm shadow-violet-100/60 dark:border-violet-900/40 dark:bg-zinc-950/90 dark:shadow-none",

        muted: "rounded-lg border border-violet-100/70 bg-violet-50/50 dark:border-violet-900/30 dark:bg-violet-950/15",

        hover: "transition-all duration-200 hover:border-violet-200 hover:bg-violet-50/40 dark:hover:border-violet-800/70 dark:hover:bg-violet-950/20",

        interactive:
            "rounded-lg border border-violet-100 bg-white transition-colors hover:border-violet-200 hover:bg-violet-50/30 dark:border-violet-900/40 dark:bg-zinc-950 dark:hover:border-violet-800/70 dark:hover:bg-violet-950/20",
    },

    text: {
        title: "text-zinc-950 dark:text-zinc-50 font-semibold tracking-tight",

        heading: "text-zinc-950 dark:text-zinc-50",

        body: "text-zinc-600 dark:text-zinc-300",

        muted: "text-zinc-500 dark:text-zinc-500",

        up: "text-emerald-600 dark:text-emerald-400",

        down: "text-red-600 dark:text-red-400",

        value: "text-zinc-950 dark:text-zinc-50 font-medium tabular-nums",
    },

    nav: {
        item: "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors text-zinc-500 hover:bg-violet-50 hover:text-violet-700 dark:text-zinc-400 dark:hover:bg-violet-950/30 dark:hover:text-violet-200",
        active:
            "flex items-center gap-2.5 rounded-lg border border-violet-200 bg-violet-50 px-3 py-2 text-sm font-semibold text-violet-800 dark:border-violet-800/60 dark:bg-violet-950/35 dark:text-violet-200",
    },

    button: {
        base:
            "inline-flex items-center justify-center gap-1.5 text-xs font-semibold transition-all duration-200 ease-out active:scale-[0.97] disabled:pointer-events-none disabled:opacity-50",
        pill: "rounded-lg px-3 py-1.5",
        primary:
            "border border-violet-200 bg-violet-50 text-violet-800 hover:border-violet-300 hover:bg-violet-100 dark:border-violet-800/60 dark:bg-violet-950/35 dark:text-violet-200 dark:hover:border-violet-700 dark:hover:bg-violet-900/25",
        secondary:
            "inline-flex items-center gap-1.5 rounded-lg border border-violet-100 bg-violet-50/30 px-3 py-1.5 text-xs font-semibold text-violet-700 transition-all duration-200 ease-out hover:border-violet-200 hover:bg-violet-50 active:scale-[0.97] dark:border-violet-900/60 dark:bg-violet-950/15 dark:text-violet-300 dark:hover:bg-violet-950/30",
        ghost:
            "text-zinc-600 hover:bg-violet-50 hover:text-violet-700 dark:text-zinc-400 dark:hover:bg-violet-950/30 dark:hover:text-violet-200",
        danger:
            "border border-red-200 bg-red-50 text-red-700 hover:border-red-300 hover:bg-red-100 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-300 dark:hover:bg-red-950/50",
    },

    input: {
        base: "w-full rounded-lg border border-violet-100 bg-white px-3 py-2 text-sm text-zinc-900 placeholder-zinc-400 outline-none transition-colors focus:border-violet-300 focus:ring-2 focus:ring-violet-100 dark:border-violet-900/50 dark:bg-zinc-950 dark:text-zinc-100 dark:placeholder-zinc-600 dark:focus:border-violet-700 dark:focus:ring-violet-950/40",
    },

    divider: "border-violet-100 dark:border-violet-900/40",
} as const;
