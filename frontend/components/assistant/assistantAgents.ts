import {TokenPriceHistory} from "@/services/token.api";
import {SimulationPayload} from "@/services/simulation.api";
import {TPortfolioAnalytics, TPortfolioData, TPortfolioRisk} from "@/types/portfolio";
import {formatMoney, formatPercent} from "@/utils/format";

export type AssistantPage = "dashboard" | "markets" | "risk-engine" | "simulator";

export type AssistantAction = {
    label: string;
    href: string;
    primary?: boolean;
};

export type AssistantReply = {
    agent: "Dashboard Agent" | "Market Agent" | "Risk Engine Agent" | "Simulator Agent";
    page: AssistantPage;
    href: string;
    message: string;
    actions: AssistantAction[];
};

export type AssistantContext = {
    pathname: string;
    wallet?: string;
    portfolio?: TPortfolioData;
    analytics?: TPortfolioAnalytics;
    risk?: TPortfolioRisk;
    markets: AssistantMarket[];
    fetchTokenHistory: (symbol: string) => Promise<TokenPriceHistory | null>;
    parseSimulationIntent: (text: string) => Promise<ParsedIntentPayload | null>;
};

export type AssistantMarket = {
    market_id?: string;
    protocol?: string;
    category?: string;
    symbol?: string;
    apr?: number;
    tvl_usd?: number;
    ahpMatchIndex?: number;
    tier?: string;
    flags?: string[];
    raw_data?: MarketRawData;
};

type MarketRawData = {
    type?: string;
    dex?: string;
    asset?: string;
    symbol?: string;
    protocol?: string;
    tvl?: number;
    tvl_usd?: number;
    totalDepositUsd?: number;
    total_apr?: number;
    pool_apr?: number;
    supplyApr?: number;
    token0?: { symbol?: string };
    token1?: { symbol?: string };
    [key: string]: unknown;
};

type ParsedIntentPayload = {
    type?: string;
    symbol?: string;
    fromSymbol?: string;
    toSymbol?: string;
    collateralSymbol?: string;
    borrowSymbol?: string;
    token0?: string;
    token1?: string;
    amount?: unknown;
    amount0?: unknown;
    amount1?: unknown;
    loops?: unknown;
    targetLtv?: unknown;
    shockPct?: unknown;
    confidence?: unknown;
    shocks?: Record<string, unknown>;
};

type SimulatorIntent = {
    type: "buy" | "swap" | "lend" | "stake" | "borrow" | "provide_liquidity" | "price_shock" | "unknown";
    symbol?: string;
    fromSymbol?: string;
    toSymbol?: string;
    amount?: number;
    token0?: string;
    token1?: string;
    amount0?: number;
    amount1?: number;
    shockPct?: number;
    marketId?: string;
    confidence?: number;
};

const DEFAULT_SYMBOLS = [
    "ETH",
    "WETH",
    "BTC",
    "WBTC",
    "USDC",
    "USDT",
    "DAI",
    "LINK",
    "AAVE",
    "UNI",
    "CRV",
    "CBETH",
    "RETH",
];

const PAGE_HREF: Record<AssistantPage, string> = {
    dashboard: "/dashboard",
    markets: "/markets",
    "risk-engine": "/risk-engine",
    simulator: "/simulator",
};

export async function runInvestorAssistant(text: string, context: AssistantContext): Promise<AssistantReply> {
    const page = classifyPage(text, context.pathname);

    if (page === "simulator") {
        return runSimulatorAgent(text, context);
    }
    if (page === "risk-engine") {
        return runRiskAgent(text, context);
    }
    if (page === "markets") {
        return runMarketAgent(text, context);
    }

    return runDashboardAgent(context);
}

