export type TAsset = {
    type: string,
    symbol: string,
    name: string,
    address: string,
    balanceRaw: number,
    decimals: number,
    balance: number,
    price: number,
    valueUsd: number
}

export type TAllocation = {
    purpose: string,
    valueUsd: number,
    percentage: number
}

export type TPosition = {
    type: string,
    protocol: string,
    positionId: string,
    marketId: string,
    asset: string[],
    rawSymbol: string,
    token0?: string | null,
    token1?: string | null,
    balance: number,
    valueUsd: number,
    side: string,
    isCollateral: boolean,
    maxLtv: number,
    liquidationThreshold: number,
    supplyApr: number,
    borrowApr: number,
    borrowStableApr: number,
};

export type TPositionSummary = {
    positionCount: number;
    totalWalletUsd: number;
    totalAmmUsd: number;
    totalSupplyUsd: number;
    totalBorrowUsd: number;
    netWorthUsd: number;
    collateralUsd: number;
    healthFactor: number;
};

export type TPortfolioData = {
    positions: TPosition[];
    allocations: TAllocation[];
    summary: TPositionSummary;
    alerts: TAlert[];
    assets: TAsset[]
};

export type TPositionPnL = {
    positionId: string;
    name: string;
    protocol: string;
    type: "hold" | "lend" | "farm" | "borrow";
    valueUsd: number;
    balance?: number;
    token0?: string | null;
    token1?: string | null;
    amount0?: number | null;
    amount1?: number | null;
    costBasisUsd: number;
    entryPrice: number | null;
    currentPrice: number | null;
    pnlUsd: number;
    pnlPct: number | null;
    pnlType: "unrealized" | "interest_earned" | "yield" | "interest_cost";
    pnlReliable?: boolean;
    pnlNote?: string | null;
    pnlMethod?: "average_cost_basis" | "basis_unavailable" | "protocol_cashflow" | "flow_unavailable";
    costBasisReliable?: boolean;
    healthFactor: number; // 0–100, <40 = danger
    apy: number | null;
};

export type TNetWorth = {
    totalUsd: number;
    calculatedTotalUsd?: number;
    tokenHoldUsd: number;
    supplyUsd?: number;
    lpUsd?: number;
    vaultUsd?: number;
    borrowUsd?: number;
    lendingUsd: number;
    interestEarnedUsd: number;
    debtUsd: number;
    debtInterestUsd: number;
    farmingUsd: number;
};

export type TPnLSummary = {
    todayUsd: number;
    todayPct: number;
    sevenDayUsd: number;
    sevenDayPct: number;
    sevenDayExternalFlowUsd?: number;
    allTimeUsd: number;
    allTimePct: number;
    allTimeExternalFlowUsd?: number;
    todayExternalFlowUsd?: number;
    roiPct: number;
    method?: string;
};

export type TPnLPeriod = "1D" | "7D" | "1M" | "3M" | "ALL";

export type TChartPoint = {
    timestamp?: number | null;
    label: string;
    tokenHold: number;
    positions: number;
    netWorth: number;
};

export type TTransaction = {
    id: string;
    txId?: string;
    action?: string;
    actionLabel?: string;
    direction?: "in" | "out" | null;
    transactionCategory?: string;
    eventSource?: string;
    protocol?: string;
    marketId?: string;
    poolId?: string;
    poolKey?: string;
    poolLabel?: string;
    description: string;
    amountUsd: number;
    recordedAmountUsd?: number;
    priceAtTx?: number | null;
    estimatedExecutionPrice?: number | null;
    priceSource?: string | null;
    priceTimestamp?: number | null;
    priceDeltaSeconds?: number | null;
    priceMaxDeltaSeconds?: number | null;
    priceReliable?: boolean | null;
    priceNote?: string | null;
    realizedPnlUsd?: number;
    symbol?: string;
    amount?: number;
    timestamp?: number;
    type: "earn" | "cost" | "transfer";
    timeAgo: string;
    source: string;
    gasCostUsd?: number;
};

export type TTransactionPoolGroup = {
    poolKey: string;
    poolLabel: string;
    protocol: string;
    symbols: string[];
    transactionCount: number;
    inflowUsd: number;
    outflowUsd: number;
    netFlowUsd: number;
    realizedPnlUsd: number;
    gasUsd: number;
    lastTimestamp: number;
    status: "take_profit" | "loss" | "neutral";
    actions: Record<string, number>;
};

