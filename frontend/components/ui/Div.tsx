import React, {ReactNode} from "react";
import {cn} from "@/utils/cn";


export default function Div({children, className}: { children: ReactNode, className?: string }) {
    return (
        <div
            className={cn(
                "relative rounded-lg border border-violet-100/80 bg-white/95 p-5 shadow-sm shadow-violet-100/60 dark:border-violet-900/40 dark:bg-zinc-950/90 dark:shadow-none",
                className
            )}
           >
            <div
                className="absolute left-4 right-4 top-0 h-px bg-gradient-to-r from-transparent via-violet-400/40 to-transparent"/>
            {children}
        </div>
    );
}
