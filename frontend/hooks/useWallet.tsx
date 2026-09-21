"use client";

import {useAccount, useConnect, useDisconnect} from "wagmi";

export function useWallet() {
    const fixedWallet = "0x01110a45258af739d4d08116d5394e392a44d76e";

    const {address, isConnected} = useAccount();

    const {connect, connectors, isPending} = useConnect();

    const {disconnect} = useDisconnect();

    const walletAddress = fixedWallet || address;

    return {
        address: walletAddress,
        isConnected: fixedWallet ? true : isConnected,
        connect: () =>
            connect({
                connector: connectors[0],
            }),
        disconnect,
        connectors,
        isPending,
    };
}
