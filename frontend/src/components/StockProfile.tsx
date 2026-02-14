"use client";
import { useState, useEffect } from "react";
import { useI18n } from "@/i18n/context";
import { getStockProfile, getNews, getRelatedStocks, getPeerStocks, getResearch, explainSection } from "@/lib/api";
import type { StockProfile as StockProfileType, NewsItem, RelatedStock, PeerStock, ResearchResult } from "@/lib/types";
import ExplainTooltip from "./ExplainTooltip";
import StockChart from "./StockChart";
import {
  X,
  Star,
  ExternalLink,
  Building2,
  Users,
  Globe,
  BarChart3,
  TrendingUp,
  DollarSign,
  Briefcase,
  Newspaper,
  Loader2,
  Sparkles,
  ArrowRight,
  Search,
  GitCompareArrows,
} from "lucide-react";

interface Props {
  ticker: string;
  onClose: () => void;
  isWatched: boolean;
  toggleWatch: () => void;
  onTrade: () => void;
  onStockClick?: (ticker: string) => void;
}

type TabKey = "overview" | "management" | "financials" | "analyst" | "peers";

function formatMarketCap(n: number | null): string {
  if (!n) return "N/A";
  if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  return `$${n.toLocaleString()}`;
}

function formatLargeNumber(n: number | null | undefined): string {
  if (n == null) return "N/A";
  if (Math.abs(n) >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  return `$${n.toLocaleString()}`;
}

function formatPct(n: number | null | undefined): string {
  if (n == null) return "N/A";
  return `${(n * 100).toFixed(2)}%`;
}

const recColors: Record<string, string> = {
  strong_buy: "bg-green-600",
  buy: "bg-green-500",
  hold: "bg-yellow-500",
  sell: "bg-red-500",
  strong_sell: "bg-red-700",
};

const recLabels: Record<string, { en: string; he: string }> = {
  strong_buy: { en: "Strong Buy", he: "קנייה חזקה" },
  buy: { en: "Buy", he: "קנייה" },
  hold: { en: "Hold", he: "החזקה" },
  sell: { en: "Sell", he: "מכירה" },
  strong_sell: { en: "Strong Sell", he: "מכירה חזקה" },
};

export default function StockProfile({ ticker, onClose, isWatched, toggleWatch, onTrade, onStockClick }: Props) {
  const { t, locale } = useI18n();
  const [profile, setProfile] = useState<StockProfileType | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const [news, setNews] = useState<NewsItem[]>([]);
  const [newsLoading, setNewsLoading] = useState(false);
  const [relatedStocks, setRelatedStocks] = useState<RelatedStock[]>([]);
  const [research, setResearch] = useState<ResearchResult | null>(null);
  const [researchLoading, setResearchLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    getStockProfile(ticker, locale)
      .then(setProfile)
      .catch(console.error)
      .finally(() => setLoading(false));

    setNewsLoading(true);
    getNews({ ticker })
      .then((items) => setNews(items.slice(0, 5)))
      .catch(() => setNews([]))
      .finally(() => setNewsLoading(false));

    getRelatedStocks(ticker)
      .then(setRelatedStocks)
      .catch(() => setRelatedStocks([]));
  }, [ticker, locale]);

  const tabs: { key: TabKey; label: string; icon: React.ReactNode }[] = [
    { key: "overview", label: t("profile.overview"), icon: <Building2 className="w-3.5 h-3.5" /> },
    { key: "management", label: t("profile.management"), icon: <Briefcase className="w-3.5 h-3.5" /> },
    { key: "financials", label: t("profile.financials"), icon: <BarChart3 className="w-3.5 h-3.5" /> },
    { key: "analyst", label: t("profile.analyst"), icon: <TrendingUp className="w-3.5 h-3.5" /> },
    { key: "peers", label: t("profile.peers"), icon: <GitCompareArrows className="w-3.5 h-3.5" /> },
  ];

  const handleResearch = async () => {
    if (research) return;
    setResearchLoading(true);
    try {
      const res = await getResearch(ticker, locale);
      setResearch(res);
    } catch {
      setResearch({ ticker, analysis: locale === "he" ? "שגיאה בטעינת מחקר" : "Error loading research", citations: [], generated_at: "" });
    } finally {
      setResearchLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-end md:items-center justify-center">
      <div className="w-full max-w-lg max-h-[90vh] overflow-y-auto bg-[#111827] rounded-t-2xl md:rounded-2xl border border-[#334155]">
        {/* Header */}
        <div className="sticky top-0 z-10 bg-[#111827] p-4 border-b border-[#334155] flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-bold text-xl text-white">{ticker}</h2>
              {profile?.exchange && (
                <span className="text-[10px] px-1.5 py-0.5 bg-[#1e293b] text-[#94a3b8] rounded font-mono">
                  {profile.exchange}
                </span>
              )}
            </div>
            {profile && <p className="text-sm text-[#94a3b8]">{profile.name}</p>}
          </div>
          <div className="flex items-center gap-2">
            <button onClick={toggleWatch} className="p-2 rounded-lg hover:bg-[#1e293b]">
              <Star
                className={`w-5 h-5 ${
                  isWatched ? "fill-yellow-400 text-yellow-400" : "text-[#94a3b8]"
                }`}
              />
            </button>
            <button onClick={onClose} className="p-2 rounded-lg hover:bg-[#1e293b]">
              <X className="w-5 h-5 text-[#94a3b8]" />
            </button>
          </div>
        </div>

        <div className="p-4 space-y-4">
          {/* Chart */}
          <StockChart ticker={ticker} />

          {/* Action buttons */}
          <div className="flex gap-3">
            <button
              onClick={onTrade}
              className="flex-1 py-2 bg-cyan-500 hover:bg-cyan-600 text-white font-medium rounded-lg transition"
            >
              {t("trade.startTrading")}
            </button>
            <button
              onClick={toggleWatch}
              className="px-4 py-2 bg-[#1e293b] hover:bg-[#334155] rounded-lg transition text-sm"
            >
              {isWatched ? t("stock.removeWatchlist") : t("stock.addWatchlist")}
            </button>
          </div>

          {/* Deep Research Button */}
          <button
            onClick={handleResearch}
            disabled={researchLoading || !!research}
            className="w-full flex items-center justify-center gap-2 py-2 bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/30 text-purple-400 font-medium rounded-lg transition text-sm disabled:opacity-50"
          >
            {researchLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            {t("profile.deepResearch")}
          </button>
          {research && (
            <div className="bg-purple-500/5 border border-purple-500/20 rounded-xl p-4 space-y-3">
              <div className="text-sm text-[#cbd5e1] leading-relaxed whitespace-pre-wrap">{research.analysis}</div>
              {research.citations.length > 0 && (
                <div className="space-y-1">
                  <div className="text-xs text-[#64748b] font-semibold">{t("profile.sources")}</div>
                  {research.citations.map((c, i) => (
                    <a key={i} href={c.url} target="_blank" rel="noopener noreferrer" className="block text-xs text-cyan-400 truncate hover:underline">
                      {c.url}
                    </a>
                  ))}
                </div>
              )}
            </div>
          )}

          {loading ? (
            <div className="text-center py-6 text-[#94a3b8]">{t("general.loading")}</div>
          ) : profile ? (
            <>
              {/* Tabs */}
              <div className="flex gap-1 bg-[#0f172a] rounded-lg p-1">
                {tabs.map((tab) => (
                  <button
                    key={tab.key}
                    onClick={() => setActiveTab(tab.key)}
                    className={`flex-1 flex items-center justify-center gap-1.5 py-2 px-2 rounded-md text-xs font-medium transition ${
                      activeTab === tab.key
                        ? "bg-[#1e293b] text-white"
                        : "text-[#64748b] hover:text-[#94a3b8]"
                    }`}
                  >
                    {tab.icon}
                    <span className="hidden sm:inline">{tab.label}</span>
                  </button>
                ))}
              </div>

              {/* Tab Content */}
              <div className="space-y-4">
                {activeTab === "overview" && <OverviewTab profile={profile} t={t} />}
                {activeTab === "management" && <ManagementTab profile={profile} t={t} locale={locale} />}
                {activeTab === "financials" && <FinancialsTab profile={profile} t={t} ticker={ticker} locale={locale} />}
                {activeTab === "analyst" && <AnalystTab profile={profile} t={t} locale={locale} ticker={ticker} />}
                {activeTab === "peers" && <PeersTab ticker={ticker} t={t} onStockClick={onStockClick} />}
              </div>

              {/* Related Stocks */}
              {relatedStocks.length > 0 && (
                <div className="border-t border-[#334155] pt-4">
                  <h3 className="text-sm font-semibold text-[#94a3b8] mb-3 flex items-center gap-2">
                    <ArrowRight className="w-4 h-4" />
                    {t("profile.relatedStocks")}
                  </h3>
                  <div className="flex gap-2 overflow-x-auto pb-2 -mx-1 px-1">
                    {relatedStocks.map((rs) => (
                      <button
                        key={rs.ticker}
                        onClick={() => onStockClick?.(rs.ticker)}
                        className="flex-shrink-0 bg-[#1e293b] hover:bg-[#263548] rounded-lg p-3 text-start transition min-w-[120px]"
                      >
                        <div className="font-mono text-sm font-bold text-cyan-400">{rs.ticker}</div>
                        {rs.current_price != null && (
                          <div className="text-xs text-white tabular-nums mt-1">${rs.current_price.toFixed(2)}</div>
                        )}
                        {rs.daily_change_pct != null && (
                          <div className={`text-xs tabular-nums ${rs.daily_change_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
                            {rs.daily_change_pct >= 0 ? "+" : ""}{rs.daily_change_pct.toFixed(2)}%
                          </div>
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Company News */}
              <div className="border-t border-[#334155] pt-4">
                <h3 className="text-sm font-semibold text-[#94a3b8] mb-3 flex items-center gap-2">
                  <Newspaper className="w-4 h-4" />
                  {t("profile.companyNews")}
                </h3>
                {newsLoading ? (
                  <div className="text-xs text-[#64748b] py-2">{t("general.loading")}</div>
                ) : news.length > 0 ? (
                  <div className="space-y-2">
                    {news.map((item, i) => (
                      <a
                        key={i}
                        href={item.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block bg-[#1e293b] rounded-lg p-3 hover:bg-[#263548] transition"
                      >
                        <div className="text-sm text-white line-clamp-2">{item.title}</div>
                        <div className="flex items-center gap-2 mt-1 text-xs text-[#64748b]">
                          <span>{item.source}</span>
                          <span>{new Date(item.published_at).toLocaleDateString()}</span>
                        </div>
                      </a>
                    ))}
                  </div>
                ) : (
                  <div className="text-xs text-[#64748b] py-2">{t("profile.noNews")}</div>
                )}
              </div>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}

/* ── Overview Tab ── */
function OverviewTab({ profile, t }: { profile: StockProfileType; t: (k: any) => string }) {
  return (
    <div className="space-y-4">
      {profile.summary && (
        <div>
          <h3 className="text-sm font-semibold text-[#94a3b8] mb-2">{t("stock.readMore")}</h3>
          <p className="text-sm text-[#cbd5e1] leading-relaxed">
            {profile.summary.length > 500 ? profile.summary.slice(0, 500) + "..." : profile.summary}
          </p>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        {profile.sector && (
          <InfoCard icon={<Building2 className="w-3 h-3" />} label={t("stock.sector")} value={profile.sector} />
        )}
        {profile.industry && (
          <InfoCard icon={<BarChart3 className="w-3 h-3" />} label={t("stock.industry")} value={profile.industry} />
        )}
        <InfoCard label={t("stock.marketCap")} value={formatMarketCap(profile.market_cap)} tabular />
        {profile.employees && (
          <InfoCard
            icon={<Users className="w-3 h-3" />}
            label={t("stock.employees")}
            value={profile.employees.toLocaleString()}
            tabular
          />
        )}
      </div>

      {profile.website && (
        <a
          href={profile.website}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 text-sm text-cyan-400 hover:text-cyan-300"
        >
          <Globe className="w-4 h-4" />
          {profile.website.replace(/^https?:\/\//, "")}
          <ExternalLink className="w-3 h-3" />
        </a>
      )}
    </div>
  );
}

/* ── Management Tab ── */
function ManagementTab({
  profile,
  t,
  locale,
}: {
  profile: StockProfileType;
  t: (k: any) => string;
  locale: string;
}) {
  if (!profile.officers || profile.officers.length === 0) {
    return <div className="text-sm text-[#64748b] py-4 text-center">{t("profile.noOfficers")}</div>;
  }
  return (
    <div className="space-y-2">
      {profile.officers.map((officer, i) => (
        <div key={i} className="bg-[#1e293b] rounded-lg p-3">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-medium text-white">{officer.name}</div>
              <div className="text-xs text-[#94a3b8]">{officer.title}</div>
            </div>
            {officer.age && (
              <div className="text-xs text-[#64748b]">
                {t("profile.age")}: {officer.age}
              </div>
            )}
          </div>
          {officer.bio && (
            <p className="text-xs text-[#cbd5e1] mt-2 leading-relaxed border-t border-[#334155] pt-2">
              {officer.bio}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

/* ── Financials Tab ── */
function FinancialsTab({
  profile,
  t,
  ticker,
  locale,
}: {
  profile: StockProfileType;
  t: (k: any) => string;
  ticker: string;
  locale: string;
}) {
  const [aiExplanation, setAiExplanation] = useState<string | null>(null);
  const [aiLoading, setAiLoading] = useState(false);

  const handleExplain = async () => {
    if (aiExplanation) {
      setAiExplanation(null);
      return;
    }
    setAiLoading(true);
    try {
      const data: Record<string, unknown> = {
        profit_margins: profile.profit_margins,
        operating_margins: profile.operating_margins,
        return_on_equity: profile.return_on_equity,
        beta: profile.beta,
        free_cashflow: profile.free_cashflow,
        total_debt: profile.total_debt,
        total_cash: profile.total_cash,
        revenue_growth: profile.revenue_growth,
        earnings_growth: profile.earnings_growth,
        pe_ratio: profile.pe_ratio,
        dividend_yield: profile.dividend_yield,
      };
      const res = await explainSection(ticker, "financials", data, locale);
      setAiExplanation(res.explanation);
    } catch {
      setAiExplanation(locale === "he" ? "שגיאה בטעינת ההסבר" : "Error loading explanation");
    } finally {
      setAiLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* AI Explain button */}
      <button
        onClick={handleExplain}
        disabled={aiLoading}
        className="flex items-center gap-2 px-3 py-1.5 bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 rounded-lg text-xs text-cyan-400 transition disabled:opacity-50"
      >
        {aiLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
        {t("explain.explainSection")}
      </button>
      {aiExplanation && (
        <div className="bg-cyan-500/5 border border-cyan-500/20 rounded-lg p-3 space-y-2">
          <p className="text-xs text-[#cbd5e1] leading-relaxed">{aiExplanation}</p>
          <p className="text-[10px] text-[#64748b]">{t("explain.aiDisclaimer")}</p>
        </div>
      )}

      {/* Financial Health */}
      <div>
        <h4 className="text-xs font-semibold text-[#94a3b8] mb-2 uppercase tracking-wider">
          {t("profile.financialHealth")}
        </h4>
        <div className="grid grid-cols-2 gap-2">
          <MetricCard label={<ExplainTooltip term="Profit Margins">{t("profile.profitMargins")}</ExplainTooltip>} value={formatPct(profile.profit_margins)} />
          <MetricCard label={<ExplainTooltip term="Operating Margins">{t("profile.operatingMargins")}</ExplainTooltip>} value={formatPct(profile.operating_margins)} />
          <MetricCard label={<ExplainTooltip term="Return on Equity">{t("profile.roe")}</ExplainTooltip>} value={formatPct(profile.return_on_equity)} />
          <MetricCard label={<ExplainTooltip term="Beta">{t("profile.beta")}</ExplainTooltip>} value={profile.beta != null ? profile.beta.toFixed(2) : "N/A"} />
          <MetricCard label={<ExplainTooltip term="Free Cashflow">{t("profile.freeCashflow")}</ExplainTooltip>} value={formatLargeNumber(profile.free_cashflow)} />
          <MetricCard label={<ExplainTooltip term="Total Debt">{t("profile.totalDebt")}</ExplainTooltip>} value={formatLargeNumber(profile.total_debt)} />
          <MetricCard label={<ExplainTooltip term="Total Cash">{t("profile.totalCash")}</ExplainTooltip>} value={formatLargeNumber(profile.total_cash)} />
        </div>
      </div>

      {/* Growth */}
      <div>
        <h4 className="text-xs font-semibold text-[#94a3b8] mb-2 uppercase tracking-wider">
          {t("profile.growth")}
        </h4>
        <div className="grid grid-cols-2 gap-2">
          <MetricCard
            label={<ExplainTooltip term="Revenue Growth">{t("profile.revenueGrowth")}</ExplainTooltip>}
            value={formatPct(profile.revenue_growth)}
            color={profile.revenue_growth != null ? (profile.revenue_growth >= 0 ? "text-green-400" : "text-red-400") : undefined}
          />
          <MetricCard
            label={<ExplainTooltip term="Earnings Growth">{t("profile.earningsGrowth")}</ExplainTooltip>}
            value={formatPct(profile.earnings_growth)}
            color={profile.earnings_growth != null ? (profile.earnings_growth >= 0 ? "text-green-400" : "text-red-400") : undefined}
          />
        </div>
      </div>

      {/* Valuation */}
      <div>
        <h4 className="text-xs font-semibold text-[#94a3b8] mb-2 uppercase tracking-wider">
          {t("profile.valuation")}
        </h4>
        <div className="grid grid-cols-2 gap-2">
          <MetricCard label={<ExplainTooltip term="P/E Ratio">{t("profile.peRatio")}</ExplainTooltip>} value={profile.pe_ratio != null ? profile.pe_ratio.toFixed(2) : "N/A"} />
          <MetricCard label={<ExplainTooltip term="Dividend Yield">{t("profile.dividendYield")}</ExplainTooltip>} value={formatPct(profile.dividend_yield)} />
          <div className="col-span-2 bg-[#0f172a] rounded-lg p-3">
            <div className="text-xs text-[#64748b] mb-1">{t("profile.52wRange")}</div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-red-400">${profile.fifty_two_week_low?.toFixed(2) ?? "N/A"}</span>
              <div className="flex-1 mx-3 h-1 bg-[#1e293b] rounded-full relative">
                {profile.fifty_two_week_low != null && profile.fifty_two_week_high != null && profile.market_cap != null && (
                  <div className="absolute top-1/2 -translate-y-1/2 w-2 h-2 bg-cyan-400 rounded-full" style={{ left: "50%" }} />
                )}
              </div>
              <span className="text-green-400">${profile.fifty_two_week_high?.toFixed(2) ?? "N/A"}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Analyst Tab ── */
function AnalystTab({
  profile,
  t,
  locale,
  ticker,
}: {
  profile: StockProfileType;
  t: (k: any) => string;
  locale: string;
  ticker: string;
}) {
  const [aiExplanation, setAiExplanation] = useState<string | null>(null);
  const [aiLoading, setAiLoading] = useState(false);

  if (!profile.recommendation_key && profile.target_mean_price == null && profile.number_of_analysts == null) {
    return <div className="text-sm text-[#64748b] py-4 text-center">{t("profile.noAnalyst")}</div>;
  }

  const recKey = profile.recommendation_key || "";
  const recColor = recColors[recKey] || "bg-[#334155]";
  const recLabel = recLabels[recKey]?.[locale as "en" | "he"] || recKey.replace("_", " ");

  const handleExplain = async () => {
    if (aiExplanation) {
      setAiExplanation(null);
      return;
    }
    setAiLoading(true);
    try {
      const data: Record<string, unknown> = {
        recommendation: profile.recommendation_key,
        target_mean_price: profile.target_mean_price,
        number_of_analysts: profile.number_of_analysts,
      };
      const res = await explainSection(ticker, "analyst", data, locale);
      setAiExplanation(res.explanation);
    } catch {
      setAiExplanation(locale === "he" ? "שגיאה בטעינת ההסבר" : "Error loading explanation");
    } finally {
      setAiLoading(false);
    }
  };

  return (
    <div className="space-y-3">
      {/* AI Explain button */}
      <button
        onClick={handleExplain}
        disabled={aiLoading}
        className="flex items-center gap-2 px-3 py-1.5 bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 rounded-lg text-xs text-cyan-400 transition disabled:opacity-50"
      >
        {aiLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
        {t("explain.explainSection")}
      </button>
      {aiExplanation && (
        <div className="bg-cyan-500/5 border border-cyan-500/20 rounded-lg p-3 space-y-2">
          <p className="text-xs text-[#cbd5e1] leading-relaxed">{aiExplanation}</p>
          <p className="text-[10px] text-[#64748b]">{t("explain.aiDisclaimer")}</p>
        </div>
      )}

      {/* Recommendation badge */}
      {profile.recommendation_key && (
        <div className="flex items-center gap-3 bg-[#1e293b] rounded-lg p-4">
          <div className="flex-1">
            <div className="text-xs text-[#64748b] mb-1">{t("profile.recommendation")}</div>
            <span className={`inline-block px-3 py-1 rounded-full text-sm font-semibold text-white ${recColor}`}>
              {recLabel}
            </span>
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        {profile.target_mean_price != null && (
          <div className="bg-[#1e293b] rounded-lg p-3">
            <div className="flex items-center gap-2 text-xs text-[#64748b] mb-1">
              <DollarSign className="w-3 h-3" />
              {t("profile.targetPrice")}
            </div>
            <div className="text-lg font-semibold text-white tabular-nums">
              ${profile.target_mean_price.toFixed(2)}
            </div>
          </div>
        )}
        {profile.number_of_analysts != null && (
          <div className="bg-[#1e293b] rounded-lg p-3">
            <div className="flex items-center gap-2 text-xs text-[#64748b] mb-1">
              <Users className="w-3 h-3" />
              {t("profile.analystCount")}
            </div>
            <div className="text-lg font-semibold text-white tabular-nums">
              {profile.number_of_analysts}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Peers Tab ── */
function PeersTab({
  ticker,
  t,
  onStockClick,
}: {
  ticker: string;
  t: (k: any) => string;
  onStockClick?: (ticker: string) => void;
}) {
  const [peers, setPeers] = useState<PeerStock[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getPeerStocks(ticker)
      .then(setPeers)
      .catch(() => setPeers([]))
      .finally(() => setLoading(false));
  }, [ticker]);

  if (loading) return <div className="text-center py-6 text-[#94a3b8]">{t("general.loading")}</div>;
  if (peers.length === 0) return <div className="text-sm text-[#64748b] py-4 text-center">{t("profile.noPeers")}</div>;

  return (
    <div className="space-y-2">
      {/* Header row */}
      <div className="grid grid-cols-4 gap-2 text-[10px] text-[#64748b] uppercase tracking-wider px-3 pb-1">
        <div>{t("profile.peerTicker")}</div>
        <div className="text-end">{t("stock.price")}</div>
        <div className="text-end">P/E</div>
        <div className="text-end">{t("stock.change")}</div>
      </div>
      {peers.map((peer) => (
        <button
          key={peer.ticker}
          onClick={() => onStockClick?.(peer.ticker)}
          className="w-full grid grid-cols-4 gap-2 items-center bg-[#1e293b] rounded-lg p-3 hover:bg-[#263548] transition text-start"
        >
          <div>
            <div className="font-mono text-sm font-bold text-cyan-400">{peer.ticker}</div>
            <div className="text-[10px] text-[#94a3b8] truncate">{peer.company_name}</div>
          </div>
          <div className="text-end text-sm text-white tabular-nums">
            {peer.current_price != null ? `$${peer.current_price.toFixed(2)}` : "N/A"}
          </div>
          <div className="text-end text-sm text-white tabular-nums">
            {peer.pe_ratio != null ? peer.pe_ratio.toFixed(1) : "N/A"}
          </div>
          <div className={`text-end text-sm tabular-nums ${
            peer.daily_change_pct != null && peer.daily_change_pct >= 0 ? "text-green-400" : "text-red-400"
          }`}>
            {peer.daily_change_pct != null ? `${peer.daily_change_pct >= 0 ? "+" : ""}${peer.daily_change_pct.toFixed(2)}%` : "N/A"}
          </div>
        </button>
      ))}

      {/* Additional metrics for first 3 peers */}
      {peers.filter(p => p.market_cap || p.institutional_pct || p.revenue_growth).length > 0 && (
        <div className="border-t border-[#334155] pt-3 mt-3">
          <h4 className="text-xs font-semibold text-[#94a3b8] mb-2">{t("profile.peerMetrics")}</h4>
          <div className="space-y-2">
            {peers.slice(0, 5).map((peer) => (
              <div key={`metrics-${peer.ticker}`} className="bg-[#0f172a] rounded-lg p-3">
                <div className="font-mono text-xs text-cyan-400 mb-2">{peer.ticker}</div>
                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div>
                    <div className="text-[#64748b]">{t("stock.marketCap")}</div>
                    <div className="text-white tabular-nums">{formatMarketCap(peer.market_cap)}</div>
                  </div>
                  <div>
                    <div className="text-[#64748b]">{t("profile.profitMargins")}</div>
                    <div className="text-white tabular-nums">{peer.profit_margins != null ? `${(peer.profit_margins * 100).toFixed(1)}%` : "N/A"}</div>
                  </div>
                  <div>
                    <div className="text-[#64748b]">{t("profile.revenueGrowth")}</div>
                    <div className={`tabular-nums ${peer.revenue_growth != null && peer.revenue_growth >= 0 ? "text-green-400" : "text-red-400"}`}>
                      {peer.revenue_growth != null ? `${(peer.revenue_growth * 100).toFixed(1)}%` : "N/A"}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Shared Components ── */
function InfoCard({
  icon,
  label,
  value,
  tabular,
}: {
  icon?: React.ReactNode;
  label: string;
  value: string;
  tabular?: boolean;
}) {
  return (
    <div className="bg-[#1e293b] rounded-lg p-3">
      <div className="flex items-center gap-2 text-xs text-[#94a3b8] mb-1">
        {icon}
        {label}
      </div>
      <div className={`text-sm text-white ${tabular ? "tabular-nums" : ""}`}>{value}</div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  color,
}: {
  label: React.ReactNode;
  value: string;
  color?: string;
}) {
  return (
    <div className="bg-[#0f172a] rounded-lg p-3">
      <div className="text-xs text-[#64748b] mb-1">{label}</div>
      <div className={`text-sm font-medium tabular-nums ${color || "text-white"}`}>{value}</div>
    </div>
  );
}
