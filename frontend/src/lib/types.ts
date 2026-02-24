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
  bio: string;
}

export interface PeerStock {
  ticker: string;
  company_name: string;
  current_price: number | null;
  daily_change_pct: number | null;
  market_cap: number | null;
  pe_ratio: number | null;
  beta: number | null;
  dividend_yield: number | null;
  profit_margins: number | null;
  revenue_growth: number | null;
  institutional_pct: number | null;
  short_ratio: number | null;
}

export interface ResearchResult {
  ticker: string;
  analysis: string;
  citations: { url: string }[];
  generated_at: string;
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
  source_type?: "news" | "x" | "google_trends" | "il_news";
  source_key?: string;
  published_at: string;
  image_url: string;
  description?: string;
  related_ticker: string | null;
  related_topic: string | null;
  language?: string;
  likes?: number;
  retweets?: number;
}

// ── Feed Types ──

export interface MomentumHistoryPoint {
  date: string;
  mentions: number;
}

export interface FeedTopicInfo {
  slug: string;
  name_en: string;
  name_he: string;
  sector: string;
  sector_en: string;
  momentum_score: number;
  direction: "rising" | "stable" | "falling";
  mention_count_today: number;
  mention_avg_7d: number;
  updated_at: string | null;
}

export interface FeedStock {
  ticker: string;
  company_name: string;
  relevance_note: string;
  current_price: number | null;
  daily_change_pct: number | null;
}

export interface FeedItem {
  topic: FeedTopicInfo;
  momentum_history: MomentumHistoryPoint[];
  stocks: FeedStock[];
  top_article: NewsItem | null;
  articles: NewsItem[];
  il_news: NewsItem[];
  global_news?: NewsItem[];
  sec_filings?: { title: string; url: string; filing_type?: string; ticker?: string }[];
}

export interface PodcastEpisode {
  podcast_key: string;
  podcast_name: string;
  title: string;
  url: string;
  audio_url: string;
  published_at: string;
  description: string;
  duration: string;
  image_url: string;
}

export interface InstitutionalItem {
  title: string;
  url: string;
  source: string;
  source_type: string;
  category?: string;
  region?: string;
  published_at?: string;
  description?: string;
  language?: string;
}

export interface BlogPost {
  title: string;
  url: string;
  source: string;
  source_type: string;
  source_key?: string;
  published_at?: string;
  description?: string;
  language?: string;
}

export interface TrendingTopic {
  topic: string;
  type: "term" | "phrase";
  mention_count: number;
  source_count: number;
  sources: string[];
  score: number;
  articles: { title: string; url: string; source: string; source_type: string; published_at?: string }[];
}

export interface TranslatedArticle {
  translated_title: string;
  summary: string;
  key_points: string[];
  language: string;
  source: string;
  url: string;
  ai_generated: boolean;
}

export interface Newsletter {
  newsletter: string;
  trending_topics: TrendingTopic[];
  top_articles: { title: string; url: string; source: string }[];
  market: string;
  language: string;
  generated_at: string;
  ai_generated: boolean;
  source_count: number;
  total_mentions: number;
}

export interface UnifiedFeed {
  feed: FeedItem[];
  il_news_general: NewsItem[];
  global_news_general?: NewsItem[];
  podcasts: PodcastEpisode[];
  institutional?: InstitutionalItem[];
  blogs?: BlogPost[];
  market_filter?: string;
  generated_at: string;
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
