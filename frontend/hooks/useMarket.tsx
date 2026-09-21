"use client";

import {useQuery} from "@tanstack/react-query";
import {getMarkets} from "@/services/market.api";

export const useMarketQuery = () => {
    return useQuery({
        queryKey: ["markets"],
        queryFn: getMarkets,
        staleTime: 1000 * 60 * 5,
        refetchInterval: 1000 * 60 * 10,
        retry: 2,
    });
};
