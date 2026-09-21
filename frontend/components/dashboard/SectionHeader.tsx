import {LucideIcon} from "lucide-react";

import {formatMoney} from "@/utils/format";

interface TProps {
    icon: LucideIcon;
    color: string;
    title: string;
    value: number;
}

export default function SectionHeader(props: TProps) {
    const {icon: Icon, color, title, value} = props;

    return (
        <div className="flex items-center justify-between mb-5">
            <h2
                className={`
                    flex items-center gap-2
                    text-sm font-bold uppercase tracking-widest
                    ${color}
                `}
            >
                <Icon size={15}/>

                {title}
            </h2>

            <span className="text-xs text-slate-500 font-mono">
                {formatMoney(value)} total
            </span>
        </div>
    );
}