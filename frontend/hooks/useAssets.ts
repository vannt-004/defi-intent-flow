"use client";

import {useQuery} from "@tanstack/react-query";
import {getAssets} from "@/services/user.api";

export const useAssetsQuery = (
    wallet?: string,
) => {
    return useQuery({
        queryKey: ["assets", wallet],
        queryFn: () => {
            if (!wallet) {
                throw new Error("Wallet is required");
            }

            return getAssets(wallet);
        },
        enabled: !!wallet,
        staleTime: 1000 * 30,
        refetchInterval: 1000 * 60,
        retry: 2,
    });
};