function classifyPage(text: string, pathname: string): AssistantPage {
    const normalized = normalizeText(text);

    const hasPercentShock = /(?:giam|tang|drop|fall|increase|up|down|shock|stress).*\d+(?:\.\d+)?\s*%/.test(normalized);
    if (
        hasPercentShock ||
        hasAny(normalized, [
            "mua",
            "buy",
            "ban",
            "sell",
            "swap",
            "doi",
            "hoan doi",
            "lend",
            "supply",
            "deposit",
            "stake",
            "staking",
            "gui",
            "vay",
            "borrow",
            "lp",
            "liquidity",
            "thanh khoan",
            "simulate",
            "simulation",
            "mo phong",
            "action",
            "hanh dong",
        ])
    ) {
        return "simulator";
    }

    if (
        hasAny(normalized, [
            "risk",
            "rui ro",
            "liquidation",
            "thanh ly",
            "health",
            "buffer",
            "impermanent",
            "il",
            "range",
            "an toan",
        ])
    ) {
        return "risk-engine";
    }

    if (
        hasAny(normalized, [
            "market",
            "markets",
            "gia",
            "price",
            "apr",
            "apy",
            "yield",
            "tvl",
            "pool",
            "protocol",
            "thi truong",
            "hien tai",
        ])
    ) {
        return "markets";
    }

    if (
        hasAny(normalized, [
            "dashboard",
            "portfolio",
            "tong quan",
            "vi",
            "tai san",
            "net worth",
            "pnl",
            "lai lo",
            "allocation",
            "giao dich",
        ])
    ) {
        return "dashboard";
    }

    if (pathname.startsWith("/markets")) return "markets";
    if (pathname.startsWith("/risk-engine")) return "risk-engine";
    if (pathname.startsWith("/simulator")) return "simulator";
    return "dashboard";
}

function runDashboardAgent(context: AssistantContext): AssistantReply {
    const summary = context.portfolio?.summary;
    const netWorth = context.analytics?.netWorth;
    const pnl = context.analytics?.pnlSummary;
    const positions = context.analytics?.positionsPnL ?? [];
    const transactions = context.analytics?.transactions ?? [];
    const allocations = context.portfolio?.allocations ?? [];
    const largestAllocation = [...allocations].sort((a, b) => b.valueUsd - a.valueUsd)[0];
    const topPosition = [...positions].sort((a, b) => b.valueUsd - a.valueUsd)[0];

    if (!summary && !netWorth) {
        const href = withAgentFocus(PAGE_HREF.dashboard, "dashboard:status", "Dashboard sync status");
        return {
            agent: "Dashboard Agent",
            page: "dashboard",
            href,
            message: "Dashboard Agent does not have a portfolio snapshot yet. I will take you to Dashboard so you can check the wallet sync status.",
            actions: [{label: "Open Dashboard", href, primary: true}],
        };
    }

    const positionUsd = ((netWorth?.lendingUsd ?? 0) + (netWorth?.farmingUsd ?? 0)) || (summary?.totalSupplyUsd ?? 0);
    const lines = [
        `Portfolio overview ${context.wallet ? shortWallet(context.wallet) : ""}`,
        `Net worth: ${formatMoney(netWorth?.totalUsd ?? summary?.netWorthUsd ?? 0)}.`,
        `Wallet tokens: ${formatMoney(netWorth?.tokenHoldUsd ?? summary?.totalWalletUsd ?? 0)} | Positions: ${formatMoney(positionUsd)} | Debt: ${formatMoney(netWorth?.debtUsd ?? summary?.totalBorrowUsd ?? 0)}.`,
    ];

    if (pnl) {
        lines.push(`PnL 7D: ${formatMoney(pnl.sevenDayUsd)} (${formatPercent(pnl.sevenDayPct)}), all-time: ${formatMoney(pnl.allTimeUsd)} (${formatPercent(pnl.allTimePct)}).`);
    }
    if (largestAllocation) {
        lines.push(`Largest allocation: ${largestAllocation.purpose} at ${largestAllocation.percentage.toFixed(1)}% (${formatMoney(largestAllocation.valueUsd)}).`);
    }
    if (topPosition) {
        lines.push(`Largest position: ${topPosition.name} on ${topPosition.protocol}, value ${formatMoney(topPosition.valueUsd)}, PnL ${formatMoney(topPosition.pnlUsd)}.`);
    }
    if (transactions.length) {
        lines.push(`Latest activity: ${transactions[0].actionLabel || transactions[0].action || "Activity"} ${transactions[0].symbol ? `${transactions[0].symbol} ` : ""}${formatMoney(transactions[0].amountUsd || 0)}.`);
    }

    const href = withAgentFocus(PAGE_HREF.dashboard, "dashboard:overview", "Portfolio overview");
    return {
        agent: "Dashboard Agent",
        page: "dashboard",
        href,
        message: lines.join("\n"),
        actions: [
            {label: "Open Dashboard", href, primary: true},
            {label: "Review Risk", href: withAgentFocus(PAGE_HREF["risk-engine"], "risk:portfolio", "Portfolio risk")},
        ],
    };
}

