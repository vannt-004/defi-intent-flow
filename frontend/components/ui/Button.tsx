import { ButtonHTMLAttributes } from "react";
import { cn } from "@/utils/cn";
import { ui } from "@/styles/ui";

interface TProps extends ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: "primary" | "secondary" | "ghost" | "danger";
}

export default function Button({
                                   className,
                                   variant = "primary",
                                   ...props
                               }: TProps) {
    return (
        <button
            className={cn(
                ui.button.base,
                ui.button.pill,
                ui.button[variant],
                className
            )}
            {...props}
        />
    );
}
