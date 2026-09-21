import type {AssistantReply} from "@/components/assistant/assistantAgents";
import {API_BASE_URL} from "@/services/const";

type AssistantHistoryMessage = {
    role: "user" | "assistant";
    text: string;
    agent?: string;
};

export type AssistantServerProvider = "google-ai-studio" | "default";
export type AssistantProviderMode = "default" | "google";

export type AssistantServerResponse = {
    reply: AssistantReply;
    provider: AssistantServerProvider;
    model?: string;
    reason?: string;
};

export class AssistantServerError extends Error {
    status: number;
    reason: string;

    constructor(reason: string, status: number) {
        super(reason);
        this.name = "AssistantServerError";
        this.reason = reason;
        this.status = status;
    }
}

export async function requestAssistantReply({
    text,
    pathname,
    wallet,
    messages,
    providerMode = "default",
}: {
    text: string;
    pathname: string;
    wallet?: string;
    messages: AssistantHistoryMessage[];
    providerMode?: AssistantProviderMode;
}): Promise<AssistantServerResponse> {
    const response = await fetch(`${API_BASE_URL}/assistant`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            text,
            pathname,
            wallet,
            providerMode,
            messages: messages.slice(-6).map((message) => ({
                role: message.role,
                text: message.text,
                agent: message.agent,
            })),
        }),
    });

    const payload = await safeJson(response);
    if (!response.ok || !payload?.reply || !payload.provider) {
        throw new AssistantServerError(payload?.reason || "assistant_server_unavailable", response.status);
    }

    return payload as AssistantServerResponse;
}

async function safeJson(response: Response): Promise<Partial<AssistantServerResponse> | null> {
    try {
        return await response.json();
    } catch {
        return null;
    }
}
