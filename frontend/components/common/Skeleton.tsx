import {cn} from "@/utils/cn";

export default function Skeleton({className = ""}: { className?: string; }) {
    return (
        <div
            className={cn(
                "relative overflow-hidden rounded-lg bg-violet-100/80 dark:bg-violet-950/35",
                "before:absolute before:inset-y-0 before:left-0 before:w-full before:-translate-x-full before:animate-[shimmer_1.4s_ease-in-out_infinite]",
                "before:bg-gradient-to-r before:from-transparent before:via-white/60 before:to-transparent dark:before:via-violet-300/10",
                className
            )}
        />
    );
}