export type TPnLFlowEvent = {
    id: string;
    txId?: string;
    txHash?: string;
    timestamp: number;
    timeAgo?: string;
    action?: string;
    actionLabel?: string;
    direction?: "in" | "out" | null;
    symbol?: string;
    amount?: number;
    amountUsd?: number;
    recordedAmountUsd?: number;
    priceAtTx?: number | null;
    priceSource?: string | null;
    priceTimestamp?: number | null;
    priceDeltaSeconds?: number | null;
    priceMaxDeltaSeconds?: number | null;
    priceReliable?: boolean | null;
    priceNote?: string | null;
    gasCostUsd?: number;
    explorerUrl?: string | null;
    description: string;
};

export type TPnLFlow = {
    flowKey: string;
    positionId?: string | null;
    marketId?: string | null;
    poolId?: string | null;
    protocol: string;
    label: string;
    type: "lending" | "lp" | "borrow";
    side?: string | null;
    symbols: string[];
    currentValueUsd: number;
    inflowUsd: number;
    outflowUsd: number;
    netCashflowUsd: number;
    gasUsd: number;
    estimatedPnlUsd: number;
    estimatedPnlPct: number | null;
    pnlReliable?: boolean;
    pnlNote?: string | null;
    capitalBaseUsd?: number;
    actions?: Record<string, number>;
    transactionCount: number;
    firstTimestamp?: number | null;
    lastTimestamp?: number | null;
    status: "open" | "closed" | "snapshot_only";
    marketLinkSymbol?: string;
    events: TPnLFlowEvent[];
    formula?: string;
};

export type TAlert = {
    id: string;
    level: "danger" | "warning" | "info" | "success";
    title: string;
    message: string;
};

export type TPortfolioAnalytics = {
    netWorth: TNetWorth;
    pnlSummary: TPnLSummary;
    positionsPnL: TPositionPnL[];
    transactions: TTransaction[];
    transactionPoolGroups?: TTransactionPoolGroup[];
    pnlFlows?: TPnLFlow[];
    chartHistory: TChartPoint[];
};

export type TPriceTrend = {
    symbol?: string | null;
    currentPrice: number;
    change_7d_pct: number;
    change_30d_pct: number;
    volatility_30d_pct: number;
    maxDrawdown_30d_pct: number;
    forecast_1d_pct?: number;
    forecast_7d_pct?: number;
    trend?: "UP" | "DOWN" | "FLAT" | "UNKNOWN";
    confidence?: number;
    sampleSize: number;
};

export type TPositionRisk = {
    positionId?: string;
    protocol?: string;
    type: "lending" | "lp";
    side?: string;
    symbol?: string;
    token0?: string;
    token1?: string;
    valueUsd: number;
    riskScore: number;
    riskLevel: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
    healthFactor?: number;
    liquidationThreshold?: number;
    liquidationBufferUsd?: number;
    priceMoveToLiquidationPct?: number | null;
    forecastLiquidationRiskPct?: number;
    impermanentLossUsd?: number;
    impermanentLossPct?: number;
    forecastImpermanentLossUsd?: number;
    forecastImpermanentLossPct?: number;
    holdValueUsd?: number;
    collectedFeeUsd?: number;
    range?: {
        inRange: boolean | null;
        currentTick: number | null;
        tickLower: number | null;
        tickUpper: number | null;
        rangeWidthTicks?: number;
        distanceToRangeEdgePct: number | null;
        forecastTick7d?: number | null;
        forecastOutOfRange?: boolean | null;
    };
    priceTrend: TPriceTrend | Record<string, TPriceTrend>;
    signals: string[];
    history: { timestamp: number; valueUsd: number; pnlUsd: number }[];
};

export type TPortfolioRisk = {
    wallet: string;
    timestamp: number;
    portfolio: {
        netWorthUsd: number;
        totalRiskValueUsd: number;
        highRiskValueUsd: number;
        highRiskRatio: number;
        riskScore: number;
        riskLevel: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
        positionCount: number;
    };
    positions: TPositionRisk[];
};
