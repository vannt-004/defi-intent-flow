"use client";

import {FormEvent, useRef, useState} from "react";
import Link from "next/link";
import {usePathname, useRouter} from "next/navigation";
import {Bot, Compass, Loader2, Send, Sparkles, Trash2, X} from "lucide-react";

import {useAssistantLayout} from "@/components/assistant/AssistantLayoutContext";
import type {AssistantAction} from "@/components/assistant/assistantAgents";
import Skeleton from "@/components/common/Skeleton";
import {useWalletTrackingStatusQuery} from "@/hooks/usePortfolioQuery";
import {useWallet} from "@/hooks/useWallet";
import {requestAssistantReply, type AssistantProviderMode} from "@/services/assistant.api";
import {ui} from "@/styles/ui";
import {cn} from "@/utils/cn";

type AssistantMessage = {
    id: string;
    role: "user" | "assistant";
    text: string;
    agent?: string;
    actions?: AssistantAction[];
    source?: "Google AI Studio" | "Default Mode";
    model?: string;
};

const QUICK_PROMPTS = [
    "Explain dashboard PnL",
    "Current ETH price",
    "Portfolio overview",
    "Highest risk",
    "Buy 1 ETH with USDC",
];

const GUEST_QUICK_PROMPTS = [
    "Current ETH price",
    "Portfolio overview",
];