async function runMarketAgent(text: string, context: AssistantContext): Promise<AssistantReply> {
    const symbol = extractSymbol(text, context.markets, context.portfolio);
    const href = symbol
        ? withAgentFocus(`/markets?symbol=${encodeURIComponent(symbol)}`, `token:${symbol}`, `${symbol} token data`)
        : withAgentFocus(PAGE_HREF.markets, "market:overview", "Market overview");

    if (symbol) {
        const pools = marketsForSymbol(context.markets, symbol);
        const bestPool = [...pools].sort((a, b) => Number(b.apr || 0) - Number(a.apr || 0))[0];
        const totalTvl = pools.reduce((sum, pool) => sum + Number(pool.tvl_usd || pool.raw_data?.tvl || pool.raw_data?.totalDepositUsd || 0), 0);
        const protocols = unique(pools.map((pool) => pool.protocol || pool.raw_data?.protocol || pool.raw_data?.dex).filter(Boolean).map(String));
        const history = await context.fetchTokenHistory(symbol);

        const lines = [`Market Agent is looking at ${symbol}.`];
        if (history?.currentPrice) {
            lines.push(`Current price: ${formatMoney(history.currentPrice)}. 7D ${formatPercent(history.change7dPct)}, 30D ${formatPercent(history.change30dPct)}.`);
            lines.push(`30D range: ${formatMoney(history.low)} - ${formatMoney(history.high)}.`);
        } else {
            lines.push("Token price history is not available from the API yet, so I will route you to Markets where the live chart can load directly.");
        }
        if (pools.length) {
            lines.push(`Found ${pools.length} related market/pool entries with total TVL ${formatMoney(totalTvl)}${protocols.length ? ` across ${protocols.slice(0, 3).join(", ")}` : ""}.`);
        }
        if (bestPool) {
            lines.push(`Best APR currently visible: ${Number(bestPool.apr || 0).toFixed(2)}% at ${bestPool.protocol || bestPool.raw_data?.protocol || "market"}${bestPool.tier ? `, tier ${bestPool.tier}` : ""}.`);
        }

        return {
            agent: "Market Agent",
            page: "markets",
            href,
            message: lines.join("\n"),
            actions: [
                {label: `Open ${symbol}`, href, primary: true},
                ...(bestPool?.market_id ? [{
                    label: "Open Best Pool",
                    href: withAgentFocus(`/markets?marketId=${encodeURIComponent(bestPool.market_id)}`, `pool:${bestPool.market_id}`, `${bestPool.symbol || symbol} pool`),
                }] : []),
                {label: `Simulate Buy`, href: simulatorHref({type: "buy", symbol, fromSymbol: "USDC", amount: 1})},
                {label: `Simulate Lend`, href: simulatorHref(withBestMarket({type: "lend", symbol, amount: 1}, context.markets))},
            ],
        };
    }

    const pools = context.markets ?? [];
    const globalTvl = pools.reduce((sum, pool) => sum + Number(pool.tvl_usd || pool.raw_data?.tvl || pool.raw_data?.totalDepositUsd || 0), 0);
    const topApr = pools.length ? Math.max(...pools.map((pool) => Number(pool.apr || 0))) : 0;
    const topPools = [...pools]
        .sort((a, b) => Number(b.ahpMatchIndex || b.apr || 0) - Number(a.ahpMatchIndex || a.apr || 0))
        .slice(0, 3);

    const lines = [
        `Market Agent sees ${pools.length} opportunities with total TVL ${formatMoney(globalTvl)}.`,
        `Current top APR: ${topApr.toFixed(2)}%.`,
    ];
    if (topPools.length) {
        lines.push(`Top scoring entries: ${topPools.map((pool) => `${pool.symbol || pool.raw_data?.asset || "UNKNOWN"} ${Number(pool.apr || 0).toFixed(2)}%`).join("; ")}.`);
    }

    return {
        agent: "Market Agent",
        page: "markets",
        href: withAgentFocus(PAGE_HREF.markets, "market:overview", "Market overview"),
        message: lines.join("\n"),
        actions: [{label: "Open Markets", href: withAgentFocus(PAGE_HREF.markets, "market:overview", "Market overview"), primary: true}],
    };
}

