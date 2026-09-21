import {API_BASE_URL} from "@/services/const";

export interface MarketRankingPayload {
    profile_or_matrix: string | number[][];
    limit?: number;
    weights?: {
        yield: number;
        safety: number;
        efficiency: number;
    };
}

export const getMarkets = async () => {
    const response = await fetch(`${API_BASE_URL}/yields`);
    if (!response.ok) throw new Error("Failed to fetch yield data");

    const result = await response.json();
    return result.data ?? result;
};

export const getRankedMarkets = async (payload: MarketRankingPayload) => {
    const profile = typeof payload.profile_or_matrix === 'string' ? payload.profile_or_matrix : 'balanced';
    const limit = payload.limit ?? 100;
    const params = new URLSearchParams({
        profile,
        limit: String(limit),
    });

    if (payload.weights) {
        params.set("yield_weight", String(payload.weights.yield));
        params.set("safety_weight", String(payload.weights.safety));
        params.set("efficiency_weight", String(payload.weights.efficiency));
    }

    const response = await fetch(`${API_BASE_URL}/yields?${params.toString()}`);
    if (!response.ok) throw new Error("Failed to fetch standardized yield data");

    const result = await response.json();
    return result.data ?? result;
};
