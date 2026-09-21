import {useState} from "react";
import {Copy, LogOut, Wallet} from "lucide-react";
import Button from "@/components/ui/Button";
import {useWallet} from "@/hooks/useWallet";
import {cn} from "@/utils/cn";
import {formatShortAddr} from "@/utils/format";
import {ui} from "@/styles/ui";

export default function WalletButton() {
    const [copied, setCopied] = useState(false);

    const {address, isConnected, connect, disconnect, isPending} = useWallet();

    const copyAddress = async () => {
        if (!address) return;

        await navigator.clipboard.writeText(address);

        setCopied(true);

        setTimeout(() => {
            setCopied(false);
        }, 1500);
    };

    if (!isConnected || !address) {
        return (
            <Button
                onClick={connect}
                disabled={isPending}
                variant="primary"
                className="gap-2"
            >
                <Wallet size={14}/>

                {isPending ? "Connecting..." : "Connect Wallet"}
            </Button>
        );
    }

    return (
        <div className="flex items-center gap-2">
            <Button
                onClick={copyAddress}
                variant="ghost"
                className={cn(
                    "flex items-center gap-2",
                    "gap-2",
                    "text-xs"
                )}
            >
                <Wallet size={12}/>

                <span className="font-mono"> {formatShortAddr(address)} </span>

                <span
                    className={cn(
                        "transition-colors",
                        copied
                            ? "text-violet-500"
                            : ui.text.muted
                    )}
                >
                    {copied
                        ? "✓"
                        : <Copy size={12}/>}
                </span>
            </Button>

            <Button
                onClick={() => disconnect()}
                variant="danger"
                className="px-3"
            >
                <LogOut size={12}/>
            </Button>
        </div>
    );
}
