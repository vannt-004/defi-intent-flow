import React from "react";
import {cn} from "@/utils/cn";
import {ui} from "@/styles/ui";

type CardProps = React.HTMLAttributes<HTMLDivElement> & {
    hover?: boolean;
};

export default function Card({
                                 children,
                                 className,
                                 hover = true,
                                 ...props
                             }: CardProps) {

    return (
        <div
            className={cn(
                ui.card.base,
                hover && ui.card.hover,
                className
            )}
            {...props}
        >
            {children}
        </div>
    );
}