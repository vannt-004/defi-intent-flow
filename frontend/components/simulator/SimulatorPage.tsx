"use client";

import {useCallback, useEffect, useMemo, useRef, useState} from "react";
import {useSearchParams} from "next/navigation";
import {
    AlertTriangle,
    ArrowDownUp,
    ArrowRightLeft,
    CheckCircle2,
    Layers,
    ListPlus,
    Minus,
    Percent,
    Play,
    Plus,
    Trash2,
    Wallet
} from "lucide-react";

import Div from "@/components/ui/Div";
import Skeleton from "@/components/common/Skeleton";
import {useAgentFocus} from "@/components/assistant/AgentFocusContext";
import {useWallet} from "@/hooks/useWallet";
import {useMarketQuery} from "@/hooks/useMarket";
import {usePortfolioQuery} from "@/hooks/usePortfolioQuery";
import {simulateWallet, SimulationPayload, SimulationResult} from "@/services/simulation.api";
import {cn} from "@/utils/cn";
import {formatMoney} from "@/utils/format";
import {ui} from "@/styles/ui";
import Select from "@/components/ui/Select";
import {TAsset} from "@/types/portfolio";

type Mode = "buy" | "lend" | "borrow" | "swap" | "provide_liquidity";

type MarketOption = {
    market_id?: string;
    protocol?: string;
    category?: string;
    symbol?: string;
    apr?: number;
    tvl_usd?: number;
    raw_data?: {
        type?: string;
        dex?: string;
        asset?: string;
        symbol?: string;
        protocol?: string;
        total_apr?: number;
        pool_apr?: number;
        supplyApr?: number;
        borrowApr?: number;
        borrowStableApr?: number;
        maxLtv?: number;
        maximumLTV?: number;
        liquidationThreshold?: number;
        tvl?: number;
        tvl_usd?: number;
        totalDepositUsd?: number;
        token0?: { symbol?: string };
        token1?: { symbol?: string };
    };
};

type ScenarioAction = {
    id: string;
    mode: Mode;
    title: string;
    summary: string;
    payload: SimulationPayload;
};

const MODE_META = {
    buy: {label: "Buy Token", icon: <ArrowRightLeft size={14}/>, hint: "Buy ETH using USDC before lending or LP"},
    lend: {label: "Lend", icon: <Wallet size={14}/>, hint: "Supply 1 ETH to lending"},
    borrow: {label: "Borrow", icon: <ArrowDownUp size={14}/>, hint: "Borrow USDC from Aave"},
    swap: {label: "Swap", icon: <ArrowRightLeft size={14}/>, hint: "Swap 0.5 ETH to USDC"},
    provide_liquidity: {label: "LP", icon: <Layers size={14}/>, hint: "Add ETH/USDC liquidity"},
};

