import {API_BASE_URL} from "@/services/const";

export type SimulationPayload =
    | { type: "price_shock"; shocks: Record<string, number> }
    | { type: "lend" | "stake"; symbol: string; amount: number; marketId?: string; gasUsd?: number }
    | { type: "borrow"; symbol: string; amount: number; marketId?: string; shockPct?: number; gasUsd?: number }
    | { type: "swap"; fromSymbol: string; toSymbol: string; amount: number; slippagePct?: number; gasUsd?: number }
    | { type: "provide_liquidity"; token0: string; token1: string; amount0: number; amount1?: number; marketId?: string; shockPct?: number; gasUsd?: number };

export type SimulationResult = {
    wallet: string;
    timestamp: number;
    type: string;
    before: Record<string, number>;
    after: Record<string, number>;
    delta: Record<string, number>;
    changes: { label: string; deltaUsd: number }[];
    warnings: string[];
    assumptions: string[];
    strategy?: Record<string, any> | null;
    feeModel?: Record<string, any>;
    notice: string;
};

export async function simulateWallet(wallet: string, payload: SimulationPayload): Promise<SimulationResult> {
    const response = await fetch(`${API_BASE_URL}/simulation/${wallet}`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error("Failed to run simulation");
    return response.json();
}

export async function parseSimulationIntent(text: string): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/simulation/intent/parse`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({text}),
    });
    if (!response.ok) throw new Error("Failed to parse simulation intent");
    return response.json();
}
