"use client";
import { useState, useEffect } from "react";
import { useI18n } from "@/i18n/context";
import { getAgentDashboard, analyzeTickerAgent, triggerAgentLearning } from "@/lib/api";
import type { AgentDashboard as AgentDashboardType, AgentAnalysis } from "@/lib/types";
import {
  Brain,
  TrendingUp,
  TrendingDown,
  Target,
  Activity,
  BarChart3,
  Loader2,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  Search,
} from "lucide-react";

interface Props {
  onStockClick?: (ticker: string) => void;
}

const SIGNAL_LABELS: Record<string, { he: string; en: string; icon: string }> = {
  momentum: { he: "מומנטום", en: "Momentum", icon: "📈" },
  sentiment: { he: "סנטימנט", en: "Sentiment", icon: "💬" },
  user_herd: { he: "עדר משתמשים", en: "User Herd", icon: "👥" },
  technical: { he: "טכני", en: "Technical", icon: "📊" },
  macro: { he: "מאקרו", en: "Macro", icon: "🏛️" },
  supply_chain: { he: "שרשרת אספקה", en: "Supply Chain", icon: "🔗" },
  cross_reference: { he: "הצלבה", en: "Cross-Ref", icon: "🔀" },
  nlp_sentiment: { he: "NLP סנטימנט", en: "NLP Sentiment", icon: "🧠" },
};

