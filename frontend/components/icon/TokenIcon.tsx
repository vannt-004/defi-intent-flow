"use client"

import {useState} from "react"
import {useTokenImages} from "@/hooks/useTokenImages"
import {cn} from "@/utils/cn"

type Props = {
    symbol: string
    size?: number
    className?: string
    fallbackClassName?: string
}

export function TokenIcon({symbol, size = 24, className, fallbackClassName}: Props) {
    const {data} = useTokenImages()
    const [failed, setFailed] = useState(false)

    const normalized = (symbol || "?").toUpperCase()
    const image = data?.[normalized]

    if (!image || failed) {
        return (
            <span
                className={cn(
                    "inline-flex shrink-0 items-center justify-center rounded-full bg-zinc-100 text-[10px] font-semibold text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300",
                    fallbackClassName,
                    className
                )}
                style={{width: size, height: size}}
                title={normalized}
            >
                {normalized.slice(0, 3)}
            </span>
        )
    }

    return (
        <img
            src={image}
            alt={normalized}
            width={size}
            height={size}
            loading="lazy"
            onError={() => setFailed(true)}
            className={cn("shrink-0 rounded-full object-cover", className)}
        />
    )
}
