"use client";

import {useCallback, useId, useLayoutEffect, useRef, useState} from "react";
import {createPortal} from "react-dom";
import {Info} from "lucide-react";

import {cn} from "@/utils/cn";

type TooltipSide = "top" | "bottom";

type TooltipPosition = {
    top: number;
    left: number;
    side: TooltipSide;
};

type InfoTooltipProps = {
    text: string;
    className?: string;
    side?: TooltipSide;
};

export default function InfoTooltip({text, className, side = "top"}: InfoTooltipProps) {
    const tooltipId = useId();
    const triggerRef = useRef<HTMLButtonElement | null>(null);
    const [open, setOpen] = useState(false);
    const [position, setPosition] = useState<TooltipPosition>({top: 0, left: 0, side});

    const updatePosition = useCallback(() => {
        const trigger = triggerRef.current;
        if (!trigger || typeof window === "undefined") return;

        const rect = trigger.getBoundingClientRect();
        const nextSide = side === "top" && rect.top < 88 ? "bottom" : side;
        const tooltipMaxWidth = Math.min(320, window.innerWidth - 24);
        const left = Math.min(
            Math.max(rect.left + rect.width / 2, 12 + tooltipMaxWidth / 2),
            window.innerWidth - 12 - tooltipMaxWidth / 2,
        );
        const top =
            nextSide === "top"
                ? Math.max(10, rect.top - 8)
                : Math.min(window.innerHeight - 10, rect.bottom + 8);

        setPosition({top, left, side: nextSide});
    }, [side]);

    useLayoutEffect(() => {
        if (!open) return;

        updatePosition();
        window.addEventListener("resize", updatePosition);
        window.addEventListener("scroll", updatePosition, true);

        return () => {
            window.removeEventListener("resize", updatePosition);
            window.removeEventListener("scroll", updatePosition, true);
        };
    }, [open, updatePosition]);

    const tooltip =
        open && typeof document !== "undefined"
            ? createPortal(
                  <div
                      id={tooltipId}
                      role="tooltip"
                      className="pointer-events-none fixed z-[90] max-w-[min(320px,calc(100vw-24px))] rounded-lg border border-violet-500/40 bg-zinc-950 px-3 py-2 text-left text-[11px] leading-relaxed text-zinc-100 shadow-xl shadow-black/40"
                      style={{
                          top: position.top,
                          left: position.left,
                          transform: position.side === "top" ? "translate(-50%, -100%)" : "translate(-50%, 0)",
                      }}
                  >
                      {text}
                  </div>,
                  document.body,
              )
            : null;

    return (
        <>
            <button
                ref={triggerRef}
                type="button"
                className={cn(
                    "inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-zinc-400 outline-none transition-colors hover:text-violet-400 focus-visible:text-violet-300 focus-visible:ring-2 focus-visible:ring-violet-500/70",
                    className,
                )}
                aria-describedby={open ? tooltipId : undefined}
                aria-label={text}
                onBlur={() => setOpen(false)}
                onFocus={() => setOpen(true)}
                onKeyDown={(event) => {
                    if (event.key === "Escape") setOpen(false);
                }}
                onMouseEnter={() => setOpen(true)}
                onMouseLeave={() => setOpen(false)}
            >
                <Info size={12} aria-hidden="true"/>
            </button>
            {tooltip}
        </>
    );
}