export default function AgentDashboard({ onStockClick }: Props) {
  const { locale } = useI18n();
  const [data, setData] = useState<AgentDashboardType | null>(null);
  const [loading, setLoading] = useState(true);
  const [analysisInput, setAnalysisInput] = useState("");
  const [analysis, setAnalysis] = useState<AgentAnalysis | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [showWeights, setShowWeights] = useState(false);
  const [showTrades, setShowTrades] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const d = await getAgentDashboard();
      setData(d);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleAnalyze = async () => {
    if (!analysisInput.trim()) return;
    setAnalyzing(true);
    setAnalysis(null);
    try {
      const result = await analyzeTickerAgent(analysisInput.trim().toUpperCase());
      setAnalysis(result);
    } catch (e) {
      console.error(e);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleLearn = async () => {
    try {
      await triggerAgentLearning();
      await load();
    } catch (e) {
      console.error(e);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-[#64748b]">
        <Loader2 className="w-5 h-5 animate-spin me-2" />
        {locale === "he" ? "טוען סוכן AI..." : "Loading AI Agent..."}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="text-center py-12 text-[#64748b]">
        {locale === "he" ? "הסוכן עדיין לא פעיל" : "Agent not active yet"}
      </div>
    );
  }

  const pnlColor = data.stats.cumulative_pnl >= 0 ? "text-green-400" : "text-red-400";

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Brain className="w-5 h-5 text-violet-400" />
          <h2 className="text-lg font-bold text-white">
            {locale === "he" ? "סוכן AI" : "AI Agent"}
          </h2>
          <span className="px-2 py-0.5 rounded-full bg-violet-500/20 text-violet-400 text-[10px] font-bold">
            BETA
          </span>
        </div>
        <button onClick={handleLearn} className="p-1.5 rounded-lg hover:bg-[#1e293b] transition text-[#64748b] hover:text-violet-400" title={locale === "he" ? "למידה + עדכון" : "Learn + Update"}>
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Disclaimer */}
      <div className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/20">
        <div className="flex items-start gap-2">
          <AlertTriangle className="w-3.5 h-3.5 text-amber-400 mt-0.5 shrink-0" />
          <p className="text-[10px] text-amber-300 leading-relaxed">
            {locale === "he"
              ? "סוכן AI ניסיוני — סוחר בכסף דמה בלבד. לא ניבוי שוק, לא ייעוץ השקעות. הסוכן לומד מטעויות ומשפר את עצמו לאורך זמן."
              : "Experimental AI agent — paper money only. Not market prediction, not investment advice. The agent learns from mistakes and improves over time."}
          </p>
        </div>
      </div>

      {/* Portfolio Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        <StatCard
          label={locale === "he" ? "שווי תיק" : "Portfolio"}
          value={`$${data.portfolio.total_value.toLocaleString()}`}
          subValue={`${data.stats.cumulative_pnl >= 0 ? "+" : ""}${data.stats.cumulative_pnl_pct.toFixed(2)}%`}
          subColor={pnlColor}
        />
        <StatCard
          label={locale === "he" ? "מזומן" : "Cash"}
          value={`$${data.portfolio.cash.toLocaleString()}`}
        />
        <StatCard
          label={locale === "he" ? "אחוז הצלחה" : "Win Rate"}
          value={`${data.stats.win_rate}%`}
          subValue={`${data.stats.wins}W / ${data.stats.losses}L`}
        />
        <StatCard
          label={locale === "he" ? "פוזיציות" : "Positions"}
          value={`${data.portfolio.open_positions}`}
          subValue={`/ ${10} max`}
        />
      </div>

      {/* Holdings */}
      {data.holdings.length > 0 && (
        <section className="bg-[#111827] rounded-xl border border-[#334155] p-3">
          <h3 className="text-xs font-semibold text-[#94a3b8] uppercase mb-2 flex items-center gap-1.5">
            <Target className="w-3.5 h-3.5" />
            {locale === "he" ? "אחזקות פעילות" : "Active Holdings"}
          </h3>
          <div className="space-y-1.5">
            {data.holdings.map((h) => (
              <button
                key={h.ticker}
                onClick={() => onStockClick?.(h.ticker)}
                className="w-full flex items-center justify-between p-2 rounded-lg bg-[#0f172a] hover:bg-[#1e293b] transition text-start"
              >
                <div>
                  <span className="text-sm font-mono font-bold text-cyan-400">{h.ticker}</span>
                  <span className="text-[10px] text-[#64748b] ms-2">
                    {h.quantity} × ${h.avg_cost.toFixed(2)}
                  </span>
                </div>
                <div className="text-end">
                  <span className="text-sm font-medium text-white">${h.current_price.toFixed(2)}</span>
                  <span className={`text-xs ms-2 font-medium ${h.pnl_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
                    {h.pnl_pct >= 0 ? "+" : ""}{h.pnl_pct.toFixed(1)}%
                  </span>
                </div>
              </button>
            ))}
          </div>
        </section>
      )}

      {/* Signal Weights — Collapsible */}
      <section className="bg-[#111827] rounded-xl border border-[#334155] overflow-hidden">
        <button
          onClick={() => setShowWeights(!showWeights)}
          className="w-full flex items-center justify-between p-3 hover:bg-[#1e293b]/50 transition"
        >
          <h3 className="text-xs font-semibold text-[#94a3b8] uppercase flex items-center gap-1.5">
            <BarChart3 className="w-3.5 h-3.5" />
            {locale === "he" ? "משקלות אותות (למידה עצמית)" : "Signal Weights (Self-Learning)"}
          </h3>
          {showWeights ? <ChevronUp className="w-4 h-4 text-[#64748b]" /> : <ChevronDown className="w-4 h-4 text-[#64748b]" />}
        </button>
        {showWeights && (
          <div className="px-3 pb-3 space-y-2">
            {data.signal_weights.map((w) => {
              const label = SIGNAL_LABELS[w.type];
              const barWidth = Math.min(100, w.weight * 50); // 2.0 = 100%
              return (
                <div key={w.type}>
                  <div className="flex items-center justify-between mb-0.5">
                    <span className="text-xs text-white">
                      {label?.icon} {locale === "he" ? label?.he : label?.en || w.type}
                    </span>
                    <span className="text-[10px] text-[#64748b]">
                      {w.predictions > 0
                        ? `${w.accuracy.toFixed(0)}% (${w.correct}/${w.predictions})`
                        : locale === "he" ? "ממתין לנתונים" : "Awaiting data"}
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-[#1e293b] overflow-hidden">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-violet-500 to-cyan-500 transition-all duration-500"
                      style={{ width: `${barWidth}%` }}
                    />
                  </div>
                </div>
              );
            })}
            <p className="text-[9px] text-[#475569] mt-1">
              {locale === "he"
                ? "משקלות מתעדכנים אוטומטית לפי הצלחת כל אות. מינימום 10 תחזיות לפני שינוי."
                : "Weights auto-adjust based on signal accuracy. Minimum 10 predictions before changing."}
            </p>
          </div>
        )}
      </section>

      {/* Recent Trades — Collapsible */}
      <section className="bg-[#111827] rounded-xl border border-[#334155] overflow-hidden">
        <button
          onClick={() => setShowTrades(!showTrades)}
          className="w-full flex items-center justify-between p-3 hover:bg-[#1e293b]/50 transition"
        >
          <h3 className="text-xs font-semibold text-[#94a3b8] uppercase flex items-center gap-1.5">
            <Activity className="w-3.5 h-3.5" />
            {locale === "he" ? `עסקאות אחרונות (${data.stats.total_trades})` : `Recent Trades (${data.stats.total_trades})`}
          </h3>
          {showTrades ? <ChevronUp className="w-4 h-4 text-[#64748b]" /> : <ChevronDown className="w-4 h-4 text-[#64748b]" />}
        </button>
        {showTrades && (
          <div className="px-3 pb-3 space-y-1.5">
            {data.recent_trades.length === 0 ? (
              <p className="text-xs text-[#64748b] text-center py-4">
                {locale === "he" ? "אין עסקאות עדיין" : "No trades yet"}
              </p>
            ) : (
              data.recent_trades.map((t, i) => (
                <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-[#0f172a] text-xs">
                  <div className="flex items-center gap-2">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                      t.action === "buy"
                        ? "bg-green-500/20 text-green-400"
                        : "bg-red-500/20 text-red-400"
                    }`}>
                      {t.action === "buy" ? (locale === "he" ? "קנייה" : "BUY") : (locale === "he" ? "מכירה" : "SELL")}
                    </span>
                    <button onClick={() => onStockClick?.(t.ticker)} className="font-mono text-cyan-400 hover:underline">
                      {t.ticker}
                    </button>
                    <span className="text-[#64748b]">×{t.quantity}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[#94a3b8]">${t.entry_price.toFixed(2)}</span>
                    {t.pnl_pct !== null && (
                      <span className={`font-medium ${t.pnl_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
                        {t.pnl_pct >= 0 ? "+" : ""}{t.pnl_pct.toFixed(1)}%
                      </span>
                    )}
                    {(t.outcome_1d !== null || t.outcome_7d !== null || t.outcome_30d !== null) && (
                      <span className="text-[9px] text-[#475569]">
                        {t.outcome_1d !== null && <span className={t.outcome_1d >= 0 ? "text-green-600" : "text-red-600"}>1d:{t.outcome_1d > 0 ? "+" : ""}{t.outcome_1d.toFixed(1)}% </span>}
                        {t.outcome_7d !== null && <span className={t.outcome_7d >= 0 ? "text-green-600" : "text-red-600"}>7d:{t.outcome_7d > 0 ? "+" : ""}{t.outcome_7d.toFixed(1)}% </span>}
                        {t.outcome_30d !== null && <span className={t.outcome_30d >= 0 ? "text-green-600" : "text-red-600"}>30d:{t.outcome_30d > 0 ? "+" : ""}{t.outcome_30d.toFixed(1)}%</span>}
                      </span>
                    )}
                    <span className={`w-1.5 h-1.5 rounded-full ${t.is_open ? "bg-green-400" : "bg-[#475569]"}`} />
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </section>

      {/* Performance vs Benchmark */}
      {data.performance.length > 0 && (
        <section className="bg-[#111827] rounded-xl border border-[#334155] p-3">
          <h3 className="text-xs font-semibold text-[#94a3b8] uppercase mb-2 flex items-center gap-1.5">
            <TrendingUp className="w-3.5 h-3.5" />
            {locale === "he" ? "ביצועים מול SPY" : "Performance vs SPY"}
          </h3>
          <div className="space-y-1">
            {data.performance.slice(0, 10).map((p) => (
              <div key={p.date} className="flex items-center justify-between text-xs py-1 border-b border-[#1e293b] last:border-0">
                <span className="text-[#64748b]">{p.date}</span>
                <div className="flex items-center gap-3">
                  <span className={`font-medium ${p.cumulative_pnl_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
                    {locale === "he" ? "סוכן" : "Agent"}: {p.cumulative_pnl_pct >= 0 ? "+" : ""}{p.cumulative_pnl_pct.toFixed(2)}%
                  </span>
                  {p.benchmark_pnl_pct !== null && (
                    <span className="text-[#94a3b8]">
                      SPY: {p.benchmark_pnl_pct >= 0 ? "+" : ""}{p.benchmark_pnl_pct.toFixed(2)}%
                    </span>
                  )}
                  <span className={`px-1 py-0.5 rounded text-[9px] ${
                    p.regime === "volatile" ? "bg-red-500/20 text-red-400" :
                    p.regime === "bull" ? "bg-green-500/20 text-green-400" :
                    p.regime === "bear" ? "bg-red-500/20 text-red-400" :
                    "bg-[#1e293b] text-[#64748b]"
                  }`}>
                    {p.regime}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Analyze Ticker */}
      <section className="bg-[#111827] rounded-xl border border-violet-500/20 p-3">
        <h3 className="text-xs font-semibold text-violet-400 uppercase mb-2 flex items-center gap-1.5">
          <Search className="w-3.5 h-3.5" />
          {locale === "he" ? "בדוק מניה" : "Analyze Ticker"}
        </h3>
        <div className="flex gap-2">
          <input
            type="text"
            value={analysisInput}
            onChange={(e) => setAnalysisInput(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
            placeholder={locale === "he" ? "NVDA, TSLA..." : "NVDA, TSLA..."}
            className="flex-1 px-3 py-2 rounded-lg bg-[#0f172a] border border-[#334155] text-sm text-white placeholder-[#475569] focus:border-violet-500/50 outline-none font-mono"
            maxLength={10}
          />
          <button
            onClick={handleAnalyze}
            disabled={analyzing || !analysisInput.trim()}
            className="px-4 py-2 rounded-lg bg-violet-500/20 text-violet-400 text-sm font-medium hover:bg-violet-500/30 transition disabled:opacity-40"
          >
            {analyzing ? <Loader2 className="w-4 h-4 animate-spin" /> : (locale === "he" ? "נתח" : "Analyze")}
          </button>
        </div>

        {/* Analysis Result */}
        {analysis && (
          <div className="mt-3 space-y-2">
            {/* Decision */}
            <div className={`p-3 rounded-lg border ${
              analysis.decision.action === "buy"
                ? "bg-green-500/10 border-green-500/20"
                : analysis.decision.action === "sell"
                ? "bg-red-500/10 border-red-500/20"
                : "bg-[#0f172a] border-[#1e293b]"
            }`}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-bold text-white">{analysis.ticker}</span>
                <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                  analysis.decision.direction === "bullish"
                    ? "bg-green-500/20 text-green-400"
                    : analysis.decision.direction === "bearish"
                    ? "bg-red-500/20 text-red-400"
                    : "bg-[#1e293b] text-[#64748b]"
                }`}>
                  {analysis.decision.direction === "bullish"
                    ? (locale === "he" ? "שורי" : "BULLISH")
                    : analysis.decision.direction === "bearish"
                    ? (locale === "he" ? "דובי" : "BEARISH")
                    : (locale === "he" ? "ניטרלי" : "NEUTRAL")}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#94a3b8]">{analysis.decision.reason}</span>
                <span className="text-white font-medium">
                  {locale === "he" ? "ביטחון" : "Conf"}: {(analysis.decision.confidence * 100).toFixed(0)}%
                </span>
              </div>
              {analysis.decision.earnings_warning && (
                <div className="mt-1 flex items-center gap-1.5 text-[10px] text-amber-400">
                  <AlertTriangle className="w-3 h-3" />
                  {locale === "he"
                    ? `אזהרת דוחות — ${analysis.decision.earnings_warning.days_until_earnings} ימים לדוחות`
                    : analysis.decision.earnings_warning.reason}
                </div>
              )
              </div>
            </div>

            {/* Signals breakdown */}
            <div className="space-y-1">
              {analysis.signals.map((s, i) => {
                const label = SIGNAL_LABELS[s.signal_type];
                return (
                  <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-[#0f172a] text-xs">
                    <span className="text-[#e2e8f0]">
                      {label?.icon} {locale === "he" ? label?.he : label?.en || s.signal_type}
                    </span>
                    <div className="flex items-center gap-2">
                      <span className={`font-medium ${
                        s.direction === "bullish" ? "text-green-400" :
                        s.direction === "bearish" ? "text-red-400" :
                        "text-[#64748b]"
                      }`}>
                        {s.direction === "bullish" ? "↑" : s.direction === "bearish" ? "↓" : "→"}
                      </span>
                      <div className="w-16 h-1.5 rounded-full bg-[#1e293b] overflow-hidden">
                        <div
                          className={`h-full rounded-full ${
                            s.direction === "bullish" ? "bg-green-400" :
                            s.direction === "bearish" ? "bg-red-400" :
                            "bg-[#475569]"
                          }`}
                          style={{ width: `${s.strength * 100}%` }}
                        />
                      </div>
                      <span className="text-[#64748b] w-8 text-end">{(s.strength * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function StatCard({ label, value, subValue, subColor }: {
  label: string;
  value: string;
  subValue?: string;
  subColor?: string;
}) {
  return (
    <div className="bg-[#111827] rounded-xl border border-[#334155] p-3">
      <div className="text-[10px] text-[#64748b] uppercase font-medium">{label}</div>
      <div className="text-lg font-bold text-white mt-0.5">{value}</div>
      {subValue && (
        <div className={`text-xs font-medium mt-0.5 ${subColor || "text-[#94a3b8]"}`}>{subValue}</div>
      )}
    </div>
  );
}
