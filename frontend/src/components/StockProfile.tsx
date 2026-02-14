"use client";
import { useState, useEffect } from "react";
import { useI18n } from "@/i18n/context";
import { getStockProfile } from "@/lib/api";
import type { StockProfile as StockProfileType } from "@/lib/types";
import StockChart from "./StockChart";
import {
  X,
  Star,
  ExternalLink,
  Building2,
  Users,
  Globe,
  BarChart3,
} from "lucide-react";

interface Props {
  ticker: string;
  onClose: () => void;
  isWatched: boolean;
  toggleWatch: () => void;
  onTrade: () => void;
}

function formatMarketCap(n: number | null): string {
  if (!n) return "N/A";
  if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  return `$${n.toLocaleString()}`;
}

export default function StockProfile({ ticker, onClose, isWatched, toggleWatch, onTrade }: Props) {
  const { t } = useI18n();
  const [profile, setProfile] = useState<StockProfileType | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getStockProfile(ticker)
      .then(setProfile)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [ticker]);

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-end md:items-center justify-center">
      <div className="w-full max-w-lg max-h-[90vh] overflow-y-auto bg-[#111827] rounded-t-2xl md:rounded-2xl border border-[#334155]">
        {/* Header */}
        <div className="sticky top-0 bg-[#111827] p-4 border-b border-[#334155] flex items-center justify-between">
          <div>
            <h2 className="font-bold text-xl text-white">{ticker}</h2>
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

        <div className="p-4 space-y-6">
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

          {/* Profile Info */}
          {loading ? (
            <div className="text-center py-6 text-[#94a3b8]">{t("general.loading")}</div>
          ) : profile ? (
            <div className="space-y-4">
              {profile.summary && (
                <div>
                  <h3 className="text-sm font-semibold text-[#94a3b8] mb-2">{t("stock.readMore")}</h3>
                  <p className="text-sm text-[#cbd5e1] leading-relaxed">
                    {profile.summary.length > 500
                      ? profile.summary.slice(0, 500) + "..."
                      : profile.summary}
                  </p>
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                {profile.sector && (
                  <div className="bg-[#1e293b] rounded-lg p-3">
                    <div className="flex items-center gap-2 text-xs text-[#94a3b8] mb-1">
                      <Building2 className="w-3 h-3" />
                      {t("stock.sector")}
                    </div>
                    <div className="text-sm text-white">{profile.sector}</div>
                  </div>
                )}
                {profile.industry && (
                  <div className="bg-[#1e293b] rounded-lg p-3">
                    <div className="flex items-center gap-2 text-xs text-[#94a3b8] mb-1">
                      <BarChart3 className="w-3 h-3" />
                      {t("stock.industry")}
                    </div>
                    <div className="text-sm text-white">{profile.industry}</div>
                  </div>
                )}
                <div className="bg-[#1e293b] rounded-lg p-3">
                  <div className="text-xs text-[#94a3b8] mb-1">{t("stock.marketCap")}</div>
                  <div className="text-sm text-white tabular-nums">
                    {formatMarketCap(profile.market_cap)}
                  </div>
                </div>
                {profile.employees && (
                  <div className="bg-[#1e293b] rounded-lg p-3">
                    <div className="flex items-center gap-2 text-xs text-[#94a3b8] mb-1">
                      <Users className="w-3 h-3" />
                      {t("stock.employees")}
                    </div>
                    <div className="text-sm text-white tabular-nums">
                      {profile.employees.toLocaleString()}
                    </div>
                  </div>
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
          ) : null}
        </div>
      </div>
    </div>
  );
}