function runRiskAgent(text: string, context: AssistantContext): AssistantReply {
    const symbol = extractSymbol(text, context.markets, context.portfolio);
    const portfolio = context.risk?.portfolio;
    const positions = context.risk?.positions ?? [];
    const matchedPositions = symbol
        ? positions.filter((position) => riskSymbols(position).includes(symbol))
        : positions;
    const topRisks = [...matchedPositions].sort((a, b) => Number(b.riskScore || 0) - Number(a.riskScore || 0)).slice(0, 3);

    if (!portfolio) {
        const href = withAgentFocus(PAGE_HREF["risk-engine"], "risk:portfolio", "Portfolio risk");
        return {
            agent: "Risk Engine Agent",
            page: "risk-engine",
            href,
            message: "Risk Engine Agent does not have a risk snapshot yet. I will take you to Risk Engine so you can check the data status.",
            actions: [{label: "Open Risk", href, primary: true}],
        };
    }

    const lines = [
        `Risk Engine Agent reads portfolio risk as ${portfolio.riskLevel} (${portfolio.riskScore.toFixed(1)}/100).`,
        `High-risk value: ${formatMoney(portfolio.highRiskValueUsd)} out of total risk value ${formatMoney(portfolio.totalRiskValueUsd)} (${portfolio.highRiskRatio.toFixed(1)}%).`,
        `Tracked positions: ${portfolio.positionCount}.`,
    ];

    if (symbol) {
        lines.push(matchedPositions.length ? `Filtered by ${symbol}: ${matchedPositions.length} related position(s).` : `No direct position risk found for ${symbol}.`);
    }
    if (topRisks.length) {
        lines.push(`Watch list: ${topRisks.map((position) => `${position.symbol || `${position.token0}/${position.token1}`} ${position.riskLevel} ${position.riskScore.toFixed(1)}`).join("; ")}.`);
        const firstSignal = topRisks.flatMap((position) => position.signals || [])[0];
        if (firstSignal) lines.push(`Key signal: ${firstSignal}.`);
    }

    const href = withAgentFocus(PAGE_HREF["risk-engine"], symbol ? `risk:token:${symbol}` : "risk:portfolio", symbol ? `${symbol} risk` : "Portfolio risk");
    return {
        agent: "Risk Engine Agent",
        page: "risk-engine",
        href,
        message: lines.join("\n"),
        actions: [
            {label: "Open Risk", href, primary: true},
            ...(symbol ? [{label: `Open ${symbol} Market`, href: withAgentFocus(`/markets?symbol=${encodeURIComponent(symbol)}`, `token:${symbol}`, `${symbol} token data`)}] : []),
        ],
    };
}

async function runSimulatorAgent(text: string, context: AssistantContext): Promise<AssistantReply> {
    const parsed = await context.parseSimulationIntent(text);
    const intent = withBestMarket(normalizeSimulatorIntent(text, parsed, context), context.markets);
    const href = simulatorHref(intent);
    const payload = payloadPreview(intent);
    const symbol = intent.symbol || intent.toSymbol || intent.token0 || "ETH";

    const lines = [
        `Simulator Agent converted the request into ${simulationLabel(intent)}.`,
        payload ? `Draft payload: ${payload}.` : "This request does not have enough information to build a complete payload yet.",
        "This is a simulation only and will not submit an on-chain transaction.",
    ];

    return {
        agent: "Simulator Agent",
        page: "simulator",
        href,
        message: lines.join("\n"),
        actions: [
            {label: "Open Simulator", href, primary: true},
            {label: `Open ${symbol} Market`, href: withAgentFocus(`/markets?symbol=${encodeURIComponent(symbol)}`, `token:${symbol}`, `${symbol} token data`)},
        ],
    };
}

