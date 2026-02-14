export interface TopicStock {
  ticker: string;
  company_name: string;
  relevance_note: string;
  current_price: number | null;
  daily_change_pct: number | null;
  previous_close: number | null;
}

export interface TrendTopic {
  slug: string;
  name_en: string;
  name_he: string;
  sector: string;
  sector_en: string;
  momentum_score: number;
  direction: "rising" | "stable" | "falling";
  mention_count_today: number;
  mention_avg_7d: number;
  stocks: TopicStock[];
}

export interface StockDetail {
  ticker: string;
  company_name: string;
  sector: string;
  topic: string;
  topic_slug: string;
  relevance_note: string;
  current_price: number | null;
  daily_change_pct: number | null;
  previous_close: number | null;
}

export interface StockHistory {
  ticker: string;
  period: string;
  data: { date: string; close: number; volume: number }[];
}

export interface CompanyOfficer {
  name: string;
  title: string;
  age: number | null;
  total_pay: number | null;
}

export interface StockProfile {
  ticker: string;
  name: string;
  summary: string;
  sector: string;
  industry: string;
  employees: number | null;
  website: string;
  market_cap: number | null;
  pe_ratio: number | null;
  dividend_yield: number | null;
  fifty_two_week_high: number | null;
  fifty_two_week_low: number | null;
  country: string;
  city: string;
  exchange: string;
  quote_type: string;
  officers: CompanyOfficer[];
  profit_margins: number | null;
  operating_margins: number | null;
  return_on_equity: number | null;
  free_cashflow: number | null;
  total_debt: number | null;
  total_cash: number | null;
  beta: number | null;
  revenue_growth: number | null;
  earnings_growth: number | null;
  recommendation_key: string | null;
  target_mean_price: number | null;
  number_of_analysts: number | null;
}

export interface NewsItem {
  title: string;
  url: string;
  source: string;
  source_type?: "news" | "x" | "google_trends";
  published_at: string;
  image_url: string;
  related_ticker: string | null;
  related_topic: string | null;
  likes?: number;
  retweets?: number;
}

export interface RelatedStock {
  ticker: string;
  company_name: string;
  topic: string;
  relevance_note: string;
  current_price: number | null;
  daily_change_pct: number | null;
}

export interface ChatResponse {
  answer: string;
  suggested_questions: string[];
  questions_remaining: number;
}

export interface Holding {
  ticker: string;
  quantity: number;
  avg_cost: number;
  current_price: number | null;
  market_value: number | null;
  pnl: number | null;
  pnl_pct: number | null;
}

export interface Portfolio {
  session_id: string;
  cash_balance: number;
  total_value: number;
  total_pnl: number;
  holdings: Holding[];
}

export interface TradeHistoryItem {
  ticker: string;
  action: string;
  quantity: number;
  price: number;
  total: number;
  executed_at: string;
}
