"use client";

import {createContext, useContext, useMemo, useState} from "react";

type AssistantLayoutContextValue = {
    isAgentOpen: boolean;
    setAgentOpen: (open: boolean) => void;
};

const AssistantLayoutContext = createContext<AssistantLayoutContextValue | null>(null);

export function AssistantLayoutProvider({children}: { children: React.ReactNode }) {
    const [isAgentOpen, setAgentOpen] = useState(false);
    const value = useMemo(() => ({isAgentOpen, setAgentOpen}), [isAgentOpen]);

    return (
        <AssistantLayoutContext.Provider value={value}>
            {children}
        </AssistantLayoutContext.Provider>
    );
}

export function useAssistantLayout() {
    const value = useContext(AssistantLayoutContext);
    if (!value) {
        throw new Error("useAssistantLayout must be used within AssistantLayoutProvider");
    }
    return value;
}
