"use client";

import {useEffect} from "react";
import {usePathname, useRouter} from "next/navigation";
import {useAssistantLayout} from "@/components/assistant/AssistantLayoutContext";
import {AgentFocusBanner} from "@/components/assistant/AgentFocusContext";
import Sidebar from "@/components/common/Sidebar";
import TopBar from "@/components/common/TopBar";
import {useWalletTrackingStatusQuery} from "@/hooks/usePortfolioQuery";
import {useWallet} from "@/hooks/useWallet";
import {cn} from "@/utils/cn";

export default function AppLayout({children}: { children: React.ReactNode }) {
    const {isAgentOpen} = useAssistantLayout();
    const pathname = usePathname();
    const router = useRouter();
    const {address} = useWallet();
    const {data: walletStatus, isPending} = useWalletTrackingStatusQuery(address);
    const fullOnlyPath = pathname.startsWith("/risk-engine") || pathname.startsWith("/simulator");
    const canUseFullFeatures = !!walletStatus?.canUseFullFeatures;

    useEffect(() => {
        if (fullOnlyPath && (!address || (!isPending && !canUseFullFeatures))) {
            router.replace("/dashboard");
        }
    }, [address, canUseFullFeatures, fullOnlyPath, isPending, router]);

    return (
        <div className={cn(
            "flex h-screen overflow-hidden bg-violet-50/40 text-zinc-950 transition-[padding] duration-200 dark:bg-[#09070f] dark:text-zinc-50",
            isAgentOpen && "lg:pr-[clamp(340px,32vw,420px)] xl:pr-[clamp(420px,28vw,520px)]"
        )}>
            <Sidebar collapsed={isAgentOpen}/>
            <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
                <TopBar/>
                <AgentFocusBanner/>
                <main className="flex min-w-0 flex-1 overflow-auto">
                    {children}
                </main>
            </div>
        </div>
    );
}