function normalizeSimulatorIntent(text: string, parsed: ParsedIntentPayload | null, context: AssistantContext): SimulatorIntent {
    const local = parseLocalSimulatorIntent(text, context);
    if (!parsed || parsed.type === "unknown") return local;

    const parsedType = String(parsed.type || "unknown") as SimulatorIntent["type"];
    const wantsBuy = hasAny(normalizeText(text), ["mua", "buy"]);

    if ((parsedType === "swap" || parsedType === "buy") && wantsBuy) {
        return {
            ...local,
            type: "buy",
            symbol: normalizeSymbol(parsed.toSymbol || local.symbol || local.toSymbol || extractSymbol(text, context.markets, context.portfolio) || "ETH"),
            fromSymbol: normalizeSymbol(parsed.fromSymbol || local.fromSymbol || "USDC"),
            amount: positiveNumber(parsed.amount) ?? local.amount ?? 1,
            confidence: positiveNumber(parsed.confidence) ?? local.confidence,
        };
    }

    if (parsedType === "swap") {
        return {
            type: "swap",
            fromSymbol: normalizeSymbol(parsed.fromSymbol || local.fromSymbol || "ETH"),
            toSymbol: normalizeSymbol(parsed.toSymbol || local.toSymbol || "USDC"),
            amount: positiveNumber(parsed.amount) ?? local.amount ?? 1,
            confidence: positiveNumber(parsed.confidence) ?? local.confidence,
        };
    }

    if (parsedType === "lend" || parsedType === "stake" || parsedType === "borrow") {
        return {
            type: parsedType,
            symbol: normalizeSymbol(parsed.symbol || local.symbol || (parsedType === "borrow" ? "USDC" : "ETH")),
            amount: positiveNumber(parsed.amount) ?? local.amount ?? (parsedType === "borrow" ? 100 : 1),
            shockPct: signedNumber(parsed.shockPct) ?? local.shockPct,
            confidence: positiveNumber(parsed.confidence) ?? local.confidence,
        };
    }

    if (parsedType === "provide_liquidity") {
        return {
            type: "provide_liquidity",
            token0: normalizeSymbol(parsed.token0 || local.token0 || local.symbol || "ETH"),
            token1: normalizeSymbol(parsed.token1 || local.token1 || local.toSymbol || "USDC"),
            amount0: positiveNumber(parsed.amount0) ?? local.amount0 ?? local.amount ?? 1,
            amount1: positiveNumber(parsed.amount1) ?? local.amount1,
            shockPct: signedNumber(parsed.shockPct) ?? local.shockPct ?? -20,
            confidence: positiveNumber(parsed.confidence) ?? local.confidence,
        };
    }

    if (parsedType === "price_shock" && parsed.shocks) {
        const [shockSymbol, shockPct] = Object.entries(parsed.shocks)[0] || [];
        return {
            type: "price_shock",
            symbol: normalizeSymbol(String(shockSymbol || local.symbol || "ETH")),
            shockPct: signedNumber(shockPct) ?? local.shockPct ?? -20,
            confidence: positiveNumber(parsed.confidence) ?? local.confidence,
        };
    }

    return local;
}

function parseLocalSimulatorIntent(text: string, context: AssistantContext): SimulatorIntent {
    const normalized = normalizeText(text);
    const symbol = extractSymbol(text, context.markets, context.portfolio) || "ETH";
    const amount = extractAmountNearSymbol(text, symbol) ?? extractFirstNumber(text);
    const pair = extractPair(text);
    const fundingSymbol = extractFundingSymbol(text, context) || "USDC";
    const shockPct = extractShockPct(text);

    if (hasAny(normalized, ["mua", "buy"])) {
        return {type: "buy", symbol, fromSymbol: fundingSymbol, amount: amount ?? 1, confidence: 0.78};
    }
    if (hasAny(normalized, ["sell", "ban", "swap", "doi", "hoan doi"])) {
        const target = extractTargetSymbol(text, context) || (symbol === "USDC" ? "ETH" : "USDC");
        return {type: "swap", fromSymbol: symbol, toSymbol: target, amount: amount ?? 1, confidence: 0.74};
    }
    if (hasAny(normalized, ["borrow", "vay"])) {
        return {type: "borrow", symbol, amount: amount ?? 100, shockPct: shockPct ?? -20, confidence: 0.72};
    }
    if (hasAny(normalized, ["lp", "liquidity", "thanh khoan", "provide liquidity", "add liquidity"])) {
        return {
            type: "provide_liquidity",
            token0: pair?.[0] || symbol,
            token1: pair?.[1] || extractTargetSymbol(text, context) || "USDC",
            amount0: amount ?? 1,
            shockPct: shockPct ?? -20,
            confidence: 0.7,
        };
    }
    if (hasAny(normalized, ["lend", "supply", "deposit", "stake", "staking", "gui"])) {
        return {type: normalized.includes("stake") ? "stake" : "lend", symbol, amount: amount ?? 1, confidence: 0.7};
    }
    if (shockPct != null) {
        return {type: "price_shock", symbol, shockPct, confidence: 0.64};
    }

    return {type: "unknown", symbol, amount: amount ?? undefined, confidence: 0};
}

