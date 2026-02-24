"use client";
import { useState, useEffect } from "react";
import { useI18n } from "@/i18n/context";
import {
  Shield,
  Users,
  Activity,
  TrendingUp,
  TrendingDown,
  BarChart3,
  Brain,
  Zap,
  RefreshCw,
  Loader2,
  ChevronDown,
  ChevronUp,
  Target,
  AlertTriangle,
  Database,
} from "lucide-react";

interface AdminData {
  platform: {
    total_users: number;
    active_users_24h: number;
    active_users_7d: number;
    interactions_24h: number;
    interactions_7d: number;
    interaction_breakdown: { type: string; count: number }[];
  };
  agent: {
    portfolio: {
      cash: number;
      market_value: number;
      total_value: number;
      pnl: number;
      pnl_pct: number;
    };
    holdings: {
      ticker: string;
      quantity: number;
      avg_cost: number;
      current_price: number;
      pnl_pct: number;
      market_value: number;
    }[];
    trades: {
      total: number;
      open: number;
      closed: number;
      wins: number;
      losses: number;
      win_rate: number;
    };
    outcomes: {
      avg_1d: number | null;
      avg_7d: number | null;
      avg_30d: number | null;
      count_1d: number;
      count_7d: number;
      count_30d: number;
    };
    recent_trades: {
      ticker: string;
      action: string;
      quantity: number;
      entry_price: number;
      exit_price: number | null;
      confidence: number;
      is_open: boolean;
      opened_at: string | null;
      pnl_pct: number | null;
      outcome_1d: number | null;
      outcome_7d: number | null;
      outcome_30d: number | null;
    }[];
  };
  signals: {
    weights: {
      type: string;
      weight: number;
      accuracy: number;
      predictions: number;
      correct: number;
    }[];
  };
  performance: {
    date: string;
    value: number;
    daily_pnl: number;
    daily_pnl_pct: number;
    cumulative_pnl_pct: number;
    benchmark_pnl_pct: number | null;
    win_rate: number;
    regime: string;
  }[];
  breaking_history: {
    ticker: string;
    headline: string;
    velocity_ratio: number;
    urgency_score: number;
    created_at: string | null;
  }[];
  ml_model: {
    status: string;
    trained_at: string | null;
    metadata: Record<string, unknown> | null;
  };
  trending_topics: {
    slug: string;
    name_en: string;
    name_he: string;
    score: number;
    direction: string;
    mentions_today: number;
    avg_7d: number;
  }[];
  top_user_topics: {
    slug: string;
    interactions: number;
    unique_sessions: number;
  }[];
  generated_at: string;
}

