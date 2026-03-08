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
  ExpenseReceipt,
  ExpenseSummary,
  ScanSchedule,
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

// Expenses
export const scanReceipt = (imageData: string, mediaType: string, filename: string) => {
  const sessionId = getSessionId();
  return fetchJSON<{ is_receipt: boolean; receipt_id?: number; data?: Record<string, unknown> }>(
    `/expenses/scan?session_id=${sessionId}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        image_data: imageData,
        media_type: mediaType,
        source_type: "upload",
        original_filename: filename,
      }),
    }
  );
};

export const addManualReceipt = (data: {
  vendor_name: string;
  amount: number;
  currency?: string;
  receipt_date?: string;
  receipt_number?: string;
  description?: string;
  category?: string;
  tax_deductible?: boolean;
}) => {
  const sessionId = getSessionId();
  return fetchJSON<{ receipt_id: number }>(`/expenses/manual?session_id=${sessionId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
};

export const getExpensesList = (filters?: {
  status?: string;
  category?: string;
  tax_deductible?: boolean;
}) => {
  const sessionId = getSessionId();
  const sp = new URLSearchParams({ session_id: sessionId });
  if (filters?.status) sp.set("status", filters.status);
  if (filters?.category) sp.set("category", filters.category);
  if (filters?.tax_deductible !== undefined) sp.set("tax_deductible", String(filters.tax_deductible));
  return fetchJSON<ExpenseReceipt[]>(`/expenses/list?${sp}`);
};

export const getExpenseSummary = () => {
  const sessionId = getSessionId();
  return fetchJSON<ExpenseSummary>(`/expenses/summary?session_id=${sessionId}`);
};

export const updateReceipt = (id: number, data: Record<string, unknown>) => {
  const sessionId = getSessionId();
  return fetchJSON<{ status: string }>(`/expenses/receipt/${id}?session_id=${sessionId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
};

export const deleteReceipt = (id: number) => {
  const sessionId = getSessionId();
  return fetchJSON<{ status: string }>(`/expenses/receipt/${id}?session_id=${sessionId}`, {
    method: "DELETE",
  });
};

export const exportReceipts = (format: "json" | "csv" = "json", taxDeductibleOnly = false) => {
  const sessionId = getSessionId();
  const sp = new URLSearchParams({
    session_id: sessionId,
    format,
    tax_deductible_only: String(taxDeductibleOnly),
  });
  return fetchJSON<{
    format: string;
    count: number;
    total_amount: number;
    tax_deductible_amount: number;
    data?: string;
    receipts?: ExpenseReceipt[];
  }>(`/expenses/export?${sp}`);
};

export const getExpenseCategories = () =>
  fetchJSON<Record<string, string>>("/expenses/categories");

export const testEmailConnection = (data: {
  email_address: string;
  imap_server: string;
  imap_port: number;
  password: string;
}) =>
  fetchJSON<{ success: boolean; message_count?: number; error?: string }>(
    "/expenses/email/test",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }
  );

export const scanEmails = (data: {
  email_address: string;
  imap_server: string;
  imap_port: number;
  password: string;
  days_back?: number;
}) => {
  const sessionId = getSessionId();
  const daysBack = data.days_back || 30;
  return fetchJSON<{
    emails_scanned: number;
    receipts_found: number;
    receipts: Record<string, unknown>[];
  }>(`/expenses/email/scan?session_id=${sessionId}&days_back=${daysBack}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
};

export const getScanSchedule = () => {
  const sessionId = getSessionId();
  return fetchJSON<ScanSchedule>(`/expenses/schedule?session_id=${sessionId}`);
};

export const setScanSchedule = (data: {
  scan_interval_hours: number;
  scan_screenshots: boolean;
  scan_emails: boolean;
  screenshot_folder?: string;
  is_active: boolean;
}) => {
  const sessionId = getSessionId();
  return fetchJSON<{ status: string; next_scan_at?: string }>(
    `/expenses/schedule?session_id=${sessionId}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }
  );
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