export default function SimulatorPage() {
    const searchParams = useSearchParams();
    const {focusClass} = useAgentFocus();
    const {address} = useWallet();
    const {data: markets = [], isLoading: isLoadingMarkets} = useMarketQuery();
    const {data: portfolio, isPending: isPortfolioLoading} = usePortfolioQuery(address);
    const [mode, setMode] = useState<Mode>("lend");
    const [symbol, setSymbol] = useState("ETH");
    const [environmentSymbol, setEnvironmentSymbol] = useState("ETH");
    const [environmentShockPct, setEnvironmentShockPct] = useState(-20);
    const [amount, setAmount] = useState(1);
    const [toSymbol, setToSymbol] = useState("USDC");
    const [fundingSymbol, setFundingSymbol] = useState("USDC");
    const [slippagePct, setSlippagePct] = useState(0.3);
    const [amount1, setAmount1] = useState(0);
    const [selectedMarketId, setSelectedMarketId] = useState("");
    const [result, setResult] = useState<SimulationResult | null>(null);
    const [isRunning, setIsRunning] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [actions, setActions] = useState<ScenarioAction[]>([]);
    const [selectedActionId, setSelectedActionId] = useState<string | null>(null);
    const appliedAgentIntentRef = useRef<string | null>(null);

    const marketOptions = useMemo(() => {
        const rows = (markets as MarketOption[]) || [];
        if (mode === "provide_liquidity") {
            return rows.filter((market) => market.category === "dex_liquidity" || market.raw_data?.type === "dex_liquidity" || market.raw_data?.dex);
        }
        if (mode === "lend" || mode === "borrow") {
            return rows.filter((market) => market.category !== "dex_liquidity" && market.raw_data?.type !== "dex_liquidity");
        }
        return rows;
    }, [markets, mode]);

    const assets = useMemo<TAsset[]>(() => portfolio?.assets || [], [portfolio?.assets]);

    const assetBySymbol = useMemo(() => {
        return new Map(assets.map((asset) => [asset.symbol.toUpperCase(), asset]));
    }, [assets]);

    const tokenOptions = useMemo(() => {
        const symbols = new Set<string>();
        assets.forEach((asset) => symbols.add(asset.symbol.toUpperCase()));
        (markets as MarketOption[]).forEach((market) => {
            const raw = market.raw_data || {};
            const symbolValue = raw.asset || raw.symbol || market.symbol;
            const token0 = raw.token0?.symbol;
            const token1 = raw.token1?.symbol;
            if (symbolValue) String(symbolValue).split(/[-/]/).forEach((item) => item && symbols.add(item.toUpperCase()));
            if (token0) symbols.add(String(token0).toUpperCase());
            if (token1) symbols.add(String(token1).toUpperCase());
        });
        ["ETH", "WETH", "WBTC", "USDC", "USDT"].forEach((item) => symbols.add(item));
        return [...symbols].sort().map((item) => ({label: item, value: item}));
    }, [assets, markets]);

    const selectedMarket = useMemo(() => {
        return marketOptions.find((market) => market.market_id === selectedMarketId) || null;
    }, [marketOptions, selectedMarketId]);

    const tokenPrice = useCallback((tokenSymbol: string) => {
        const normalized = tokenSymbol.toUpperCase();
        const direct = assetBySymbol.get(normalized)?.price;
        if (direct && direct > 0) return direct;
        if (normalized === "ETH") return assetBySymbol.get("WETH")?.price || 0;
        if (normalized === "WETH") return assetBySymbol.get("ETH")?.price || 0;
        if (["USDC", "USDT", "DAI"].includes(normalized)) return 1;
        return 0;
    }, [assetBySymbol]);

    const simulatedBalances = useMemo(() => {
        const balances = new Map<string, number>();
        assets.forEach((asset) => balances.set(asset.symbol.toUpperCase(), Number(asset.balance || 0)));

        const addBalance = (tokenSymbol: string, delta: number) => {
            const normalized = tokenSymbol.toUpperCase();
            balances.set(normalized, Math.max((balances.get(normalized) || 0) + delta, 0));
        };

        actions.forEach((action) => {
            const payload = action.payload;
            if (payload.type === "lend" || payload.type === "stake") {
                addBalance(payload.symbol, -payload.amount);
                return;
            }
            if (payload.type === "swap") {
                const fromPrice = tokenPrice(payload.fromSymbol);
                const toPrice = tokenPrice(payload.toSymbol);
                const feeMultiplier = Math.max(1 - Number(payload.slippagePct || 0) / 100, 0);
                addBalance(payload.fromSymbol, -payload.amount);
                if (fromPrice > 0 && toPrice > 0) {
                    addBalance(payload.toSymbol, payload.amount * fromPrice * feeMultiplier / toPrice);
                }
                return;
            }
            if (payload.type === "provide_liquidity") {
                addBalance(payload.token0, -payload.amount0);
                if (payload.amount1) addBalance(payload.token1, -payload.amount1);
            }
        });

        return balances;
    }, [actions, assets, tokenPrice]);

    const simulatedAssets = useMemo(() => {
        const symbols = new Set<string>([...assets.map((asset) => asset.symbol.toUpperCase()), ...simulatedBalances.keys()]);
        return [...symbols].sort().map((tokenSymbol) => {
            const base = assetBySymbol.get(tokenSymbol);
            const balance = simulatedBalances.get(tokenSymbol) || 0;
            const price = tokenPrice(tokenSymbol);
            return {
                symbol: tokenSymbol,
                balance,
                originalBalance: base?.balance || 0,
                valueUsd: balance * price,
            };
        });
    }, [assetBySymbol, assets, simulatedBalances, tokenPrice]);

    const marketLabel = (market: MarketOption) => {
        const raw = market.raw_data || {};
        const apr = Number(market.apr ?? raw.total_apr ?? raw.pool_apr ?? raw.supplyApr ?? 0);
        const tvl = Number(market.tvl_usd ?? raw.tvl ?? raw.tvl_usd ?? raw.totalDepositUsd ?? 0);
        return `${market.protocol || raw.protocol || raw.dex || "Market"} · ${market.symbol || raw.asset || raw.symbol || "UNKNOWN"} · APR ${apr.toFixed(2)}% · TVL ${formatMoney(tvl)}`;
    };

    const applyMarket = (marketId: string) => {
        setSelectedMarketId(marketId);
        const market = marketOptions.find((item) => item.market_id === marketId);
        const raw = market?.raw_data || {};
        if (!market) return;

        if (mode === "provide_liquidity") {
            const token0 = raw.token0?.symbol || String(market.symbol || "ETH-USDC").split(/[-/]/)[0];
            const token1 = raw.token1?.symbol || String(market.symbol || "ETH-USDC").split(/[-/]/)[1] || "USDC";
            setSymbol(String(token0).toUpperCase());
            setToSymbol(String(token1).toUpperCase());
            return;
        }

        const asset = raw.asset || raw.symbol || market.symbol || "ETH";
        setSymbol(String(asset).toUpperCase());
    };

    const buildPayload = (): SimulationPayload => {
        const marketId = selectedMarketId || undefined;
        if (mode === "buy") {
            return {type: "swap", fromSymbol: fundingSymbol.toUpperCase(), toSymbol: symbol.toUpperCase(), amount, slippagePct};
        }
        if (mode === "lend") {
            return {type: "lend", symbol: symbol.toUpperCase(), amount, marketId};
        }
        if (mode === "borrow") {
            return {type: "borrow", symbol: symbol.toUpperCase(), amount, marketId, shockPct: environmentShockPct};
        }
        if (mode === "swap") {
            return {type: "swap", fromSymbol: symbol.toUpperCase(), toSymbol: toSymbol.toUpperCase(), amount, slippagePct};
        }
        return {
            type: "provide_liquidity",
            token0: symbol.toUpperCase(),
            token1: toSymbol.toUpperCase(),
            amount0: amount,
            amount1: amount1 > 0 ? amount1 : undefined,
            marketId,
            shockPct: environmentShockPct,
        };
    };

    const applyEnvironmentToPayload = (payload: SimulationPayload): SimulationPayload => {
        if (payload.type === "borrow" || payload.type === "provide_liquidity") {
            return {...payload, shockPct: environmentShockPct};
        }
        return payload;
    };

    const describePayload = useCallback((payload: SimulationPayload) => {
        if (payload.type === "price_shock") {
            const [shockSymbol, pct] = Object.entries(payload.shocks)[0] || ["TOKEN", 0];
            return {
                title: `Shock ${shockSymbol}`,
                summary: `${Number(pct) >= 0 ? "+" : ""}${Number(pct).toFixed(2)}% price move`,
            };
        }
        if (payload.type === "lend" || payload.type === "stake") {
            return {
                title: `${payload.type === "stake" ? "Stake" : "Lend"} ${payload.symbol}`,
                summary: `${formatAmount(payload.amount)} ${payload.symbol}${payload.marketId ? " via selected market" : ""}`,
            };
        }
        if (payload.type === "borrow") {
            return {
                title: `Borrow ${payload.symbol}`,
                summary: `${formatAmount(payload.amount)} ${payload.symbol} · stress ${payload.shockPct ?? 0}%`,
            };
        }
        if (payload.type === "swap") {
            return {
                title: `Swap ${payload.fromSymbol} to ${payload.toSymbol}`,
                summary: `${formatAmount(payload.amount)} ${payload.fromSymbol} · slippage ${payload.slippagePct ?? 0}%`,
            };
        }
        if (payload.type === "provide_liquidity") {
            return {
                title: `LP ${payload.token0}/${payload.token1}`,
                summary: `${formatAmount(payload.amount0)} ${payload.token0}${payload.amount1 ? ` + ${formatAmount(payload.amount1)} ${payload.token1}` : ""} · IL shock ${payload.shockPct ?? 0}%`,
            };
        }
        return {
            title: "Unsupported action",
            summary: "This action cannot be simulated yet",
        };
    }, []);

    const actionModeFromPayload = useCallback((payload: SimulationPayload): Mode => {
        if (payload.type === "stake") return "lend";
        if (payload.type === "swap") return "swap";
        return payload.type as Mode;
    }, []);

    const addActionFromPayload = useCallback((payload: SimulationPayload, actionMode = actionModeFromPayload(payload)) => {
        const description = actionMode === "buy" && payload.type === "swap"
            ? {
                title: `Buy ${payload.toSymbol}`,
                summary: `Spend ${formatAmount(payload.amount)} ${payload.fromSymbol} · slippage ${payload.slippagePct ?? 0}%`,
            }
            : describePayload(payload);
        const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
        const action: ScenarioAction = {
            id,
            mode: actionMode,
            title: description.title,
            summary: description.summary,
            payload,
        };
        setActions((current) => [...current, action].slice(0, 8));
        setSelectedActionId(id);
        setError(null);
    }, [actionModeFromPayload, describePayload]);

    useEffect(() => {
        const supportedModes: Mode[] = ["buy", "lend", "borrow", "swap", "provide_liquidity"];
        const queryMode = searchParams.get("mode") as Mode | null;
        const nextMode = queryMode && supportedModes.includes(queryMode) ? queryMode : null;
        const querySymbol = searchParams.get("symbol")?.toUpperCase();
        const queryToSymbol = searchParams.get("toSymbol")?.toUpperCase();
        const queryFundingSymbol = searchParams.get("fundingSymbol")?.toUpperCase();
        const queryMarketId = searchParams.get("marketId") || "";
        const queryShockSymbol = searchParams.get("shockSymbol")?.toUpperCase();
        const amountParam = numberFromParam(searchParams.get("amount"));
        const amount1Param = numberFromParam(searchParams.get("amount1"));
        const shockParam = numberFromParam(searchParams.get("shockPct"));
        const slippageParam = numberFromParam(searchParams.get("slippagePct"));

        if (nextMode) setMode(nextMode);
        if (querySymbol) {
            setSymbol(querySymbol);
            setEnvironmentSymbol(querySymbol);
        }
        if (queryToSymbol) setToSymbol(queryToSymbol);
        if (queryFundingSymbol) setFundingSymbol(queryFundingSymbol);
        if (queryMarketId) setSelectedMarketId(queryMarketId);
        if (queryShockSymbol) setEnvironmentSymbol(queryShockSymbol);
        if (amountParam != null) setAmount(amountParam);
        if (amount1Param != null) setAmount1(amount1Param);
        if (shockParam != null) setEnvironmentShockPct(shockParam);
        if (slippageParam != null) setSlippagePct(slippageParam);

        const autoAdd = searchParams.get("autoAdd") === "1";
        const intentId = searchParams.get("intentId") || searchParams.toString();
        if (!autoAdd || !intentId || appliedAgentIntentRef.current === intentId || !nextMode) return;

        const payload = payloadFromQuery(nextMode, {
            symbol: querySymbol,
            toSymbol: queryToSymbol,
            fundingSymbol: queryFundingSymbol,
            amount: amountParam,
            amount1: amount1Param,
            shockPct: shockParam,
            slippagePct: slippageParam,
            marketId: queryMarketId || undefined,
        });

        if (payload) {
            addActionFromPayload(payload, nextMode);
            appliedAgentIntentRef.current = intentId;
        }
    }, [addActionFromPayload, searchParams]);

    const selectedAction = useMemo(() => {
        return actions.find((action) => action.id === selectedActionId) || null;
    }, [actions, selectedActionId]);

    const removeAction = (id: string) => {
        setActions((current) => current.filter((action) => action.id !== id));
        setSelectedActionId((current) => current === id ? null : current);
    };

    const requiredBalances = (payload: SimulationPayload, actionMode = actionModeFromPayload(payload)) => {
        if (payload.type === "lend" || payload.type === "stake") {
            return [{symbol: payload.symbol.toUpperCase(), amount: payload.amount, label: `${payload.symbol} to lend`}];
        }
        if (payload.type === "swap") {
            return [{symbol: payload.fromSymbol.toUpperCase(), amount: payload.amount, label: actionMode === "buy" ? `${payload.fromSymbol} to spend` : `${payload.fromSymbol} to swap`}];
        }
        if (payload.type === "provide_liquidity") {
            return [
                {symbol: payload.token0.toUpperCase(), amount: payload.amount0, label: `${payload.token0} liquidity`},
                ...(payload.amount1 ? [{symbol: payload.token1.toUpperCase(), amount: payload.amount1, label: `${payload.token1} liquidity`}] : []),
            ];
        }
        return [];
    };

    const draftPayload = buildPayload();
    const draftRequirements = requiredBalances(draftPayload, mode);
    const draftIssues = draftRequirements
        .map((requirement) => {
            const balance = simulatedBalances.get(requirement.symbol) || 0;
            return balance + 1e-12 >= requirement.amount ? null : {
                ...requirement,
                balance,
                missing: Math.max(requirement.amount - balance, 0),
            };
        })
        .filter(Boolean) as { symbol: string; amount: number; label: string; balance: number; missing: number }[];

    const draftWarnings = useMemo(() => {
        const warnings: string[] = [];
        if (draftPayload.type === "borrow" && Number(portfolio?.summary?.collateralUsd || portfolio?.summary?.totalSupplyUsd || 0) <= 0) {
            warnings.push("Borrow action needs existing supplied collateral. No collateral position is visible in the current snapshot.");
        }
        return warnings;
    }, [draftPayload, portfolio?.summary?.collateralUsd, portfolio?.summary?.totalSupplyUsd]);

    const addBuyActionForMissingToken = (targetSymbol: string) => {
        setMode("buy");
        setSymbol(targetSymbol.toUpperCase());
        setFundingSymbol((simulatedBalances.get("USDC") || 0) > 0 ? "USDC" : simulatedAssets.find((asset) => asset.balance > 0)?.symbol || "USDC");
        setAmount(Math.max(1, Number(draftIssues.find((item) => item.symbol === targetSymbol)?.missing || 1)));
    };

    const availableFor = (tokenSymbol: string) => simulatedBalances.get(tokenSymbol.toUpperCase()) || 0;

    const primaryAvailable = (() => {
        if (mode === "buy") return availableFor(fundingSymbol);
        if (mode === "lend" || mode === "swap" || mode === "provide_liquidity") return availableFor(symbol);
        return undefined;
    })();

    const runSimulation = async (payload = buildPayload()) => {
        if (!address) {
            setError("Connect wallet before running simulation.");
            return;
        }
        setIsRunning(true);
        setError(null);
        try {
            setResult(await simulateWallet(address, applyEnvironmentToPayload(payload)));
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : "Simulation failed");
        } finally {
            setIsRunning(false);
        }
    };

    const runSelectedAction = async () => {
        await runSimulation(selectedAction?.payload || buildPayload());
    };

    const runEnvironmentOnly = async () => {
        await runSimulation({type: "price_shock", shocks: {[environmentSymbol.toUpperCase()]: environmentShockPct}});
    };

    return (
        <div className="flex flex-1 flex-col gap-4 p-4 md:p-5">
            <div className="grid gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(380px,2fr)]">
                <div className="space-y-4">
                    <div className="grid items-stretch gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
                        <Div className={focusClass(`simulator:shock:${environmentSymbol.toUpperCase()}`, "h-full transition-all duration-200")}>
                            <div className="mb-3 flex items-center justify-between gap-3">
                                <div>
                                    <div className="flex items-center gap-2">
                                        <Percent size={15} className="text-violet-500"/>
                                        <p className={cn("text-sm font-semibold", ui.text.heading)}>Market Environment</p>
                                    </div>
                                    <p className="mt-1 text-[11px] text-zinc-500">Stress inputs, not actions.</p>
                                </div>
                                <button
                                    onClick={runEnvironmentOnly}
                                    disabled={isRunning}
                                    className="rounded-lg border border-violet-200 px-3 py-2 text-[11px] font-semibold text-violet-700 transition-all hover:bg-violet-50 disabled:opacity-60 dark:border-violet-900/50 dark:text-violet-300 dark:hover:bg-violet-950/30"
                                >
                                    Run Shock
                                </button>
                            </div>
                            <div className="grid items-end gap-3 sm:grid-cols-2">
                                <Select label="Token" value={environmentSymbol} onChange={setEnvironmentSymbol} options={tokenOptions}/>
                                <label className="block">
                                    <span className="text-xs font-medium text-zinc-500">Price move (%)</span>
                                    <input className={cn(ui.input.base, "mt-1")} type="number" value={environmentShockPct} onChange={(e) => setEnvironmentShockPct(Number(e.target.value))}/>
                                </label>
                            </div>
                        </Div>

                        <Div className={focusClass("simulator:wallet", "h-full transition-all duration-200")}>
                            <p className={cn("text-sm font-semibold", ui.text.heading)}>Wallet Context</p>
                            <p className="mt-1 text-[11px] text-zinc-500">After queued actions, used for feasibility checks.</p>
                            <div className="mt-3 grid grid-cols-3 gap-2">
                                {[
                                    {label: "Supply", value: portfolio?.summary?.totalSupplyUsd || 0},
                                    {label: "Collateral", value: portfolio?.summary?.collateralUsd || 0},
                                    {label: "Debt", value: portfolio?.summary?.totalBorrowUsd || 0},
                                ].map((item) => (
                                    <div key={item.label} className="rounded-lg border border-violet-100 bg-violet-50/50 px-3 py-2 dark:border-violet-900/40 dark:bg-violet-950/20">
                                        <p className="text-[10px] uppercase tracking-wider text-zinc-500">{item.label}</p>
                                        <p className={cn("mt-1 truncate text-xs font-semibold", ui.text.heading)}>{formatMoney(item.value)}</p>
                                    </div>
                                ))}
                            </div>
                            <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
                                {isPortfolioLoading ? (
                                    <>
                                        <Skeleton className="h-14 min-w-28"/>
                                        <Skeleton className="h-14 min-w-28"/>
                                        <Skeleton className="h-14 min-w-28"/>
                                    </>
                                ) : simulatedAssets.length ? simulatedAssets.map((asset) => {
                                    const delta = asset.balance - asset.originalBalance;
                                    return (
                                    <div key={asset.symbol} className="min-w-[116px] rounded-lg border border-violet-100 bg-white/70 px-3 py-2 text-xs dark:border-violet-900/40 dark:bg-zinc-950/30">
                                        <p className={cn("font-semibold", ui.text.heading)}>{asset.symbol}</p>
                                        <p className="mt-0.5 text-[11px] text-zinc-500">{formatAmount(asset.balance)}</p>
                                        {Math.abs(delta) > 1e-9 && (
                                            <p className={cn("mt-0.5 text-[10px] font-semibold", delta > 0 ? ui.text.up : ui.text.down)}>
                                                {delta > 0 ? "+" : ""}{formatAmount(delta)}
                                            </p>
                                        )}
                                        <p className="mt-1 font-semibold tabular-nums">{formatMoney(asset.valueUsd)}</p>
                                    </div>
                                )}) : (
                                    <div className="rounded-lg border border-violet-100 bg-violet-50/50 p-3 text-xs text-zinc-500 dark:border-violet-900/40 dark:bg-violet-950/20">
                                        No wallet assets loaded yet.
                                    </div>
                                )}
                            </div>
                        </Div>
                    </div>

                    <Div className={focusClass(payloadFocusKeys(draftPayload, mode), "transition-all duration-200")}>
                        <div className="mb-3 flex items-center justify-between">
                            <p className={cn("text-sm font-semibold", ui.text.heading)}>Configure Draft</p>
                            <span className="hidden text-[11px] font-medium text-zinc-500 sm:block">{MODE_META[mode].hint}</span>
                        </div>

                        <div className="mb-4 grid grid-cols-2 gap-1 rounded-xl bg-violet-50 p-1 sm:grid-cols-3 dark:bg-violet-950/20">
                            {(Object.keys(MODE_META) as Mode[]).map((key) => (
                                <button
                                    key={key}
                                    onClick={() => {
                                        setMode(key);
                                        setSelectedMarketId("");
                                    }}
                                    className={cn(
                                        "flex items-center justify-center gap-1 rounded-lg px-2 py-2 text-[11px] font-semibold transition-all",
                                        mode === key ? "border border-violet-200 bg-violet-50 text-violet-800 dark:border-violet-800/60 dark:bg-violet-950/35 dark:text-violet-200" : "text-zinc-500 hover:bg-violet-50/70 hover:text-violet-600 dark:hover:bg-violet-950/25"
                                    )}
                                >
                                    {MODE_META[key].icon}
                                    {MODE_META[key].label}
                                </button>
                            ))}
                        </div>

                        <div className="space-y-3 rounded-xl border border-violet-100 bg-white/60 p-3 dark:border-violet-900/40 dark:bg-zinc-950/25">
                            {(mode === "lend" || mode === "borrow" || mode === "provide_liquidity") && (
                                <Select
                                    label="Market"
                                    value={selectedMarketId}
                                    placeholder={isLoadingMarkets ? "Loading markets..." : "Select a market"}
                                    onChange={applyMarket}
                                    options={marketOptions
                                        .filter((market) => market.market_id)
                                        .map((market) => ({
                                            label: market.symbol || market.raw_data?.asset || market.raw_data?.symbol || "UNKNOWN",
                                            value: market.market_id || "",
                                            description: marketLabel(market),
                                        }))}
                                />
                            )}

                            {mode === "buy" && (
                                <div className="grid gap-3 sm:grid-cols-2">
                                    <Select label="Buy token" value={symbol} onChange={setSymbol} options={tokenOptions}/>
                                    <Select label="Pay with" value={fundingSymbol} onChange={setFundingSymbol} options={tokenOptions}/>
                                </div>
                            )}

                            {mode === "swap" && (
                                <div className="grid gap-3 sm:grid-cols-2">
                                    <Select label="Sell token" value={symbol} onChange={setSymbol} options={tokenOptions}/>
                                    <Select label="Receive token" value={toSymbol} onChange={setToSymbol} options={tokenOptions}/>
                                </div>
                            )}

                            {mode === "lend" && !selectedMarket && (
                                <Select label="Supply token" value={symbol} onChange={setSymbol} options={tokenOptions}/>
                            )}

                            {selectedMarket && (
                                <div className={focusClass([`pool:${selectedMarketId}`, ...payloadFocusKeys(draftPayload, mode)], "rounded-lg border border-violet-100 bg-violet-50/50 p-3 text-xs transition-all duration-200 dark:border-violet-900/40 dark:bg-violet-950/20")}>
                                    <div className="grid gap-2 sm:grid-cols-2">
                                        <Info label="Protocol" value={selectedMarket.protocol || selectedMarket.raw_data?.protocol || selectedMarket.raw_data?.dex || "Unknown"}/>
                                        <Info label="Market" value={selectedMarket.symbol || selectedMarket.raw_data?.asset || selectedMarket.raw_data?.symbol || "-"}/>
                                        <Info label="APR" value={`${Number(selectedMarket.apr ?? selectedMarket.raw_data?.total_apr ?? selectedMarket.raw_data?.supplyApr ?? 0).toFixed(2)}%`}/>
                                        <Info label="Borrow APR" value={`${Number(selectedMarket.raw_data?.borrowApr ?? selectedMarket.raw_data?.borrowStableApr ?? 0).toFixed(2)}%`}/>
                                        <Info label="Max LTV" value={`${toPct(selectedMarket.raw_data?.maxLtv || selectedMarket.raw_data?.maximumLTV)}`}/>
                                        <Info label="Liquidation" value={`${toPct(selectedMarket.raw_data?.liquidationThreshold)}`}/>
                                    </div>
                                </div>
                            )}

                            <AmountInput
                                label={mode === "buy" ? `Spend amount (${fundingSymbol})` : `Amount${primaryAvailable !== undefined ? ` · available ${formatAmount(primaryAvailable)}` : ""}`}
                                value={amount}
                                onChange={setAmount}
                                max={primaryAvailable}
                            />

                            {mode === "provide_liquidity" && (
                                <>
                                    <Select
                                        label="Pair token"
                                        value={toSymbol}
                                        onChange={setToSymbol}
                                        options={tokenOptions}
                                    />
                                </>
                            )}

                            {(mode === "buy" || mode === "swap") && (
                                <AmountInput label="Slippage (%)" value={slippagePct} onChange={setSlippagePct} step={0.1}/>
                            )}

                            {mode === "provide_liquidity" && (
                                <>
                                    <AmountInput
                                        label={`Pair token amount · available ${formatAmount(availableFor(toSymbol))}`}
                                        value={amount1}
                                        onChange={setAmount1}
                                        max={availableFor(toSymbol)}
                                    />
                                </>
                            )}

                            {draftRequirements.length > 0 && (
                                <div className={cn(
                                    "rounded-lg border px-3 py-2 text-xs",
                                    draftIssues.length
                                        ? "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/20 dark:text-amber-300"
                                        : "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/20 dark:text-emerald-300"
                                )}>
                                    {draftIssues.length ? (
                                        <div className="space-y-2">
                                            {draftIssues.map((issue) => (
                                                <div key={issue.symbol} className="flex items-center justify-between gap-3">
                                                    <span>
                                                        Missing {formatAmount(issue.missing)} {issue.symbol} for {issue.label}. Current balance: {formatAmount(issue.balance)}.
                                                    </span>
                                                    {mode !== "buy" && (
                                                        <button
                                                            onClick={() => addBuyActionForMissingToken(issue.symbol)}
                                                            className="shrink-0 rounded-md bg-amber-100 px-2 py-1 text-[11px] font-semibold text-amber-800 transition-all dark:bg-amber-900/40 dark:text-amber-200"
                                                        >
                                                            Configure buy
                                                        </button>
                                                    )}
                                                </div>
                                            ))}
                                        </div>
                                    ) : (
                                        <span>Wallet has enough token balance for this draft action.</span>
                                    )}
                                </div>
                            )}

                            {draftWarnings.length > 0 && (
                                <div className="rounded-lg border border-violet-200 bg-violet-50/50 px-3 py-2 text-xs text-violet-800 dark:border-violet-900/50 dark:bg-violet-950/20 dark:text-violet-200">
                                    {draftWarnings.map((warning) => (
                                        <p key={warning}>{warning}</p>
                                    ))}
                                </div>
                            )}
                        </div>

                        <button
                            onClick={() => addActionFromPayload(buildPayload(), mode)}
                            className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-lg border border-violet-200 bg-violet-50 px-3 py-2.5 text-xs font-semibold text-violet-800 transition-all hover:border-violet-300 hover:bg-violet-100 dark:border-violet-800/60 dark:bg-violet-950/35 dark:text-violet-200 dark:hover:bg-violet-900/25 disabled:opacity-60"
                        >
                            <ListPlus size={14}/>
                            Add Draft Action
                        </button>
                    </Div>
                </div>

                <div className="space-y-4">
                    <Div className={focusClass(payloadFocusKeys(selectedAction?.payload || draftPayload, selectedAction?.mode || mode), "transition-all duration-200")}>
                        <div className="mb-3 flex items-center justify-between gap-3">
                            <div>
                                <p className={cn("text-sm font-semibold", ui.text.heading)}>Scenario Actions</p>
                                <p className="mt-0.5 text-[11px] text-zinc-500">Queue of actions to compare and run.</p>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="rounded-full bg-violet-100 px-2 py-1 text-[10px] font-semibold text-violet-700 dark:bg-violet-950/40 dark:text-violet-300">
                                    {actions.length}/8
                                </span>
                                <button
                                    onClick={runSelectedAction}
                                    disabled={isRunning}
                                    className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-violet-200 bg-violet-50 px-3 py-2 text-[11px] font-semibold text-violet-800 transition-all hover:border-violet-300 hover:bg-violet-100 dark:border-violet-800/60 dark:bg-violet-950/35 dark:text-violet-200 dark:hover:bg-violet-900/25 disabled:opacity-60"
                                >
                                    <Play size={13}/>
                                    Run
                                </button>
                            </div>
                        </div>

                            <div className="max-h-[260px] space-y-2 overflow-y-auto pr-1">
                            {actions.length ? actions.map((action, index) => {
                                const active = action.id === selectedActionId;
                                return (
                                    <button
                                        key={action.id}
                                        onClick={() => setSelectedActionId(action.id)}
                                        className={focusClass(payloadFocusKeys(action.payload, action.mode), cn(
                                            "group flex w-full items-center gap-3 rounded-xl border p-3 text-left transition-all duration-200",
                                            active
                                                ? "border-violet-500 bg-violet-50 shadow-[0_10px_30px_rgba(139,92,246,0.12)] dark:bg-violet-950/30"
                                                : "border-violet-100 bg-violet-50/30 hover:border-violet-300 hover:bg-violet-50/60 dark:border-violet-900/40 dark:bg-zinc-950/30 dark:hover:bg-violet-950/20"
                                        ))}
                                    >
                                        <span className={cn(
                                            "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border text-xs font-semibold",
                                            active
                                                ? "border border-violet-200 bg-violet-50 text-violet-800 hover:border-violet-300 hover:bg-violet-100 dark:border-violet-800/60 dark:bg-violet-950/35 dark:text-violet-200 dark:hover:bg-violet-900/25"
                                                : "border-violet-100 bg-violet-50 text-violet-600 dark:border-violet-900/50 dark:bg-violet-950/30"
                                        )}>
                                            {active ? <CheckCircle2 size={15}/> : index + 1}
                                        </span>
                                        <span className="min-w-0 flex-1">
                                            <span className={cn("block truncate text-xs font-semibold", ui.text.heading)}>{action.title}</span>
                                            <span className="mt-0.5 block truncate text-[11px] text-zinc-500">{action.summary}</span>
                                        </span>
                                        <span
                                            role="button"
                                            tabIndex={0}
                                            onClick={(event) => {
                                                event.stopPropagation();
                                                removeAction(action.id);
                                            }}
                                            onKeyDown={(event) => {
                                                if (event.key === "Enter" || event.key === " ") {
                                                    event.preventDefault();
                                                    event.stopPropagation();
                                                    removeAction(action.id);
                                                }
                                            }}
                                            className="rounded-md p-1.5 text-zinc-400 opacity-0 transition-all hover:bg-red-50 hover:text-red-500 group-hover:opacity-100 dark:hover:bg-red-950/30"
                                            aria-label={`Remove ${action.title}`}
                                        >
                                            <Trash2 size={14}/>
                                        </span>
                                    </button>
                                );
                            }) : (
                                <div className="rounded-xl border border-dashed border-violet-200 bg-violet-50/40 p-4 text-center text-xs text-zinc-500 dark:border-violet-900/50 dark:bg-violet-950/20">
                                    Configure a real action, then add it to this scenario.
                                </div>
                            )}
                        </div>
                    </Div>

                    {error && (
                        <div className="flex gap-2 rounded-lg border border-red-100 bg-red-50 p-3 text-sm text-red-600 dark:border-red-900/40 dark:bg-red-950/20">
                            <AlertTriangle size={16}/>
                            {error}
                        </div>
                    )}

                    {isRunning ? (
                        <Div>
                            <Skeleton className="h-10 w-52"/>
                            <div className="mt-5 grid grid-cols-3 gap-3">
                                <Skeleton className="h-20"/>
                                <Skeleton className="h-20"/>
                                <Skeleton className="h-20"/>
                            </div>
                            <Skeleton className="mt-5 h-48"/>
                        </Div>
                    ) : result ? (
                        <Div>
                            <div className="grid gap-3 sm:grid-cols-3">
                                {[
                                    {label: "Net Worth", before: result.before.netWorthUsd, after: result.after.netWorthUsd},
                                    {label: "Token Hold", before: result.before.tokenHoldUsd, after: result.after.tokenHoldUsd},
                                    {label: "Positions", before: result.before.positionUsd, after: result.after.positionUsd},
                                ].map((item) => {
                                    const delta = item.after - item.before;
                                    return (
                                        <div key={item.label} className="rounded-lg border border-violet-100 bg-violet-50/40 p-3 dark:border-violet-900/40 dark:bg-violet-950/15">
                                            <p className="text-[10px] uppercase tracking-wider text-zinc-500">{item.label}</p>
                                            <p className={cn("mt-1 text-base font-semibold", ui.text.heading)}>{formatMoney(item.after)}</p>
                                            <p className={cn("mt-0.5 text-xs font-semibold", delta >= 0 ? ui.text.up : ui.text.down)}>
                                                {delta >= 0 ? "+" : ""}{formatMoney(delta)}
                                            </p>
                                        </div>
                                    );
                                })}
                            </div>

                            <div className="mt-5 grid gap-4 2xl:grid-cols-2">
                                <div>
                                    <p className={cn("mb-2 text-sm font-semibold", ui.text.heading)}>Expected Changes</p>
                                    <div className="space-y-2">
                                        {result.changes.map((change) => (
                                            <div key={change.label} className="flex justify-between gap-3 rounded-lg bg-violet-50/50 px-3 py-2 text-sm dark:bg-violet-950/20">
                                                <span className="text-zinc-500">{change.label}</span>
                                                <span className={cn("font-semibold tabular-nums", change.deltaUsd >= 0 ? ui.text.up : ui.text.down)}>
                                                    {change.deltaUsd >= 0 ? "+" : ""}{formatMoney(change.deltaUsd)}
                                                </span>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                <div>
                                    <p className={cn("mb-2 text-sm font-semibold", ui.text.heading)}>Warnings & Assumptions</p>
                                    <div className="space-y-2">
                                        {[...result.warnings, ...result.assumptions].map((item) => (
                                            <div key={item} className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-zinc-600 dark:bg-amber-950/20 dark:text-zinc-400">
                                                {item}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </div>

                            {result.strategy && (
                                <div className="mt-5 rounded-lg border border-violet-100 bg-white/60 p-3 dark:border-violet-900/40 dark:bg-zinc-950/30">
                                    <p className={cn("mb-2 text-sm font-semibold", ui.text.heading)}>Strategy Details</p>
                                    <div className="grid gap-2 text-xs sm:grid-cols-2">
                                        {Object.entries(result.strategy)
                                            .filter(([, value]) => typeof value !== "object" || value === null)
                                            .map(([key, value]) => (
                                                <div key={key} className="flex items-center justify-between gap-3 rounded-md bg-violet-50/60 px-3 py-2 dark:bg-violet-950/20">
                                                    <span className="text-zinc-500">{key}</span>
                                                    <span className={cn("font-semibold", ui.text.heading)}>{String(value)}</span>
                                                </div>
                                            ))}
                                    </div>
                                </div>
                            )}
                        </Div>
                    ) : (
                        <Div className="flex min-h-[420px] items-center justify-center text-sm text-zinc-500">
                            Select a market, build a scenario, then run simulation.
                        </Div>
                    )}
                </div>
            </div>
        </div>
    );
}

function Info({label, value}: { label: string; value: string }) {
    return (
        <div>
            <p className="text-[10px] uppercase tracking-wider text-zinc-400">{label}</p>
            <p className="mt-0.5 font-semibold text-zinc-700 dark:text-zinc-200">{value}</p>
        </div>
    );
}

function payloadFocusKeys(payload: SimulationPayload, actionMode: Mode): string[] {
    if (payload.type === "price_shock") {
        const [symbol] = Object.keys(payload.shocks);
        return [`simulator:shock:${String(symbol || "ETH").toUpperCase()}`];
    }
    if (payload.type === "swap") {
        if (actionMode === "buy") {
            return [
                `simulator:buy:${payload.toSymbol.toUpperCase()}`,
                `token:${payload.toSymbol.toUpperCase()}`,
                `token:${payload.fromSymbol.toUpperCase()}`,
            ];
        }
        return [
            `simulator:swap:${payload.fromSymbol.toUpperCase()}:${payload.toSymbol.toUpperCase()}`,
            `token:${payload.fromSymbol.toUpperCase()}`,
            `token:${payload.toSymbol.toUpperCase()}`,
        ];
    }
    if (payload.type === "lend" || payload.type === "stake") {
        return [
            `simulator:${actionMode}:${payload.symbol.toUpperCase()}`,
            `token:${payload.symbol.toUpperCase()}`,
            ...(payload.marketId ? [`pool:${payload.marketId}`] : []),
        ];
    }
    if (payload.type === "borrow") {
        return [
            `simulator:borrow:${payload.symbol.toUpperCase()}`,
            `token:${payload.symbol.toUpperCase()}`,
            ...(payload.marketId ? [`pool:${payload.marketId}`] : []),
        ];
    }
    if (payload.type === "provide_liquidity") {
        return [
            `simulator:lp:${payload.token0.toUpperCase()}:${payload.token1.toUpperCase()}`,
            `token:${payload.token0.toUpperCase()}`,
            `token:${payload.token1.toUpperCase()}`,
            ...(payload.marketId ? [`pool:${payload.marketId}`] : []),
        ];
    }

    return [`simulator:${actionMode}`];
}

function payloadFromQuery(
    mode: Mode,
    values: {
        symbol?: string;
        toSymbol?: string;
        fundingSymbol?: string;
        amount?: number | null;
        amount1?: number | null;
        shockPct?: number | null;
        slippagePct?: number | null;
        marketId?: string;
    },
): SimulationPayload | null {
    const amount = values.amount ?? (mode === "borrow" ? 100 : 1);
    const marketId = values.marketId || undefined;
    const symbol = values.symbol || "ETH";

    if (mode === "buy") {
        return {
            type: "swap",
            fromSymbol: values.fundingSymbol || "USDC",
            toSymbol: symbol,
            amount,
            slippagePct: values.slippagePct ?? 0.3,
        };
    }
    if (mode === "lend") {
        return {type: "lend", symbol, amount, marketId};
    }
    if (mode === "borrow") {
        return {type: "borrow", symbol, amount, marketId, shockPct: values.shockPct ?? -20};
    }
    if (mode === "swap") {
        return {
            type: "swap",
            fromSymbol: symbol,
            toSymbol: values.toSymbol || "USDC",
            amount,
            slippagePct: values.slippagePct ?? 0.3,
        };
    }
    if (mode === "provide_liquidity") {
        return {
            type: "provide_liquidity",
            token0: symbol,
            token1: values.toSymbol || "USDC",
            amount0: amount,
            amount1: values.amount1 && values.amount1 > 0 ? values.amount1 : undefined,
            marketId,
            shockPct: values.shockPct ?? -20,
        };
    }

    return null;
}

function numberFromParam(value: string | null) {
    if (value == null || value === "") return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
}

function toPct(value: unknown) {
    const numeric = Number(value || 0);
    if (!numeric) return "-";
    return `${(numeric > 1 ? numeric : numeric * 100).toFixed(2)}%`;
}

function formatAmount(value: number) {
    if (!Number.isFinite(value)) return "0";
    if (Math.abs(value) >= 1000) return value.toLocaleString(undefined, {maximumFractionDigits: 2});
    return value.toLocaleString(undefined, {maximumFractionDigits: 6});
}

function AmountInput({
    label,
    value,
    onChange,
    min = 0,
    max,
    step = 0.01,
}: {
    label: string;
    value: number;
    onChange: (value: number) => void;
    min?: number;
    max?: number;
    step?: number;
}) {
    const clamp = (next: number) => {
        if (!Number.isFinite(next)) return min;
        const upper = max === undefined ? next : Math.min(next, max);
        return Math.max(upper, min);
    };
    const setPercent = (pct: number) => {
        if (max === undefined) return;
        onChange(clamp(max * pct));
    };

    return (
        <div className="block">
            <div className="mb-1 flex items-center justify-between gap-2">
                <span className="text-xs font-medium text-zinc-500">{label}</span>
                {max !== undefined && max > 0 && (
                    <button
                        type="button"
                        onClick={() => onChange(clamp(max))}
                        className="rounded-md bg-violet-50 px-2 py-1 text-[10px] font-semibold text-violet-700 transition-all hover:bg-violet-100 dark:bg-violet-950/30 dark:text-violet-300"
                    >
                        Max
                    </button>
                )}
            </div>
            <div className="flex h-12 overflow-hidden rounded-lg border border-violet-100 bg-white transition-all focus-within:border-violet-400 focus-within:ring-2 focus-within:ring-violet-100 dark:border-violet-900/50 dark:bg-zinc-950 dark:focus:ring-violet-950/40">
                <button
                    type="button"
                    onClick={() => onChange(clamp(value - step))}
                    className="flex w-11 items-center justify-center text-violet-600 transition-colors hover:bg-violet-50 dark:text-violet-300 dark:hover:bg-violet-950/30"
                >
                    <Minus size={14}/>
                </button>
                <input
                    className="min-w-0 flex-1 bg-transparent px-2 text-center text-sm font-semibold text-zinc-900 outline-none dark:text-zinc-100"
                    type="number"
                    value={value}
                    min={min}
                    max={max}
                    step={step}
                    onChange={(event) => onChange(clamp(Number(event.target.value)))}
                />
                <button
                    type="button"
                    onClick={() => onChange(clamp(value + step))}
                    className="flex w-11 items-center justify-center text-violet-600 transition-colors hover:bg-violet-50 dark:text-violet-300 dark:hover:bg-violet-950/30"
                >
                    <Plus size={14}/>
                </button>
            </div>
            {max !== undefined && max > 0 && (
                <div className="mt-2 grid grid-cols-4 gap-1">
                    {[
                        {label: "25%", value: 0.25},
                        {label: "50%", value: 0.5},
                        {label: "75%", value: 0.75},
                        {label: "100%", value: 1},
                    ].map((item) => (
                        <button
                            key={item.label}
                            type="button"
                            onClick={() => setPercent(item.value)}
                            className="rounded-md border border-violet-100 bg-violet-50/60 px-2 py-1 text-[10px] font-semibold text-violet-700 transition-all hover:border-violet-300 hover:bg-violet-100 dark:border-violet-900/50 dark:bg-violet-950/20 dark:text-violet-300"
                        >
                            {item.label}
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}
