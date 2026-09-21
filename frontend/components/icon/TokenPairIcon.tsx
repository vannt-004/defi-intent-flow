"use client"

import {TokenIcon} from "@/components/icon/TokenIcon"
import {cn} from "@/utils/cn"

type Props = {
    symbols: string[]
    size?: number
    className?: string
}

export function TokenPairIcon({symbols, size = 30, className}: Props) {
    const [first, second] = symbols.filter(Boolean)

    if (!second) {
        return <TokenIcon symbol={first || "LP"} size={size} className={className}/>
    }

    const childSize = Math.round(size * 0.72)

    return (
        <div
            className={cn("relative shrink-0", className)}
            style={{width: size, height: size}}
            title={`${first}/${second}`}
        >
            <TokenIcon
                symbol={first}
                size={childSize}
                className="absolute left-0 top-0 border-2 border-white dark:border-zinc-950"
            />
            <TokenIcon
                symbol={second}
                size={childSize}
                className="absolute bottom-0 right-0 border-2 border-white dark:border-zinc-950"
            />
        </div>
    )
}
