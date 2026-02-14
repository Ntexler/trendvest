"use client";
import { useState, useEffect } from "react";
import { useI18n } from "@/i18n/context";
import { getStockProfile, getNews } from "@/lib/api";
import type { StockProfile as StockProfileType, NewsItem } from "@/lib/types";
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
} from "lucide-react";

interface Props {
  ticker: string;
  onClose: () => void;
  isWatched: boolean;
  toggleWatch: () => void;
  onTrade: () => void;
}

type TabKey = "overview" | "management" | "financials" | "analyst";

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

export default function StockProfile({ ticker, onClose, isWatched, toggleWatch, onTrade }: Props) {
  const { t, locale } = useI18n();
  const [profile, setProfile] = useState<StockProfileType | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const [news, setNews] = useState<NewsItem[]>([]);
  const [newsLoading, setNewsLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    getStockProfile(ticker)
      .then(setProfile)
      .catch(console.error)
      .finally(() => setLoading(false));

    setNewsLoading(true);
    getNews({ ticker })
      .then((items) => setNews(items.slice(0, 5)))
      .catch(() => setNews([]))
      .finally(() => setNewsLoading(false));
  }, [ticker]);

  const tabs: { key: TabKey; label: string; icon: React.ReactNode }[] = [
    { key: "overview", label: t("profile.overview"), icon: <Building2 className="w-3.5 h-3.5" /> },
    { key: "management", label: t("profile.management"), icon: <Briefcase className="w-3.5 h-3.5" /> },
    { key: "financials", label: t("profile.financials"), icon: <BarChart3 className="w-3.5 h-3.5" /> },
    { key: "analyst", label: t("profile.analyst"), icon: <TrendingUp className="w-3.5 h-3.5" /> },
  ];

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
                {activeTab === "financials" && <FinancialsTab profile={profile} t={t} />}
                {activeTab === "analyst" && <AnalystTab profile={profile} t={t} locale={locale} />}
              </div>

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
        <div key={i} className="bg-[#1e293b] rounded-lg p-3 flex items-center justify-between">
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
      ))}
    </div>
  );
}

/* ── Financials Tab ── */
function FinancialsTab({ profile, t }: { profile: StockProfileType; t: (k: any) => string }) {
  return (
    <div className="space-y-4">
      {/* Financial Health */}
      <div>
        <h4 className="text-xs font-semibold text-[#94a3b8] mb-2 uppercase tracking-wider">
          {t("profile.financialHealth")}
        </h4>
        <div className="grid grid-cols-2 gap-2">
          <MetricCard label={t("profile.profitMargins")} value={formatPct(profile.profit_margins)} />
          <MetricCard label={t("profile.operatingMargins")} value={formatPct(profile.operating_margins)} />
          <MetricCard label={t("profile.roe")} value={formatPct(profile.return_on_equity)} />
          <MetricCard label={t("profile.beta")} value={profile.beta != null ? profile.beta.toFixed(2) : "N/A"} />
          <MetricCard label={t("profile.freeCashflow")} value={formatLargeNumber(profile.free_cashflow)} />
          <MetricCard label={t("profile.totalDebt")} value={formatLargeNumber(profile.total_debt)} />
          <MetricCard label={t("profile.totalCash")} value={formatLargeNumber(profile.total_cash)} />
        </div>
      </div>

      {/* Growth */}
      <div>
        <h4 className="text-xs font-semibold text-[#94a3b8] mb-2 uppercase tracking-wider">
          {t("profile.growth")}
        </h4>
        <div className="grid grid-cols-2 gap-2">
          <MetricCard
            label={t("profile.revenueGrowth")}
            value={formatPct(profile.revenue_growth)}
            color={profile.revenue_growth != null ? (profile.revenue_growth >= 0 ? "text-green-400" : "text-red-400") : undefined}
          />
          <MetricCard
            label={t("profile.earningsGrowth")}
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
          <MetricCard label={t("profile.peRatio")} value={profile.pe_ratio != null ? profile.pe_ratio.toFixed(2) : "N/A"} />
          <MetricCard label={t("profile.dividendYield")} value={formatPct(profile.dividend_yield)} />
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
}: {
  profile: StockProfileType;
  t: (k: any) => string;
  locale: string;
}) {
  if (!profile.recommendation_key && profile.target_mean_price == null && profile.number_of_analysts == null) {
    return <div className="text-sm text-[#64748b] py-4 text-center">{t("profile.noAnalyst")}</div>;
  }

  const recKey = profile.recommendation_key || "";
  const recColor = recColors[recKey] || "bg-[#334155]";
  const recLabel = recLabels[recKey]?.[locale as "en" | "he"] || recKey.replace("_", " ");

  return (
    <div className="space-y-3">
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
  label: string;
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
