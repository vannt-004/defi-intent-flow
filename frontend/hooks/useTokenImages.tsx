"use client"

import { useQuery } from "@tanstack/react-query"
import {getTokenImages} from "@/services/token.api";

export function useTokenImages() {

    return useQuery({
        queryKey: ["token-images"],
        queryFn: getTokenImages,
        staleTime:
        Infinity,
        gcTime:
        Infinity,
        retry: false,
    })
}