export default function InvestorAssistant() {
    const router = useRouter();
    const pathname = usePathname();
    const {isAgentOpen, setAgentOpen} = useAssistantLayout();
    const {address} = useWallet();
    const {data: walletStatus} = useWalletTrackingStatusQuery(address);
    const quickPrompts = walletStatus?.canUseFullFeatures ? QUICK_PROMPTS : GUEST_QUICK_PROMPTS;

    const [input, setInput] = useState("");
    const [isThinking, setIsThinking] = useState(false);
    const [messages, setMessages] = useState<AssistantMessage[]>([]);
    const [providerMode, setProviderMode] = useState<AssistantProviderMode>("default");
    const inputRef = useRef<HTMLInputElement>(null);
    const conversationVersionRef = useRef(0);

    const submitPrompt = async (value: string) => {
        const text = value.trim();
        if (!text || isThinking) return;

        const conversationVersion = conversationVersionRef.current;
        setAgentOpen(true);
        setInput("");
        const userMessage: AssistantMessage = {id: crypto.randomUUID(), role: "user", text};
        setMessages((current) => [...current, userMessage].slice(-10));
        setIsThinking(true);

        try {
            const serverResult = await requestAssistantReply({
                text,
                pathname,
                wallet: address,
                providerMode,
                messages: [...messages, userMessage],
            });
            if (conversationVersionRef.current !== conversationVersion) return;

            const reply = serverResult.reply;

            const assistantMessage: AssistantMessage = {
                id: crypto.randomUUID(),
                role: "assistant",
                text: reply.message,
                agent: reply.agent,
                actions: reply.actions,
                source: serverResult.provider === "google-ai-studio" ? "Google AI Studio" : "Default Mode",
                model: serverResult.model,
            };
            setMessages((current) => [...current, assistantMessage].slice(-10));

            if (reply.href && reply.href !== pathname) {
                router.push(reply.href);
            }
        } catch {
            if (conversationVersionRef.current !== conversationVersion) return;

            const errorMessage: AssistantMessage = {
                id: crypto.randomUUID(),
                role: "assistant",
                text: "The assistant hit an error while processing this request. Try a shorter prompt.",
                agent: "Orchestrator",
            };
            setMessages((current) => [...current, errorMessage].slice(-10));
        } finally {
            if (conversationVersionRef.current === conversationVersion) {
                setIsThinking(false);
            }
        }
    };

    const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        await submitPrompt(input);
    };

    const clearConversation = () => {
        conversationVersionRef.current += 1;
        setMessages([]);
        setInput("");
        setIsThinking(false);
        window.setTimeout(() => inputRef.current?.focus(), 0);
    };

    return (
        <>
            {isAgentOpen ? (
                <>
                    <button
                        type="button"
                        aria-label="Close assistant backdrop"
                        onClick={() => setAgentOpen(false)}
                        className="fixed inset-0 z-40 bg-zinc-950/35 backdrop-blur-[1px] lg:hidden"
                    />
                    <section
                        aria-label="Investor Agent"
                        className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[100vw] flex-col overflow-hidden border-l border-violet-100 bg-white shadow-xl shadow-violet-100/70 dark:border-violet-900/50 dark:bg-zinc-950 dark:shadow-none sm:w-[min(480px,100vw)] lg:w-[clamp(340px,32vw,420px)] xl:w-[clamp(420px,28vw,520px)]"
                    >
                    <header className="flex h-14 shrink-0 items-center justify-between border-b border-violet-100 px-4 dark:border-violet-900/40">
                        <div className="flex min-w-0 items-center gap-2">
                            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-violet-100 bg-violet-50 text-violet-700 dark:border-violet-900/60 dark:bg-violet-950/30 dark:text-violet-300">
                                <Bot size={16}/>
                            </span>
                            <div className="min-w-0">
                                <p className={cn("truncate text-sm font-semibold", ui.text.heading)}>Investor Agent</p>
                                <p className={cn("truncate text-[11px]", ui.text.muted)}>
                                    Server-side AI with scoped project context
                                </p>
                            </div>
                        </div>
                        <div className="flex shrink-0 items-center gap-1">
                            <button
                                type="button"
                                aria-label="Toggle Google AI Studio mode"
                                aria-pressed={providerMode === "google"}
                                title={providerMode === "google" ? "Google AI Studio mode" : "Default deterministic NLP mode"}
                                onClick={() => setProviderMode((mode) => mode === "google" ? "default" : "google")}
                                className={cn(
                                    ui.button.base,
                                    "h-8 rounded-lg px-2 text-[10px] font-semibold",
                                    providerMode === "google"
                                        ? "border border-violet-300 bg-violet-100 text-violet-800 dark:border-violet-700 dark:bg-violet-950/60 dark:text-violet-200"
                                        : "border border-violet-100 bg-transparent text-zinc-500 hover:bg-violet-50 hover:text-violet-700 dark:border-violet-900/40 dark:text-zinc-400 dark:hover:bg-violet-950/25 dark:hover:text-violet-300"
                                )}
                            >
                                <Sparkles size={13}/>
                                <span className="hidden sm:inline">{providerMode === "google" ? "Google AI" : "Default"}</span>
                            </button>
                            <button
                                type="button"
                                aria-label="Clear assistant conversation"
                                title="Clear conversation"
                                onClick={clearConversation}
                                disabled={!messages.length && !input && !isThinking}
                                className={cn(ui.button.base, ui.button.ghost, "h-8 w-8 rounded-lg disabled:cursor-not-allowed disabled:opacity-40")}
                            >
                                <Trash2 size={15}/>
                            </button>
                            <button
                                type="button"
                                aria-label="Close assistant"
                                onClick={() => setAgentOpen(false)}
                                className={cn(ui.button.base, ui.button.ghost, "h-8 w-8 rounded-lg")}
                            >
                                <X size={16}/>
                            </button>
                        </div>
                    </header>

                    <div className="flex-1 space-y-3 overflow-y-auto p-3 sm:p-4">
                        {messages.length === 0 && (
                            <div className="space-y-3">
                                <div className="rounded-lg border border-violet-100 bg-violet-50/55 p-3 text-xs leading-5 text-zinc-600 dark:border-violet-900/40 dark:bg-violet-950/20 dark:text-zinc-300">
                                    Ask for a price, portfolio metric, risk signal, or simulation action. Default mode uses deterministic NLP routing; switch on Google AI for LLM wording over the same scoped context.
                                </div>
                                <div className="grid grid-cols-1 gap-2 min-[380px]:grid-cols-2">
                                    {quickPrompts.map((prompt) => (
                                        <button
                                            key={prompt}
                                            type="button"
                                            onClick={() => submitPrompt(prompt)}
                                            className="rounded-lg border border-violet-100 bg-white px-2.5 py-2 text-left text-[11px] font-semibold text-zinc-600 transition-colors hover:border-violet-200 hover:bg-violet-50 hover:text-violet-700 dark:border-violet-900/40 dark:bg-zinc-950 dark:text-zinc-300 dark:hover:bg-violet-950/25 dark:hover:text-violet-300"
                                        >
                                            {prompt}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}

                        {messages.map((message) => (
                            <div key={message.id} className={cn("flex", message.role === "user" ? "justify-end" : "justify-start")}>
                                <div
                                    className={cn(
                                        "max-w-[88%] break-words rounded-lg px-3 py-2 text-xs leading-5",
                                        message.role === "user"
                                            ? "bg-violet-600 text-white"
                                            : "border border-violet-100 bg-violet-50/55 text-zinc-700 dark:border-violet-900/40 dark:bg-violet-950/20 dark:text-zinc-200",
                                    )}
                                >
                                    {message.agent && (
                                        <div className="mb-1 flex min-w-0 flex-wrap items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-violet-500 dark:text-violet-300">
                                            <Compass size={11}/>
                                            <span>{message.agent}</span>
                                            {message.source && (
                                                <span className="max-w-full truncate rounded border border-violet-200/70 px-1.5 py-0.5 text-[9px] text-violet-600 dark:border-violet-800/70 dark:text-violet-300">
                                                    {message.source}
                                                    {message.model ? ` / ${message.model}` : ""}
                                                </span>
                                            )}
                                        </div>
                                    )}
                                    <MessageText text={message.text} inverted={message.role === "user"}/>
                                    {message.actions?.length ? (
                                        <div className="mt-2 flex flex-wrap gap-1.5">
                                            {message.actions.map((action) => (
                                                <Link
                                                    key={`${message.id}-${action.href}-${action.label}`}
                                                    href={action.href}
                                                    className={cn(
                                                        "rounded-md border px-2 py-1 text-[10px] font-semibold transition-colors",
                                                        action.primary
                                                            ? "border-violet-200 bg-white text-violet-700 hover:bg-violet-50 dark:border-violet-800/60 dark:bg-zinc-950 dark:text-violet-300"
                                                            : "border-violet-100 bg-white/70 text-zinc-600 hover:text-violet-700 dark:border-violet-900/50 dark:bg-zinc-950/70 dark:text-zinc-300",
                                                    )}
                                                >
                                                    {action.label}
                                                </Link>
                                            ))}
                                        </div>
                                    ) : null}
                                </div>
                            </div>
                        ))}

                        {isThinking && (
                            <div className="max-w-[88%] rounded-lg border border-violet-100 bg-violet-50/55 p-3 dark:border-violet-900/40 dark:bg-violet-950/20">
                                <div className="flex items-center gap-2 text-xs font-semibold text-violet-700 dark:text-violet-300">
                                    <Loader2 size={14} className="animate-spin"/>
                                    Routing on server
                                </div>
                                <Skeleton className="mt-2 h-3 w-48"/>
                            </div>
                        )}
                    </div>

                    <form onSubmit={handleSubmit} className="flex shrink-0 items-center gap-2 border-t border-violet-100 p-3 sm:p-4 dark:border-violet-900/40">
                        <input
                            ref={inputRef}
                            value={input}
                            onChange={(event) => setInput(event.target.value)}
                            className={cn(ui.input.base, "h-10 min-w-0 text-xs")}
                            placeholder="Message..."
                        />
                        <button
                            type="submit"
                            disabled={!input.trim() || isThinking}
                            aria-label="Send message"
                            className={cn(ui.button.base, ui.button.primary, "h-10 w-10 rounded-lg")}
                        >
                            {isThinking ? <Loader2 size={15} className="animate-spin"/> : <Send size={15}/>}
                        </button>
                    </form>
                    </section>
                </>
            ) : null}

            {!isAgentOpen && (
            <button
                type="button"
                aria-label="Open investor assistant"
                onClick={() => {
                    setAgentOpen(true);
                    window.setTimeout(() => inputRef.current?.focus(), 0);
                }}
                className="fixed bottom-4 right-4 z-50 flex h-12 items-center gap-2 rounded-lg border border-violet-200 bg-white px-3 text-sm font-semibold text-violet-800 shadow-lg shadow-violet-100/70 transition-colors hover:bg-violet-50 dark:border-violet-800/60 dark:bg-zinc-950 dark:text-violet-200 dark:shadow-none dark:hover:bg-violet-950/30"
            >
                <Bot size={17}/>
                Agent
            </button>
            )}
        </>
    );
}

function MessageText({text, inverted = false}: { text: string; inverted?: boolean }) {
    const lines = text.split("\n");

    return (
        <div className="space-y-1">
            {lines.map((line, lineIndex) => (
                <p key={`${lineIndex}-${line.slice(0, 12)}`} className="min-w-0">
                    {line ? splitLinkedText(line).map((part, index) => {
                        if (!part.href) {
                            return <span key={`${index}-${part.text}`}>{part.text}</span>;
                        }

                        return (
                            <a
                                key={`${index}-${part.href}`}
                                href={part.href}
                                target="_blank"
                                rel="noreferrer"
                                className={cn(
                                    "inline-flex max-w-full align-baseline font-semibold underline decoration-violet-400/70 underline-offset-2",
                                    inverted
                                        ? "break-all text-white"
                                        : "break-words rounded border border-violet-200/70 bg-white/80 px-1 py-0.5 text-violet-700 no-underline dark:border-violet-800/70 dark:bg-zinc-950/70 dark:text-violet-300"
                                )}
                            >
                                <span className="truncate">{part.text}</span>
                            </a>
                        );
                    }) : <span>&nbsp;</span>}
                </p>
            ))}
        </div>
    );
}

function splitLinkedText(text: string): { text: string; href?: string }[] {
    const markdownPattern = /\[([^\]\n]{1,96})\]\((https?:\/\/[^\s<>()]+)\)/g;
    const parts: { text: string; href?: string }[] = [];
    let cursor = 0;
    let match: RegExpExecArray | null;

    while ((match = markdownPattern.exec(text)) !== null) {
        if (match.index > cursor) {
            parts.push(...splitRawLinkedText(text.slice(cursor, match.index)));
        }

        const label = compactLinkText(match[1], match[2]);
        parts.push({text: label, href: match[2]});
        cursor = match.index + match[0].length;
    }

    if (cursor < text.length) {
        parts.push(...splitRawLinkedText(text.slice(cursor)));
    }

    return parts.length ? parts : [{text}];
}

function splitRawLinkedText(text: string): { text: string; href?: string }[] {
    const pattern = /(https?:\/\/[^\s<>()\]]+|0x[a-fA-F0-9]{64})/g;
    const parts: { text: string; href?: string }[] = [];
    let cursor = 0;
    let match: RegExpExecArray | null;

    while ((match = pattern.exec(text)) !== null) {
        if (match.index > cursor) {
            parts.push({text: text.slice(cursor, match.index)});
        }

        const raw = match[0];
        const trailing = raw.match(/[.,;:]+$/)?.[0] ?? "";
        const linkedText = trailing ? raw.slice(0, -trailing.length) : raw;
        const href = linkedText.startsWith("http")
            ? linkedText
            : `https://etherscan.io/tx/${linkedText}`;
        parts.push({text: compactLinkText(linkedText, href), href});
        if (trailing) {
            parts.push({text: trailing});
        }
        cursor = match.index + raw.length;
    }

    if (cursor < text.length) {
        parts.push({text: text.slice(cursor)});
    }

    return parts.length ? parts : [{text}];
}

function compactLinkText(label: string, href?: string) {
    const hash = extractTxHash(label) ?? extractTxHash(href ?? "");
    if (hash) {
        return shortHash(hash);
    }

    if (/^https?:\/\//.test(label)) {
        try {
            const url = new URL(label);
            const path = url.pathname.length > 18 ? `${url.pathname.slice(0, 16)}...` : url.pathname;
            return `${url.hostname}${path}`;
        } catch {
            return label.length > 32 ? `${label.slice(0, 24)}...` : label;
        }
    }

    return label.length > 36 ? `${label.slice(0, 30)}...` : label;
}

function extractTxHash(value: string) {
    return value.match(/0x[a-fA-F0-9]{64}/)?.[0];
}

function shortHash(value: string) {
    return `${value.slice(0, 8)}...${value.slice(-6)}`;
}
