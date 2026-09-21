"use client";

import {QueryClient, QueryClientProvider} from "@tanstack/react-query";
import {WagmiProvider, createConfig, http} from "wagmi";
import {mainnet} from "wagmi/chains";
import {AgentFocusProvider} from "@/components/assistant/AgentFocusContext";
import {AssistantLayoutProvider} from "@/components/assistant/AssistantLayoutContext";
import InvestorAssistant from "@/components/assistant/InvestorAssistant";

const config = createConfig({
    chains: [mainnet],
    transports: {
        [mainnet.id]: http(),
    },
});

const queryClient = new QueryClient();

export default function Providers({
                                      children,
                                  }: {
    children: React.ReactNode;
}) {
    return (
        <WagmiProvider config={config}>
            <QueryClientProvider client={queryClient}>
                <AssistantLayoutProvider>
                    <AgentFocusProvider>
                        {children}
                        <InvestorAssistant/>
                    </AgentFocusProvider>
                </AssistantLayoutProvider>
            </QueryClientProvider>
        </WagmiProvider>
    );
}
