import type {
  TrendTopic,
  StockDetail,
  StockHistory,
  StockProfile,
  NewsItem,
  ChatResponse,
  Portfolio,
  TradeHistoryItem,
  RelatedStock,
  PeerStock,
  ResearchResult,
  UnifiedFeed,
  TrendingTopic,
  TranslatedArticle,
  Newsletter,
  CryptoFeed,
  CommodityPrice,
  ForexRate,
  BondYield,
  SupplyChain,
  CommodityImpact,
} from "./types";

const BASE = "/api";

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, init);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

// Trends
export const getTrends = (sector?: string) =>
  fetchJSON<TrendTopic[]>(`/trends${sector ? `?sector=${sector}` : ""}`);

export const getTrendBySlug = (slug: string) =>
  fetchJSON<TrendTopic>(`/trends/${slug}`);

// Stocks
export const getStocks = (params?: {
  sector?: string;
  search?: string;
  sort_by?: string;
  min_price?: number;
  max_price?: number;
  topic?: string;
}) => {
  const sp = new URLSearchParams();
  if (params?.sector) sp.set("sector", params.sector);
  if (params?.search) sp.set("search", params.search);
  if (params?.sort_by) sp.set("sort_by", params.sort_by);
  if (params?.min_price) sp.set("min_price", String(params.min_price));
  if (params?.max_price) sp.set("max_price", String(params.max_price));
  if (params?.topic) sp.set("topic", params.topic);
  return fetchJSON<StockDetail[]>(`/stocks?${sp}`);
};

export const getStockHistory = (ticker: string, period = "1mo") =>
  fetchJSON<StockHistory>(`/stocks/${ticker}/history?period=${period}`);

export const getStockProfile = (ticker: string, language?: string) =>
  fetchJSON<StockProfile>(`/stocks/${ticker}/profile${language ? `?language=${language}` : ""}`);

// News
export const getNews = (params?: { topic?: string; ticker?: string }) => {
  const sp = new URLSearchParams();
  if (params?.topic) sp.set("topic", params.topic);
  if (params?.ticker) sp.set("ticker", params.ticker);
  return fetchJSON<NewsItem[]>(`/news?${sp}`);
};

// Topic Insights
export const getTopicInsight = (slug: string, language: string) =>
  fetchJSON<{
    slug: string;
    why_trending: string;
    stock_connections: Record<string, string>;
    ai_analysis?: string;
    generated?: boolean;
    related_topics?: { slug: string; name: string; connection: string }[];
    hidden_connections?: { ticker: string; company: string; connection: string }[];
  }>(`/trends/${slug}/insight?language=${language}`);

export const getStockInsight = (slug: string, ticker: string, language: string) =>
  fetchJSON<{ slug: string; ticker: string; connection: string }>(
    `/trends/${slug}/stock-insight/${ticker}?language=${language}`
  );

// Chat
export const askAI = (question: string, language: string, context?: string) =>
  fetchJSON<ChatResponse>("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, language, context }),
  });

export const getChatRemaining = () =>
  fetchJSON<{ remaining: number; daily_limit: number }>("/chat/remaining");

// Explain
export const explainTerm = (term: string, language: string) =>
  fetchJSON<{ term: string; explanation: string }>("/chat/explain-term", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ term, language }),
  });

export const explainSection = (
  ticker: string,
  section: string,
  data: Record<string, unknown>,
  language: string
) =>
  fetchJSON<{ ticker: string; section: string; explanation: string }>(
    "/chat/explain-section",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker, section, data, language }),
    }
  );

// Related Stocks
export const getRelatedStocks = (ticker: string) =>
  fetchJSON<RelatedStock[]>(`/stocks/${ticker}/related`);

// Peer Comparison
export const getPeerStocks = (ticker: string) =>
  fetchJSON<PeerStock[]>(`/stocks/${ticker}/peers`);

// Deep Research
export const getResearch = (ticker: string, language: string) =>
  fetchJSON<ResearchResult>(`/stocks/${ticker}/research?language=${language}`, {
    method: "POST",
  });

// Paper Trading
export const getPortfolio = (sessionId: string) =>
  fetchJSON<Portfolio>(`/paper/portfolio/${sessionId}`);

export const getTradeHistory = (sessionId: string) =>
  fetchJSON<TradeHistoryItem[]>(`/paper/history/${sessionId}`);

export const executeTrade = (data: {
  session_id: string;
  ticker: string;
  action: "buy" | "sell";
  quantity: number;
}) =>
  fetchJSON<{ status: string; price: number; total: number }>("/paper/trade", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });

// Unified Feed
export const getFeed = (params?: {
  sector?: string;
  market?: string;
  include_il?: boolean;
  include_global?: boolean;
  include_podcasts?: boolean;
  include_institutional?: boolean;
  include_blogs?: boolean;
}) => {
  const sp = new URLSearchParams();
  if (params?.sector) sp.set("sector", params.sector);
  if (params?.market) sp.set("market", params.market);
  if (params?.include_il !== undefined) sp.set("include_il", String(params.include_il));
  if (params?.include_global !== undefined) sp.set("include_global", String(params.include_global));
  if (params?.include_podcasts !== undefined) sp.set("include_podcasts", String(params.include_podcasts));
  if (params?.include_institutional !== undefined) sp.set("include_institutional", String(params.include_institutional));
  if (params?.include_blogs !== undefined) sp.set("include_blogs", String(params.include_blogs));
  return fetchJSON<UnifiedFeed>(`/feed?${sp}`);
};

