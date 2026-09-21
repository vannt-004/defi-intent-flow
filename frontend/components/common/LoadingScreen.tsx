export default function LoadingScreen() {
    return (
        <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-violet-50 dark:bg-[#09070f]">
            <div className="h-12 w-12 animate-spin rounded-full border-2 border-violet-200 border-t-violet-600 dark:border-violet-950 dark:border-t-violet-400" />
            <p className="animate-pulse text-xs font-semibold uppercase tracking-widest text-violet-500 dark:text-violet-300">
                Loading DeFi Intelligence…
            </p>
        </div>
    );
}
