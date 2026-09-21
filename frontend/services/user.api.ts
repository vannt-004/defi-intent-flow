import {TPortfolioAnalytics, TPortfolioData, TPortfolioRisk, TPositionPnL, TPositionRisk, TTransaction} from "@/types/portfolio";
import {API_BASE_URL} from "@/services/const";

type RiskRecord = Record<string, unknown>;
type RiskLevel = TPortfolioRisk["portfolio"]["riskLevel"];

const RISK_LEVELS = new Set<RiskLevel>(["LOW", "MEDIUM", "HIGH", "CRITICAL"]);

const isRecord = (value: unknown): value is RiskRecord =>
    typeof value === "object" && value !== null && !Array.isArray(value);

const arrayFrom = (value: unknown) => Array.isArray(value) ? value : [];

const valueFrom = (record: RiskRecord, ...keys: string[]) => {
    for (const key of keys) {
        if (record[key] !== undefined && record[key] !== null) return record[key];
    }
    return undefined;
};

const numberFrom = (record: RiskRecord, ...keys: string[]) => {
    const value = valueFrom(record, ...keys);
    if (typeof value === "number" && Number.isFinite(value)) return value;
    if (typeof value === "string" && value.trim()) {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : undefined;
    }
    return undefined;
};

const stringFrom = (record: RiskRecord, ...keys: string[]) => {
    const value = valueFrom(record, ...keys);
    return typeof value === "string" && value.trim() ? value : undefined;
};

const booleanOrNullFrom = (record: RiskRecord, ...keys: string[]) => {
    const value = valueFrom(record, ...keys);
    return typeof value === "boolean" ? value : null;
};

const riskLevelFromScore = (score: number): RiskLevel => {
    if (score >= 85) return "CRITICAL";
    if (score >= 65) return "HIGH";
    if (score >= 30) return "MEDIUM";
    return "LOW";
};

const riskLevelFrom = (value: unknown, score: number): RiskLevel => {
    if (typeof value === "string") {
        const level = value.toUpperCase();
        if (RISK_LEVELS.has(level as RiskLevel)) return level as RiskLevel;
    }
    return riskLevelFromScore(score);
};

const normalizeRiskRange = (value: unknown): TPositionRisk["range"] | undefined => {
    if (!isRecord(value)) return undefined;

    return {
        inRange: booleanOrNullFrom(value, "inRange", "in_range"),
        currentTick: numberFrom(value, "currentTick", "current_tick") ?? null,
        tickLower: numberFrom(value, "tickLower", "tick_lower") ?? null,
        tickUpper: numberFrom(value, "tickUpper", "tick_upper") ?? null,
        rangeWidthTicks: numberFrom(value, "rangeWidthTicks", "range_width_ticks"),
        distanceToRangeEdgePct: numberFrom(value, "distanceToRangeEdgePct", "distance_to_range_edge_pct") ?? null,
        forecastTick7d: numberFrom(value, "forecastTick7d", "forecast_tick_7d") ?? null,
        forecastOutOfRange: booleanOrNullFrom(value, "forecastOutOfRange", "forecast_out_of_range"),
    };
};

const normalizeRiskHistory = (value: unknown): TPositionRisk["history"] => {
    return arrayFrom(value).flatMap((item) => {
        if (!isRecord(item)) return [];
        return [{
            timestamp: numberFrom(item, "timestamp") ?? 0,
            valueUsd: numberFrom(item, "valueUsd", "value_usd") ?? 0,
            pnlUsd: numberFrom(item, "pnlUsd", "pnl_usd") ?? 0,
        }];
    });
};

const normalizePositionRisk = (value: unknown, index: number): TPositionRisk => {
    const record = isRecord(value) ? value : {};
    const rawType = stringFrom(record, "type");
    const positionType: TPositionRisk["type"] = rawType === "lp" || rawType === "amm" ? "lp" : "lending";
    const riskScore = numberFrom(record, "riskScore", "risk_score") ?? 0;
    const symbol = stringFrom(record, "symbol");
    const token0 = stringFrom(record, "token0", "token_0");
    const token1 = stringFrom(record, "token1", "token_1");
    const positionId = stringFrom(record, "positionId", "position_id")
        || [symbol, token0, token1, index].filter(Boolean).join("-")
        || `position-${index}`;
    const signals = arrayFrom(valueFrom(record, "signals"))
        .filter((signal): signal is string => typeof signal === "string");
    const priceTrend = valueFrom(record, "priceTrend", "price_trend");

    return {
        positionId,
        protocol: stringFrom(record, "protocol"),
        type: positionType,
        side: stringFrom(record, "side"),
        symbol,
        token0,
        token1,
        valueUsd: numberFrom(record, "valueUsd", "value_usd") ?? 0,
        riskScore,
        riskLevel: riskLevelFrom(valueFrom(record, "riskLevel", "risk_level"), riskScore),
        healthFactor: numberFrom(record, "healthFactor", "health_factor"),
        liquidationThreshold: numberFrom(record, "liquidationThreshold", "liquidation_threshold"),
        liquidationBufferUsd: numberFrom(record, "liquidationBufferUsd", "liquidation_buffer_usd"),
        priceMoveToLiquidationPct: numberFrom(record, "priceMoveToLiquidationPct", "price_move_to_liquidation_pct") ?? null,
        forecastLiquidationRiskPct: numberFrom(record, "forecastLiquidationRiskPct", "forecast_liquidation_risk_pct"),
        impermanentLossUsd: numberFrom(record, "impermanentLossUsd", "impermanent_loss_usd"),
        impermanentLossPct: numberFrom(record, "impermanentLossPct", "impermanent_loss_pct"),
        forecastImpermanentLossUsd: numberFrom(record, "forecastImpermanentLossUsd", "forecast_impermanent_loss_usd"),
        forecastImpermanentLossPct: numberFrom(record, "forecastImpermanentLossPct", "forecast_impermanent_loss_pct"),
        holdValueUsd: numberFrom(record, "holdValueUsd", "hold_value_usd"),
        collectedFeeUsd: numberFrom(record, "collectedFeeUsd", "collected_fee_usd"),
        range: normalizeRiskRange(valueFrom(record, "range")),
        priceTrend: isRecord(priceTrend) ? priceTrend as TPositionRisk["priceTrend"] : {},
        signals,
        history: normalizeRiskHistory(valueFrom(record, "history")),
    };
};