// Translate article
export const translateArticle = (params: {
  title: string;
  description?: string;
  source?: string;
  url?: string;
  target_language?: string;
}) => {
  const sp = new URLSearchParams();
  sp.set("title", params.title);
  if (params.description) sp.set("description", params.description);
  if (params.source) sp.set("source", params.source);
  if (params.url) sp.set("url", params.url);
  sp.set("target_language", params.target_language || "he");
  return fetchJSON<TranslatedArticle>(`/feed/translate?${sp}`, { method: "POST" });
};

// Trending topics (cross-referenced)
export const getTrendingTopics = (params?: { market?: string; limit?: number }) => {
  const sp = new URLSearchParams();
  if (params?.market) sp.set("market", params.market);
  if (params?.limit) sp.set("limit", String(params.limit));
  return fetchJSON<{ trending_topics: TrendingTopic[]; market: string }>(`/feed/trending-topics?${sp}`);
};

// Newsletter
export const generateNewsletter = (params?: { language?: string; market?: string }) => {
  const sp = new URLSearchParams();
  sp.set("language", params?.language || "he");
  if (params?.market) sp.set("market", params.market);
  return fetchJSON<Newsletter>(`/feed/newsletter?${sp}`, { method: "POST" });
};

// Crypto
export const getCryptoFeed = (vs_currency = "usd") =>
  fetchJSON<CryptoFeed>(`/feed/crypto?vs_currency=${vs_currency}`);

// Commodities
export const getCommodities = (category?: string) => {
  const sp = new URLSearchParams();
  if (category) sp.set("category", category);
  return fetchJSON<{ commodities: CommodityPrice[] }>(`/feed/commodities?${sp}`);
};

// Forex
export const getForexRates = (category?: string) => {
  const sp = new URLSearchParams();
  if (category) sp.set("category", category);
  return fetchJSON<{ forex: ForexRate[] }>(`/feed/forex?${sp}`);
};

// Bonds
export const getBondYields = () =>
  fetchJSON<{ yields: BondYield[] }>("/feed/bonds");

// Supply Chain
export const getSupplyChain = (chain?: string) => {
  const sp = new URLSearchParams();
  if (chain) sp.set("chain", chain);
  return fetchJSON<SupplyChain | { supply_chains: { key: string; name: string; name_he: string; stages: number }[] }>(`/feed/supply-chain?${sp}`);
};

export const getCommodityImpact = (commodity: string) =>
  fetchJSON<{ commodity: string; impacts: CommodityImpact[] }>(`/feed/supply-chain/commodity-impact/${commodity}`);

export const getIsraeliSupplyChain = () =>
  fetchJSON<{ connections: CommodityImpact[] }>("/feed/supply-chain/israel");

export const getSupplyChainTips = (params?: { commodity?: string; chain?: string; category?: string; limit?: number }) => {
  const sp = new URLSearchParams();
  if (params?.commodity) sp.set("commodity", params.commodity);
  if (params?.chain) sp.set("chain", params.chain);
  if (params?.category) sp.set("category", params.category);
  if (params?.limit) sp.set("limit", String(params.limit));
  return fetchJSON<{ tips: import("./types").SupplyChainTip[] }>(`/feed/supply-chain/tips?${sp}`);
};

// AI Agent
export const getAgentDashboard = () =>
  fetchJSON<import("./types").AgentDashboard>("/agent/dashboard");

export const analyzeTickerAgent = (ticker: string) =>
  fetchJSON<import("./types").AgentAnalysis>(`/agent/analyze/${ticker}`, { method: "POST" });

export const executeTickerAgent = (ticker: string) =>
  fetchJSON<{ ticker: string; decision: string; confidence: number; reason: string; trade: unknown }>(`/agent/execute/${ticker}`, { method: "POST" });

export const triggerAgentLearning = () =>
  fetchJSON<{ weight_update: unknown; performance: unknown }>("/agent/learn", { method: "POST" });

export const getBreakingNews = () =>
  fetchJSON<import("./types").BreakingNewsResult>("/agent/breaking");

export const triggerBreakingScan = () =>
  fetchJSON<{ breaking: import("./types").BreakingNewsResult; auto_analyses: import("./types").BreakingAnalysis[] }>("/agent/breaking/scan", { method: "POST" });

export const retrainAgentML = () =>
  fetchJSON<import("./types").MLModelInfo>("/agent/ml/retrain", { method: "POST" });

export const getAgentMLInfo = () =>
  fetchJSON<import("./types").MLModelInfo>("/agent/ml/info");

// Tracking
export const trackInteraction = (data: {
  interaction_type: string;
  target_slug?: string;
  metadata?: Record<string, string>;
}) => {
  const sessionId = getSessionId();
  fetch(`${BASE}/track?session_id=${sessionId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  }).catch(() => {});
};

// Session
export function getSessionId(): string {
  if (typeof window === "undefined") return "";
  let id = localStorage.getItem("trendvest_session");
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem("trendvest_session", id);
  }
  return id;
}
