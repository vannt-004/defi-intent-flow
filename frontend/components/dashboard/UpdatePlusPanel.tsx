"use client";

import {useState} from "react";
import {CheckCircle2, Crown, Loader2, X} from "lucide-react";
import {useQueryClient} from "@tanstack/react-query";

import Button from "@/components/ui/Button";
import Div from "@/components/ui/Div";
import {requestUpdatePlus, WalletTrackingStatus} from "@/services/user.api";
import {formatShortAddr} from "@/utils/format";
import {cn} from "@/utils/cn";
import {ui} from "@/styles/ui";

type Props = {
    wallet: string;
    status?: WalletTrackingStatus;
};

export default function UpdatePlusPanel({wallet, status}: Props) {
    const queryClient = useQueryClient();
    const [confirmOpen, setConfirmOpen] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const isQueued = status?.status === "queued" || status?.status === "syncing";

    const submit = async () => {
        setIsSubmitting(true);
        setError(null);
        try {
            await requestUpdatePlus(wallet);
            setConfirmOpen(false);
            await queryClient.invalidateQueries({queryKey: ["wallet-tracking-status", wallet]});
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : "Could not start Update Plus");
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <>
            <Div className="border-violet-300 bg-violet-50/70 dark:border-violet-900/60 dark:bg-violet-950/20">
                <div className="grid gap-4 md:grid-cols-[1fr_auto] md:items-center">
                    <div>
                        <div className="flex items-center gap-2">
                            {isQueued ? (
                                <Loader2 size={16} className="animate-spin text-violet-500"/>
                            ) : (
                                <Crown size={16} className="text-violet-500"/>
                            )}
                            <p className={cn("text-sm font-semibold", ui.text.heading)}>
                                {isQueued ? "Portfolio crawl is running" : "Connected wallet is in guest mode"}
                            </p>
                        </div>
                        <p className={cn("mt-2 max-w-3xl text-xs leading-5", ui.text.muted)}>
                            {isQueued
                                ? "Your wallet has been added to the crawl queue. The dashboard will refresh automatically when the first snapshot is ready."
                                : "Guest mode previews current holdings and protocol positions without saving your wallet. Update Plus adds this wallet to the system so cashflow, risk engine, simulation, and transaction history can be built."}
                        </p>
                        <p className="mt-2 font-mono text-xs text-violet-600 dark:text-violet-300">
                            {formatShortAddr(wallet)}
                        </p>
                    </div>
                    {isQueued ? (
                        <div className="rounded-lg border border-violet-200 bg-white px-3 py-2 text-xs font-semibold text-violet-700 dark:border-violet-900/50 dark:bg-zinc-950 dark:text-violet-300">
                            Waiting for first snapshot
                        </div>
                    ) : (
                        <Button onClick={() => setConfirmOpen(true)} variant="primary" className="gap-2">
                            <Crown size={14}/>
                            Update Plus
                        </Button>
                    )}
                </div>
            </Div>

            {confirmOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
                    <div className="w-full max-w-md rounded-xl border border-violet-200 bg-white p-5 shadow-xl dark:border-violet-900/60 dark:bg-zinc-950">
                        <div className="flex items-start justify-between gap-3">
                            <div>
                                <p className={cn("text-base font-semibold", ui.text.heading)}>Enable Update Plus?</p>
                                <p className={cn("mt-2 text-sm leading-6", ui.text.muted)}>
                                    This will add your wallet to the system and start an initial crawl. It may take a few minutes before all portfolio features are available.
                                </p>
                            </div>
                            <button onClick={() => setConfirmOpen(false)} className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-900">
                                <X size={16}/>
                            </button>
                        </div>

                        {error && <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600 dark:bg-red-950/20">{error}</p>}

                        <div className="mt-5 flex justify-end gap-2">
                            <Button onClick={() => setConfirmOpen(false)} variant="ghost" disabled={isSubmitting}>
                                Cancel
                            </Button>
                            <Button onClick={submit} variant="primary" disabled={isSubmitting} className="gap-2">
                                {isSubmitting ? <Loader2 size={14} className="animate-spin"/> : <CheckCircle2 size={14}/>}
                                Confirm
                            </Button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
