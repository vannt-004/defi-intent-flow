"use client";

import {useQuery} from "@tanstack/react-query";
import {
    getPortfolio,
    getPortfolioAnalytics,
    getPortfolioAnalyticsPreview,
    getPortfolioPreview,
    getPortfolioRisk,
    getWalletTrackingStatus,
} from "@/services/user.api";

export const useWalletTrackingStatusQuery = (wallet?: string) => {
    return useQuery({
        queryKey: ["wallet-tracking-status", wallet],
        queryFn: () => {
            if (!wallet) throw new Error("Wallet is required");
            return getWalletTrackingStatus(wallet);
        },
        enabled: !!wallet,
        staleTime: 1000 * 10,
        refetchInterval: (query) => {
            const status = query.state.data?.status;
            return status === "queued" || status === "syncing" ? 5000 : false;
        },
        retry: 1,
    });
};

export const usePortfolioQuery = (
    wallet?: string,
    enabled = true,
    preview = false,
) => {
    return useQuery({
        queryKey: ["portfolio", preview ? "preview" : "full", wallet],
        queryFn: () => {
            if (!wallet) {
                throw new Error("Wallet is required");
            }

            return preview ? getPortfolioPreview(wallet) : getPortfolio(wallet);
        },
        enabled: !!wallet && enabled,
        staleTime: 1000 * 60 * 3,
        refetchInterval: 1000 * 60 * 5,
        retry: 2,
    });
};

export const usePortfolioAnalyticsQuery = (
    wallet?: string,
    enabled = true,
    preview = false,
) => {
    return useQuery({
        queryKey: ["portfolio-analytics", preview ? "preview" : "full", wallet],
        queryFn: () => {
            if (!wallet) {
                throw new Error("Wallet is required");
            }

            return preview ? getPortfolioAnalyticsPreview(wallet) : getPortfolioAnalytics(wallet);
        },
        enabled: !!wallet && enabled,
        staleTime: 1000 * 60 * 3,
        refetchInterval: 1000 * 60 * 5,
        retry: 2,
    });
};

export const usePortfolioRiskQuery = (
    wallet?: string,
    enabled = true,
) => {
    return useQuery({
        queryKey: ["portfolio-risk", wallet],
        queryFn: () => {
            if (!wallet) {
                throw new Error("Wallet is required");
            }

            return getPortfolioRisk(wallet);
        },
        enabled: !!wallet && enabled,
        staleTime: 1000 * 60 * 3,
        refetchInterval: 1000 * 60 * 5,
        retry: 2,
    });
};