const normalizePortfolioRisk = (value: unknown): TPortfolioRisk => {
    const record = isRecord(value) ? value : {};
    const portfolioRecord = isRecord(record.portfolio) ? record.portfolio : {};
    const positions = arrayFrom(record.positions).map(normalizePositionRisk);
    const totalRiskValueUsd = numberFrom(portfolioRecord, "totalRiskValueUsd", "total_risk_value_usd")
        ?? positions.reduce((sum, position) => sum + position.valueUsd, 0);
    const highRiskValueUsd = numberFrom(portfolioRecord, "highRiskValueUsd", "high_risk_value_usd")
        ?? positions
            .filter((position) => position.riskLevel === "HIGH" || position.riskLevel === "CRITICAL")
            .reduce((sum, position) => sum + position.valueUsd, 0);
    const riskScore = numberFrom(portfolioRecord, "riskScore", "risk_score")
        ?? (positions.length ? positions.reduce((sum, position) => sum + position.riskScore, 0) / positions.length : 0);

    return {
        wallet: stringFrom(record, "wallet") ?? "",
        timestamp: numberFrom(record, "timestamp") ?? 0,
        portfolio: {
            netWorthUsd: numberFrom(portfolioRecord, "netWorthUsd", "net_worth_usd") ?? totalRiskValueUsd,
            totalRiskValueUsd,
            highRiskValueUsd,
            highRiskRatio: numberFrom(portfolioRecord, "highRiskRatio", "high_risk_ratio")
                ?? (totalRiskValueUsd > 0 ? highRiskValueUsd / totalRiskValueUsd * 100 : 0),
            riskScore,
            riskLevel: riskLevelFrom(valueFrom(portfolioRecord, "riskLevel", "risk_level"), riskScore),
            positionCount: numberFrom(portfolioRecord, "positionCount", "position_count") ?? positions.length,
        },
        positions,
    };
};

export type WalletTrackingStatus = {
    wallet: string;
    status: "guest" | "queued" | "syncing" | "synced" | "disabled" | string;
    isTracked: boolean;
    canUseFullFeatures: boolean;
    hasSnapshot: boolean;
    lastSyncedAt?: number | null;
    message: string;
};

export const getWalletTrackingStatus = async (wallet: string): Promise<WalletTrackingStatus> => {
    const response = await fetch(`${API_BASE_URL}/portfolio/wallet/${wallet}/status`);
    if (!response.ok) throw new Error("Something went wrong while fetching wallet status");
    return response.json();
};

export const requestUpdatePlus = async (wallet: string): Promise<{ success: boolean; wallet: string; status: string; msg: string; event_id?: string }> => {
    const response = await fetch(`${API_BASE_URL}/portfolio/wallet`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({wallet}),
    });
    if (!response.ok) throw new Error("Something went wrong while adding wallet");
    return response.json();
};

export const getPortfolio = async (wallet: string): Promise<TPortfolioData> => {
    const response = await fetch(`${API_BASE_URL}/portfolio/${wallet}`);
    if (!response.ok) throw new Error("Something went wrong while fetching positions");
    return response.json();
};

export const getPortfolioPreview = async (wallet: string): Promise<TPortfolioData> => {
    const response = await fetch(`${API_BASE_URL}/portfolio/preview/${wallet}`);
    if (!response.ok) throw new Error("Something went wrong while fetching portfolio preview");
    return response.json();
};

export const getAssets = async (wallet: string) => {
    const portfolio = await getPortfolio(wallet);
    return portfolio.assets;
};

export const getPortfolioAnalytics = async (wallet: string): Promise<TPortfolioAnalytics> => {
    const response = await fetch(`${API_BASE_URL}/portfolio/analytics/${wallet}`);
    if (!response.ok) throw new Error("Something went wrong while fetching portfolio analytics");
    return response.json();
};

export const getPortfolioAnalyticsPreview = async (wallet: string): Promise<TPortfolioAnalytics> => {
    const response = await fetch(`${API_BASE_URL}/portfolio/analytics/${wallet}/preview`);
    if (!response.ok) throw new Error("Something went wrong while fetching portfolio analytics preview");
    return response.json();
};

export const getPortfolioTransactions = async (wallet: string, limit = 100): Promise<TTransaction[]> => {
    const response = await fetch(`${API_BASE_URL}/portfolio/analytics/${wallet}/transactions?limit=${limit}`);
    if (!response.ok) throw new Error("Something went wrong while fetching portfolio transactions");
    return response.json();
};

export const getPortfolioPositionsPnL = async (wallet: string): Promise<TPositionPnL[]> => {
    const response = await fetch(`${API_BASE_URL}/portfolio/analytics/${wallet}/positions-pnl`);
    if (!response.ok) throw new Error("Something went wrong while fetching portfolio PnL");
    return response.json();
};

export const getPortfolioRisk = async (wallet: string): Promise<TPortfolioRisk> => {
    const response = await fetch(`${API_BASE_URL}/portfolio/analytics/${wallet}/risk`);
    if (!response.ok) throw new Error("Something went wrong while fetching portfolio risk");
    return normalizePortfolioRisk(await response.json());
};
