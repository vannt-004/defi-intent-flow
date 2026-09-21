import {API_BASE_URL} from "@/services/const";

export type TokenImageMap = Record<string, string>;

export type TokenPriceHistory = {
    symbol: string;
    name?: string;
    image?: string;
    currentPrice: number;
    change7dPct: number;
    change30dPct: number;
    high: number;
    low: number;
    history: { timestamp: number; price: number }[];
};

export async function getTokenImages(): Promise<TokenImageMap> {
    const response = await fetch(`${API_BASE_URL}/tokens/images`, {
        next: {
            revalidate: 60 * 60 * 24,
        },
    });

    if (!response.ok) {
        throw new Error("Failed to fetch token images");
    }

    return response.json();
}

export async function getTokenPriceHistory(symbol: string, days = 30): Promise<TokenPriceHistory> {
    const response = await fetch(`${API_BASE_URL}/tokens/${symbol}/history?days=${days}`);

    if (!response.ok) {
        throw new Error("Failed to fetch token price history");
    }

    return response.json();
}