function simulatorHref(intent: SimulatorIntent): string {
    const params = new URLSearchParams();
    params.set("agent", "1");
    params.set("intentId", String(Date.now()));

    if (intent.type === "price_shock") {
        params.set("shockSymbol", intent.symbol || "ETH");
        params.set("shockPct", String(intent.shockPct ?? -20));
        params.set("agentFocus", `simulator:shock:${intent.symbol || "ETH"}`);
        params.set("focusLabel", `Price shock ${intent.symbol || "ETH"}`);
        return `/simulator?${params.toString()}`;
    }

    if (intent.type === "buy") {
        params.set("mode", "buy");
        params.set("symbol", intent.symbol || intent.toSymbol || "ETH");
        params.set("fundingSymbol", intent.fromSymbol || "USDC");
        params.set("amount", String(intent.amount ?? 1));
        params.set("slippagePct", "0.3");
    } else if (intent.type === "swap") {
        params.set("mode", "swap");
        params.set("symbol", intent.fromSymbol || intent.symbol || "ETH");
        params.set("toSymbol", intent.toSymbol || "USDC");
        params.set("amount", String(intent.amount ?? 1));
        params.set("slippagePct", "0.3");
    } else if (intent.type === "borrow") {
        params.set("mode", "borrow");
        params.set("symbol", intent.symbol || "USDC");
        params.set("amount", String(intent.amount ?? 100));
        params.set("shockPct", String(intent.shockPct ?? -20));
    } else if (intent.type === "provide_liquidity") {
        params.set("mode", "provide_liquidity");
        params.set("symbol", intent.token0 || intent.symbol || "ETH");
        params.set("toSymbol", intent.token1 || "USDC");
        params.set("amount", String(intent.amount0 ?? intent.amount ?? 1));
        if (intent.amount1) params.set("amount1", String(intent.amount1));
        params.set("shockPct", String(intent.shockPct ?? -20));
    } else {
        params.set("mode", intent.type === "stake" ? "lend" : "lend");
        params.set("symbol", intent.symbol || "ETH");
        params.set("amount", String(intent.amount ?? 1));
    }

    if (intent.marketId) params.set("marketId", intent.marketId);
    params.set("autoAdd", "1");
    params.set("agentFocus", simulatorFocusKey(intent));
    params.set("focusLabel", simulationLabel(intent));
    return `/simulator?${params.toString()}`;
}

function withAgentFocus(href: string, focusKey: string, focusLabel: string) {
    const [path, query = ""] = href.split("?");
    const params = new URLSearchParams(query);
    params.set("agentFocus", focusKey);
    params.set("focusLabel", focusLabel);
    return `${path}?${params.toString()}`;
}

function simulatorFocusKey(intent: SimulatorIntent) {
    if (intent.marketId) return `pool:${intent.marketId}`;
    if (intent.type === "buy") return `simulator:buy:${intent.symbol || intent.toSymbol || "ETH"}`;
    if (intent.type === "swap") return `simulator:swap:${intent.fromSymbol || intent.symbol || "ETH"}:${intent.toSymbol || "USDC"}`;
    if (intent.type === "borrow") return `simulator:borrow:${intent.symbol || "USDC"}`;
    if (intent.type === "provide_liquidity") return `simulator:lp:${intent.token0 || intent.symbol || "ETH"}:${intent.token1 || "USDC"}`;
    return `simulator:${intent.type}:${intent.symbol || "ETH"}`;
}

function withBestMarket(intent: SimulatorIntent, markets: AssistantMarket[]): SimulatorIntent {
    if (intent.marketId || !["lend", "stake", "borrow", "provide_liquidity"].includes(intent.type)) return intent;

    const symbols = intent.type === "provide_liquidity"
        ? [intent.token0, intent.token1].filter(Boolean).map(String)
        : [intent.symbol].filter(Boolean).map(String);

    const candidates = markets.filter((market) => {
        if (!market.market_id) return false;
        const marketSymbols = poolSymbols(market);
        const isLp = market.category === "dex_liquidity" || market.raw_data?.type === "dex_liquidity" || Boolean(market.raw_data?.dex);
        if (intent.type === "provide_liquidity" && !isLp) return false;
        if (intent.type !== "provide_liquidity" && isLp) return false;
        return symbols.every((symbol) => marketSymbols.includes(normalizeSymbol(symbol)));
    });

    const best = candidates.sort((a, b) => {
        const aScore = Number(a.ahpMatchIndex || 0) + Number(a.apr || 0) + Number(a.tvl_usd || 0) / 1_000_000_000;
        const bScore = Number(b.ahpMatchIndex || 0) + Number(b.apr || 0) + Number(b.tvl_usd || 0) / 1_000_000_000;
        return bScore - aScore;
    })[0];

    return best?.market_id ? {...intent, marketId: best.market_id} : intent;
}

