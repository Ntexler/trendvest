import type {
  TrendTopic,
  StockDetail,
  StockHistory,
  StockProfile,
  NewsItem,
  ChatResponse,
  Portfolio,
  TradeHistoryItem,
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
  max_price?: number;
}) => {
  const sp = new URLSearchParams();
  if (params?.sector) sp.set("sector", params.sector);
  if (params?.search) sp.set("search", params.search);
  if (params?.sort_by) sp.set("sort_by", params.sort_by);
  if (params?.max_price) sp.set("max_price", String(params.max_price));
  return fetchJSON<StockDetail[]>(`/stocks?${sp}`);
};

export const getStockHistory = (ticker: string, period = "1mo") =>
  fetchJSON<StockHistory>(`/stocks/${ticker}/history?period=${period}`);

export const getStockProfile = (ticker: string) =>
  fetchJSON<StockProfile>(`/stocks/${ticker}/profile`);

// News
export const getNews = (params?: { topic?: string; ticker?: string }) => {
  const sp = new URLSearchParams();
  if (params?.topic) sp.set("topic", params.topic);
  if (params?.ticker) sp.set("ticker", params.ticker);
  return fetchJSON<NewsItem[]>(`/news?${sp}`);
};

// Chat
export const askAI = (question: string, language: string, context?: string) =>
  fetchJSON<ChatResponse>("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, language, context }),
  });

export const getChatRemaining = () =>
  fetchJSON<{ remaining: number; daily_limit: number }>("/chat/remaining");

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