const SIGNAL_LABELS: Record<string, string> = {
  momentum: "Momentum",
  sentiment: "Sentiment",
  user_herd: "User Herd",
  technical: "Technical",
  macro: "Macro",
  supply_chain: "Supply Chain",
  cross_reference: "Cross-Ref",
  nlp_sentiment: "NLP",
  user_ml: "User ML",
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function AdminDashboard() {
  const { locale } = useI18n();
  const isHe = locale === "he";
  const [data, setData] = useState<AdminData | null>(null);
  const [loading, setLoading] = useState(true);
  const [section, setSection] = useState<string>("overview");
  const [retraining, setRetraining] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const resp = await fetch(`${API_BASE}/api/admin/overview`);
      if (resp.ok) setData(await resp.json());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleRetrain = async () => {
    setRetraining(true);
    try {
      await fetch(`${API_BASE}/api/agent/ml/retrain`, { method: "POST" });
      await load();
    } catch (e) {
      console.error(e);
    } finally {
      setRetraining(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-[#64748b]">
        <Loader2 className="w-5 h-5 animate-spin me-2" />
        {isHe ? "טוען דשבורד מנהלים..." : "Loading Admin Dashboard..."}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="text-center py-12 text-[#64748b]">
        {isHe ? "לא ניתן לטעון את הנתונים" : "Failed to load admin data"}
      </div>
    );
  }

  const tabs = [
    { id: "overview", label: isHe ? "סקירה" : "Overview", icon: Shield },
    { id: "agent", label: isHe ? "סוכן AI" : "AI Agent", icon: Brain },
    { id: "signals", label: isHe ? "אותות" : "Signals", icon: Activity },
    { id: "users", label: isHe ? "משתמשים" : "Users", icon: Users },
    { id: "breaking", label: isHe ? "התראות" : "Alerts", icon: Zap },
  ];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield className="w-5 h-5 text-amber-400" />
          <h2 className="text-lg font-bold text-white">
            {isHe ? "דשבורד מנהלים" : "Admin Dashboard"}
          </h2>
          <span className="px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400 text-[10px] font-bold">
            INTERNAL
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[9px] text-[#475569]">
            {new Date(data.generated_at).toLocaleTimeString()}
          </span>
          <button onClick={load} className="p-1.5 rounded-lg hover:bg-[#1e293b] transition text-[#64748b] hover:text-amber-400">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-1 overflow-x-auto pb-1">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setSection(id)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition ${
              section === id
                ? "bg-amber-500/20 text-amber-400"
                : "text-[#64748b] hover:bg-[#1e293b] hover:text-white"
            }`}
          >
            <Icon className="w-3.5 h-3.5" />
            {label}
          </button>
        ))}
      </div>

      {/* ═══ OVERVIEW TAB ═══ */}
      {section === "overview" && (
        <div className="space-y-4">
          {/* Key Metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <MetricCard
              label={isHe ? "משתמשים" : "Total Users"}
              value={data.platform.total_users.toString()}
              icon={<Users className="w-4 h-4 text-cyan-400" />}
            />
            <MetricCard
              label={isHe ? "פעילים 24h" : "Active 24h"}
              value={data.platform.active_users_24h.toString()}
              sub={`${data.platform.active_users_7d} / 7d`}
              icon={<Activity className="w-4 h-4 text-green-400" />}
            />
            <MetricCard
              label={isHe ? "שווי סוכן" : "Agent Value"}
              value={`$${data.agent.portfolio.total_value.toLocaleString()}`}
              sub={`${data.agent.portfolio.pnl >= 0 ? "+" : ""}${data.agent.portfolio.pnl_pct.toFixed(2)}%`}
              subColor={data.agent.portfolio.pnl >= 0 ? "text-green-400" : "text-red-400"}
              icon={<Brain className="w-4 h-4 text-violet-400" />}
            />
            <MetricCard
              label={isHe ? "אחוז הצלחה" : "Win Rate"}
              value={`${data.agent.trades.win_rate}%`}
              sub={`${data.agent.trades.wins}W / ${data.agent.trades.losses}L`}
              icon={<Target className="w-4 h-4 text-amber-400" />}
            />
          </div>

          {/* Outcome Averages */}
          <Section title={isHe ? "ממוצע תוצאות עסקאות" : "Avg Trade Outcomes"} icon={<BarChart3 className="w-3.5 h-3.5" />}>
            <div className="grid grid-cols-3 gap-2">
              <OutcomeCard label="1 Day" value={data.agent.outcomes.avg_1d} count={data.agent.outcomes.count_1d} />
              <OutcomeCard label="7 Days" value={data.agent.outcomes.avg_7d} count={data.agent.outcomes.count_7d} />
              <OutcomeCard label="30 Days" value={data.agent.outcomes.avg_30d} count={data.agent.outcomes.count_30d} />
            </div>
          </Section>

          {/* ML Model Status */}
          <Section title={isHe ? "מודל ML" : "ML Model Status"} icon={<Database className="w-3.5 h-3.5" />}>
            <div className="flex items-center justify-between p-3 rounded-lg bg-[#0f172a]">
              <div>
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                  data.ml_model.status === "trained"
                    ? "bg-green-500/20 text-green-400"
                    : "bg-amber-500/20 text-amber-400"
                }`}>
                  {data.ml_model.status === "trained" ? (isHe ? "מאומן" : "TRAINED") : (isHe ? "לא מאומן" : "NOT TRAINED")}
                </span>
                {data.ml_model.trained_at && (
                  <span className="text-[10px] text-[#64748b] ms-2">
                    {new Date(data.ml_model.trained_at).toLocaleDateString()}
                  </span>
                )}
                {data.ml_model.metadata && (
                  <div className="mt-1 text-[10px] text-[#94a3b8]">
                    {isHe ? "סוג:" : "Type:"} {(data.ml_model.metadata as Record<string, unknown>).model_type as string || "—"}
                    {" | "}
                    {isHe ? "דיוק:" : "Accuracy:"} {((data.ml_model.metadata as Record<string, unknown>).cv_accuracy as number * 100)?.toFixed(1) || "—"}%
                    {" | "}
                    {isHe ? "דוגמאות:" : "Samples:"} {(data.ml_model.metadata as Record<string, unknown>).samples as number || "—"}
                  </div>
                )}
              </div>
              <button
                onClick={handleRetrain}
                disabled={retraining}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-violet-500/20 text-violet-400 text-xs font-medium hover:bg-violet-500/30 transition disabled:opacity-40"
              >
                {retraining ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                {isHe ? "אמן מחדש" : "Retrain"}
              </button>
            </div>
          </Section>

          {/* Performance vs Benchmark (condensed) */}
          {data.performance.length > 0 && (
            <Section title={isHe ? "ביצועים מול SPY" : "Performance vs SPY"} icon={<TrendingUp className="w-3.5 h-3.5" />}>
              <div className="space-y-1 max-h-64 overflow-y-auto">
                {data.performance.slice(0, 20).map((p) => (
                  <div key={p.date} className="flex items-center justify-between text-xs py-1 border-b border-[#1e293b] last:border-0">
                    <span className="text-[#64748b] w-20">{p.date}</span>
                    <span className="text-[#94a3b8] w-20 text-end">${p.value.toLocaleString()}</span>
                    <span className={`w-16 text-end font-medium ${p.daily_pnl_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
                      {p.daily_pnl_pct >= 0 ? "+" : ""}{p.daily_pnl_pct.toFixed(2)}%
                    </span>
                    <span className={`w-16 text-end font-medium ${p.cumulative_pnl_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
                      {p.cumulative_pnl_pct >= 0 ? "+" : ""}{p.cumulative_pnl_pct.toFixed(2)}%
                    </span>
                    {p.benchmark_pnl_pct !== null && (
                      <span className="text-[#64748b] w-16 text-end">
                        SPY {p.benchmark_pnl_pct >= 0 ? "+" : ""}{p.benchmark_pnl_pct.toFixed(2)}%
                      </span>
                    )}
                    <span className={`px-1 py-0.5 rounded text-[8px] w-14 text-center ${
                      p.regime === "volatile" ? "bg-red-500/20 text-red-400" :
                      p.regime === "bull" ? "bg-green-500/20 text-green-400" :
                      p.regime === "bear" ? "bg-red-500/20 text-red-400" :
                      "bg-[#1e293b] text-[#64748b]"
                    }`}>
                      {p.regime}
                    </span>
                  </div>
                ))}
              </div>
            </Section>
          )}
        </div>
      )}

      {/* ═══ AGENT TAB ═══ */}
      {section === "agent" && (
        <div className="space-y-4">
          {/* Agent Holdings */}
          <Section title={isHe ? "אחזקות סוכן" : "Agent Holdings"} icon={<Target className="w-3.5 h-3.5" />}>
            {data.agent.holdings.length === 0 ? (
              <p className="text-xs text-[#475569] text-center py-4">{isHe ? "אין אחזקות" : "No holdings"}</p>
            ) : (
              <div className="space-y-1">
                <div className="grid grid-cols-6 gap-2 text-[9px] text-[#475569] font-medium px-2 uppercase">
                  <span>Ticker</span><span>Qty</span><span>Avg Cost</span><span>Current</span><span>P&L</span><span>Value</span>
                </div>
                {data.agent.holdings.map((h) => (
                  <div key={h.ticker} className="grid grid-cols-6 gap-2 text-xs p-2 rounded-lg bg-[#0f172a]">
                    <span className="font-mono font-bold text-cyan-400">{h.ticker}</span>
                    <span className="text-[#94a3b8]">{h.quantity}</span>
                    <span className="text-[#94a3b8]">${h.avg_cost.toFixed(2)}</span>
                    <span className="text-white">${h.current_price.toFixed(2)}</span>
                    <span className={h.pnl_pct >= 0 ? "text-green-400" : "text-red-400"}>
                      {h.pnl_pct >= 0 ? "+" : ""}{h.pnl_pct.toFixed(1)}%
                    </span>
                    <span className="text-[#94a3b8]">${h.market_value.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            )}
          </Section>

          {/* All Trades */}
          <Section title={isHe ? `כל העסקאות (${data.agent.trades.total})` : `All Trades (${data.agent.trades.total})`} icon={<Activity className="w-3.5 h-3.5" />}>
            <div className="space-y-1 max-h-96 overflow-y-auto">
              <div className="grid grid-cols-8 gap-1 text-[8px] text-[#475569] font-medium px-2 uppercase sticky top-0 bg-[#111827]">
                <span>Action</span><span>Ticker</span><span>Qty</span><span>Entry</span><span>Conf</span><span>1d</span><span>7d</span><span>30d</span>
              </div>
              {data.agent.recent_trades.map((t, i) => (
                <div key={i} className="grid grid-cols-8 gap-1 text-[10px] p-1.5 rounded bg-[#0f172a]">
                  <span className={`font-bold ${t.action === "buy" ? "text-green-400" : "text-red-400"}`}>
                    {t.action.toUpperCase()}
                  </span>
                  <span className="font-mono text-cyan-400">{t.ticker}</span>
                  <span className="text-[#94a3b8]">{t.quantity}</span>
                  <span className="text-[#94a3b8]">${t.entry_price.toFixed(0)}</span>
                  <span className="text-white">{(t.confidence * 100).toFixed(0)}%</span>
                  <span className={t.outcome_1d !== null ? (t.outcome_1d >= 0 ? "text-green-500" : "text-red-500") : "text-[#334155]"}>
                    {t.outcome_1d !== null ? `${t.outcome_1d > 0 ? "+" : ""}${t.outcome_1d.toFixed(1)}%` : "—"}
                  </span>
                  <span className={t.outcome_7d !== null ? (t.outcome_7d >= 0 ? "text-green-500" : "text-red-500") : "text-[#334155]"}>
                    {t.outcome_7d !== null ? `${t.outcome_7d > 0 ? "+" : ""}${t.outcome_7d.toFixed(1)}%` : "—"}
                  </span>
                  <span className={t.outcome_30d !== null ? (t.outcome_30d >= 0 ? "text-green-500" : "text-red-500") : "text-[#334155]"}>
                    {t.outcome_30d !== null ? `${t.outcome_30d > 0 ? "+" : ""}${t.outcome_30d.toFixed(1)}%` : "—"}
                  </span>
                </div>
              ))}
            </div>
          </Section>
        </div>
      )}

      {/* ═══ SIGNALS TAB ═══ */}
      {section === "signals" && (
        <div className="space-y-4">
          <Section title={isHe ? "משקלות אותות + דיוק" : "Signal Weights + Accuracy"} icon={<BarChart3 className="w-3.5 h-3.5" />}>
            <div className="space-y-2">
              {data.signals.weights.map((w) => {
                const barWidth = Math.min(100, w.weight * 50);
                const accBar = Math.min(100, w.accuracy);
                return (
                  <div key={w.type} className="p-2 rounded-lg bg-[#0f172a]">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-medium text-white">{SIGNAL_LABELS[w.type] || w.type}</span>
                      <div className="flex items-center gap-3 text-[10px]">
                        <span className="text-[#64748b]">
                          {isHe ? "משקל" : "Weight"}: <span className="text-white font-medium">{w.weight.toFixed(2)}</span>
                        </span>
                        <span className="text-[#64748b]">
                          {isHe ? "דיוק" : "Acc"}: <span className={`font-medium ${w.accuracy >= 55 ? "text-green-400" : w.accuracy >= 45 ? "text-amber-400" : "text-red-400"}`}>{w.accuracy.toFixed(1)}%</span>
                        </span>
                        <span className="text-[#475569]">{w.correct}/{w.predictions}</span>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <div className="flex-1">
                        <div className="text-[8px] text-[#475569] mb-0.5">{isHe ? "משקל" : "WEIGHT"}</div>
                        <div className="h-1.5 rounded-full bg-[#1e293b] overflow-hidden">
                          <div className="h-full rounded-full bg-gradient-to-r from-violet-500 to-cyan-500" style={{ width: `${barWidth}%` }} />
                        </div>
                      </div>
                      <div className="flex-1">
                        <div className="text-[8px] text-[#475569] mb-0.5">{isHe ? "דיוק" : "ACCURACY"}</div>
                        <div className="h-1.5 rounded-full bg-[#1e293b] overflow-hidden">
                          <div className={`h-full rounded-full ${w.accuracy >= 55 ? "bg-green-500" : w.accuracy >= 45 ? "bg-amber-500" : "bg-red-500"}`} style={{ width: `${accBar}%` }} />
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </Section>
        </div>
      )}

      {/* ═══ USERS TAB ═══ */}
      {section === "users" && (
        <div className="space-y-4">
          {/* Interaction Stats */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            <MetricCard
              label={isHe ? "אינטראקציות 24h" : "Interactions 24h"}
              value={data.platform.interactions_24h.toLocaleString()}
              icon={<Activity className="w-4 h-4 text-cyan-400" />}
            />
            <MetricCard
              label={isHe ? "אינטראקציות 7d" : "Interactions 7d"}
              value={data.platform.interactions_7d.toLocaleString()}
              icon={<Activity className="w-4 h-4 text-blue-400" />}
            />
            <MetricCard
              label={isHe ? "פעילים 7d" : "Active Users 7d"}
              value={data.platform.active_users_7d.toString()}
              icon={<Users className="w-4 h-4 text-green-400" />}
            />
          </div>

          {/* Interaction Breakdown */}
          <Section title={isHe ? "פילוח אינטראקציות (24h)" : "Interaction Breakdown (24h)"} icon={<BarChart3 className="w-3.5 h-3.5" />}>
            <div className="space-y-1.5">
              {data.platform.interaction_breakdown.map((item) => {
                const maxCount = Math.max(...data.platform.interaction_breakdown.map(x => x.count), 1);
                return (
                  <div key={item.type} className="flex items-center gap-3">
                    <span className="text-xs text-[#94a3b8] w-32 truncate">{item.type}</span>
                    <div className="flex-1 h-2 rounded-full bg-[#1e293b] overflow-hidden">
                      <div className="h-full rounded-full bg-cyan-500/70" style={{ width: `${(item.count / maxCount) * 100}%` }} />
                    </div>
                    <span className="text-xs text-white font-medium w-10 text-end">{item.count}</span>
                  </div>
                );
              })}
            </div>
          </Section>

          {/* Top Topics by User Interest */}
          <Section title={isHe ? "נושאים פופולריים (24h)" : "Top User Topics (24h)"} icon={<TrendingUp className="w-3.5 h-3.5" />}>
            <div className="space-y-1">
              {data.top_user_topics.map((t, i) => (
                <div key={t.slug} className="flex items-center justify-between p-2 rounded-lg bg-[#0f172a] text-xs">
                  <div className="flex items-center gap-2">
                    <span className="text-[#475569] w-4 text-end">#{i + 1}</span>
                    <span className="text-white font-medium">{t.slug}</span>
                  </div>
                  <div className="flex items-center gap-3 text-[10px]">
                    <span className="text-cyan-400">{t.interactions} {isHe ? "אינטראקציות" : "interactions"}</span>
                    <span className="text-[#64748b]">{t.unique_sessions} {isHe ? "סשנים" : "sessions"}</span>
                  </div>
                </div>
              ))}
            </div>
          </Section>

          {/* Trending Topics */}
          <Section title={isHe ? "טרנדים (מומנטום)" : "Trending (Momentum)"} icon={<TrendingUp className="w-3.5 h-3.5" />}>
            <div className="space-y-1">
              {data.trending_topics.map((t) => (
                <div key={t.slug} className="flex items-center justify-between p-2 rounded-lg bg-[#0f172a] text-xs">
                  <span className="text-white font-medium">{isHe ? t.name_he : t.name_en}</span>
                  <div className="flex items-center gap-2">
                    <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                      t.direction === "rising" ? "bg-green-500/20 text-green-400" :
                      t.direction === "falling" ? "bg-red-500/20 text-red-400" :
                      "bg-[#1e293b] text-[#64748b]"
                    }`}>
                      {t.direction === "rising" ? "↑" : t.direction === "falling" ? "↓" : "→"} {t.score}
                    </span>
                    <span className="text-[#64748b] text-[10px]">{t.mentions_today} / {t.avg_7d.toFixed(0)} avg</span>
                  </div>
                </div>
              ))}
            </div>
          </Section>
        </div>
      )}

      {/* ═══ BREAKING TAB ═══ */}
      {section === "breaking" && (
        <div className="space-y-4">
          <Section title={isHe ? "היסטוריית התראות חדשות חמות" : "Breaking News Alert History"} icon={<Zap className="w-3.5 h-3.5" />}>
            {data.breaking_history.length === 0 ? (
              <p className="text-xs text-[#475569] text-center py-6">{isHe ? "אין התראות עדיין" : "No alerts recorded yet"}</p>
            ) : (
              <div className="space-y-1.5 max-h-96 overflow-y-auto">
                {data.breaking_history.map((a, i) => (
                  <div key={i} className="p-2 rounded-lg bg-[#0f172a] border border-[#1e293b]">
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="font-mono text-sm font-bold text-red-400">{a.ticker}</span>
                      <div className="flex items-center gap-2">
                        <span className={`px-1 py-0.5 rounded text-[9px] font-bold ${
                          a.urgency_score >= 0.7 ? "bg-red-500/20 text-red-400" :
                          a.urgency_score >= 0.4 ? "bg-amber-500/20 text-amber-400" :
                          "bg-[#1e293b] text-[#64748b]"
                        }`}>
                          urgency: {a.urgency_score.toFixed(2)}
                        </span>
                        <span className="text-[9px] text-[#475569]">{a.velocity_ratio}x velocity</span>
                      </div>
                    </div>
                    <p className="text-[10px] text-[#94a3b8] line-clamp-1">{a.headline}</p>
                    {a.created_at && (
                      <p className="text-[9px] text-[#334155] mt-0.5">{new Date(a.created_at).toLocaleString()}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Section>
        </div>
      )}
    </div>
  );
}

// ── Helper Components ──

function MetricCard({ label, value, sub, subColor, icon }: {
  label: string; value: string; sub?: string; subColor?: string; icon?: React.ReactNode;
}) {
  return (
    <div className="bg-[#111827] rounded-xl border border-[#334155] p-3">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[9px] text-[#64748b] uppercase font-medium">{label}</span>
        {icon}
      </div>
      <div className="text-lg font-bold text-white">{value}</div>
      {sub && <div className={`text-xs font-medium mt-0.5 ${subColor || "text-[#94a3b8]"}`}>{sub}</div>}
    </div>
  );
}

function Section({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="bg-[#111827] rounded-xl border border-[#334155] p-3">
      <h3 className="text-xs font-semibold text-[#94a3b8] uppercase mb-2 flex items-center gap-1.5">
        {icon} {title}
      </h3>
      {children}
    </section>
  );
}

function OutcomeCard({ label, value, count }: { label: string; value: number | null; count: number }) {
  return (
    <div className="bg-[#0f172a] rounded-lg p-3 text-center">
      <div className="text-[9px] text-[#475569] uppercase font-medium">{label}</div>
      <div className={`text-lg font-bold mt-0.5 ${value === null ? "text-[#334155]" : value >= 0 ? "text-green-400" : "text-red-400"}`}>
        {value !== null ? `${value > 0 ? "+" : ""}${value.toFixed(2)}%` : "—"}
      </div>
      <div className="text-[9px] text-[#475569] mt-0.5">{count} trades</div>
    </div>
  );
}
