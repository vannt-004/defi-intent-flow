"use client";

import {useQuery} from "@tanstack/react-query";

import {getTokenPriceHistory} from "@/services/token.api";

export function useTokenPriceHistory(symbol?: string, days = 30) {
    return useQuery({
        queryKey: ["token-price-history", symbol, days],
        queryFn: () => {
            if (!symbol) {
                throw new Error("Token symbol is required");
            }
            return getTokenPriceHistory(symbol, days);
        },
        enabled: !!symbol,
        staleTime: 1000 * 60,
        retry: 1,
    });
}