function payloadPreview(intent: SimulatorIntent): string | null {
    const payload = intentToPayload(intent);
    if (!payload) return null;
    if (payload.type === "swap") return `${payload.amount} ${payload.fromSymbol} -> ${payload.toSymbol}`;
    if (payload.type === "lend" || payload.type === "stake") return `${payload.type} ${payload.amount} ${payload.symbol}${payload.marketId ? " via selected market" : ""}`;
    if (payload.type === "borrow") return `borrow ${payload.amount} ${payload.symbol}, shock ${payload.shockPct ?? 0}%`;
    if (payload.type === "provide_liquidity") return `LP ${payload.amount0} ${payload.token0}/${payload.token1}${payload.marketId ? " via selected market" : ""}`;
    if (payload.type === "price_shock") {
        const [symbol, pct] = Object.entries(payload.shocks)[0] || ["ETH", -20];
        return `shock ${symbol} ${pct}%`;
    }
    return null;
}

function intentToPayload(intent: SimulatorIntent): SimulationPayload | null {
    if (intent.type === "buy") {
        return {type: "swap", fromSymbol: intent.fromSymbol || "USDC", toSymbol: intent.symbol || intent.toSymbol || "ETH", amount: intent.amount ?? 1, slippagePct: 0.3};
    }
    if (intent.type === "swap") {
        return {type: "swap", fromSymbol: intent.fromSymbol || intent.symbol || "ETH", toSymbol: intent.toSymbol || "USDC", amount: intent.amount ?? 1, slippagePct: 0.3};
    }
    if (intent.type === "lend" || intent.type === "stake") {
        return {type: intent.type, symbol: intent.symbol || "ETH", amount: intent.amount ?? 1, marketId: intent.marketId};
    }
    if (intent.type === "borrow") {
        return {type: "borrow", symbol: intent.symbol || "USDC", amount: intent.amount ?? 100, marketId: intent.marketId, shockPct: intent.shockPct ?? -20};
    }
    if (intent.type === "provide_liquidity") {
        return {type: "provide_liquidity", token0: intent.token0 || intent.symbol || "ETH", token1: intent.token1 || "USDC", amount0: intent.amount0 ?? intent.amount ?? 1, amount1: intent.amount1, marketId: intent.marketId, shockPct: intent.shockPct ?? -20};
    }
    if (intent.type === "price_shock") {
        return {type: "price_shock", shocks: {[intent.symbol || "ETH"]: intent.shockPct ?? -20}};
    }
    return null;
}

function simulationLabel(intent: SimulatorIntent) {
    if (intent.type === "buy") return `Buy ${intent.symbol || intent.toSymbol || "ETH"}`;
    if (intent.type === "swap") return `Swap ${intent.fromSymbol || intent.symbol || "ETH"} to ${intent.toSymbol || "USDC"}`;
    if (intent.type === "lend" || intent.type === "stake") return `${intent.type === "stake" ? "Stake" : "Lend"} ${intent.symbol || "ETH"}`;
    if (intent.type === "borrow") return `Borrow ${intent.symbol || "USDC"}`;
    if (intent.type === "provide_liquidity") return `LP ${intent.token0 || "ETH"}/${intent.token1 || "USDC"}`;
    if (intent.type === "price_shock") return `Price shock ${intent.symbol || "ETH"}`;
    return "simulation draft";
}

function marketsForSymbol(markets: AssistantMarket[], symbol: string) {
    const normalized = normalizeSymbol(symbol);
    return markets.filter((market) => poolSymbols(market).includes(normalized));
}

function poolSymbols(market: AssistantMarket) {
    const raw = market.raw_data || {};
    const values = [
        raw.token0?.symbol,
        raw.token1?.symbol,
        raw.asset,
        raw.symbol,
        market.symbol,
    ].filter(Boolean).flatMap((value) => String(value).split(/[-/]/));

    return unique(values.map((value) => normalizeSymbol(value)).filter(Boolean));
}

function riskSymbols(position: TPortfolioRisk["positions"][number]) {
    return unique([
        position.symbol,
        position.token0,
        position.token1,
    ].filter(Boolean).flatMap((value) => String(value).split(/[-/]/)).map((value) => normalizeSymbol(value)));
}

function extractSymbol(text: string, markets: AssistantMarket[] = [], portfolio?: TPortfolioData) {
    const known = unique([
        ...DEFAULT_SYMBOLS,
        ...(portfolio?.assets ?? []).map((asset) => asset.symbol),
        ...markets.flatMap(poolSymbols),
    ].map((item) => normalizeSymbol(item)).filter(Boolean));

    const upper = text.toUpperCase();
    const match = known.find((symbol) => new RegExp(`(^|[^A-Z0-9])${escapeRegExp(symbol)}([^A-Z0-9]|$)`).test(upper));
    return match || null;
}

function extractTargetSymbol(text: string, context: AssistantContext) {
    const normalized = normalizeText(text);
    const targetMatch = normalized.match(/(?:to|for|into|sang|ra|lay|nhan)\s+([a-zA-Z][a-zA-Z0-9.]*)/);
    if (!targetMatch) return null;
    const raw = targetMatch[1].toUpperCase();
    const known = extractSymbol(raw, context.markets, context.portfolio);
    return known || normalizeSymbol(raw);
}

function extractFundingSymbol(text: string, context: AssistantContext) {
    const normalized = normalizeText(text);
    const fundingMatch = normalized.match(/(?:bang|with|using|pay with|dung)\s+([a-zA-Z][a-zA-Z0-9.]*)/);
    if (!fundingMatch) return null;
    const raw = fundingMatch[1].toUpperCase();
    const known = extractSymbol(raw, context.markets, context.portfolio);
    return known || normalizeSymbol(raw);
}

function extractPair(text: string): [string, string] | null {
    const match = text.toUpperCase().match(/\b([A-Z][A-Z0-9.]*)\s*[/-]\s*([A-Z][A-Z0-9.]*)\b/);
    return match ? [normalizeSymbol(match[1]), normalizeSymbol(match[2])] : null;
}

function extractAmountNearSymbol(text: string, symbol: string) {
    const escaped = escapeRegExp(symbol);
    const before = new RegExp(`(\\d+(?:\\.\\d+)?)\\s*${escaped}`, "i").exec(text);
    if (before) return positiveNumber(before[1]);
    const after = new RegExp(`${escaped}\\s*(\\d+(?:\\.\\d+)?)`, "i").exec(text);
    if (after) return positiveNumber(after[1]);
    return null;
}

function extractFirstNumber(text: string) {
    const match = text.match(/\d+(?:\.\d+)?/);
    return match ? positiveNumber(match[0]) : null;
}

function extractShockPct(text: string) {
    const match = text.match(/(giam|drop|fall|down|decrease|tang|up|rise|increase|shock|stress)[^\d-]*(-?\d+(?:\.\d+)?)\s*%/i)
        || text.match(/(-?\d+(?:\.\d+)?)\s*%/);
    if (!match) return null;
    const value = signedNumber(match[2] ?? match[1]);
    const direction = normalizeText(match[1] ?? "");
    if (value == null) return null;
    return hasAny(direction, ["giam", "drop", "fall", "down", "decrease"]) ? -Math.abs(value) : value;
}

function normalizeText(text: string) {
    return text
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/đ/g, "d");
}

function normalizeSymbol(symbol: string) {
    return String(symbol || "").trim().toUpperCase();
}

function hasAny(text: string, keywords: string[]) {
    return keywords.some((keyword) => text.includes(keyword));
}

function unique<T>(items: T[]) {
    return [...new Set(items)];
}

function positiveNumber(value: unknown) {
    const number = Number(value);
    return Number.isFinite(number) && number > 0 ? number : null;
}

function signedNumber(value: unknown) {
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
}

function escapeRegExp(value: string) {
    return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function shortWallet(wallet: string) {
    return `${wallet.slice(0, 6)}...${wallet.slice(-4)}`;
}
