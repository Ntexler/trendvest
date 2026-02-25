"use client";
import { useState, useEffect, useCallback, useRef } from "react";
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
  Clock,
  CheckCircle,
  XCircle,
  Play,
  Search,
} from "lucide-react";

// ── Types ──

interface AdminData {
  platform: {
    total_users: number;
    active_users_24h: number;
    active_users_7d: number;
    interactions_24h: number;
    interactions_7d: number;
    prev_active_users_24h: number;
    prev_interactions_24h: number;
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
      closed_at: string | null;
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
      updated_at: string | null;
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
  health: {
    last_trade_at: string | null;
    last_alert_at: string | null;
    last_weight_update: string | null;
    ml_freshness_hours: number | null;
    data_pipeline_ok: boolean;
    agent_active: boolean;
  };
  timeline: {
    event_type: string;
    ticker: string;
    detail: string | null;
    confidence: number | null;
    event_time: string | null;
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
  earnings_blackout: "Earnings",
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const AUTO_REFRESH_MS = 30_000;

function authHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("tv_access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// ── Helpers ──

function calcDelta(current: number, previous: number): { pct: number; direction: "up" | "down" | "flat" } {
  if (previous === 0) return { pct: 0, direction: "flat" };
  const pct = ((current - previous) / previous) * 100;
  return { pct: Math.round(pct), direction: pct > 0 ? "up" : pct < 0 ? "down" : "flat" };
}

function timeAgo(iso: string | null): string {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

// ── Main Component ──

export default function AdminDashboard() {
  const { locale } = useI18n();
  const isHe = locale === "he";
  const [data, setData] = useState<AdminData | null>(null);
  const [loading, setLoading] = useState(true);
  const [section, setSection] = useState<string>("overview");
  const [retraining, setRetraining] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [learning, setLearning] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [expandedTrade, setExpandedTrade] = useState<number | null>(null);
  const refreshTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const resp = await fetch(`${API_BASE}/api/admin/overview`, { headers: authHeaders() });
      if (resp.ok) setData(await resp.json());
    } catch (e) {
      console.error(e);
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => { load(); }, [load]);

  // Auto-refresh
  useEffect(() => {
    if (autoRefresh) {
      refreshTimer.current = setInterval(() => load(true), AUTO_REFRESH_MS);
    }
    return () => {
      if (refreshTimer.current) clearInterval(refreshTimer.current);
    };
  }, [autoRefresh, load]);

  const handleRetrain = async () => {
    setRetraining(true);
    try {
      await fetch(`${API_BASE}/api/agent/ml/retrain`, { method: "POST", headers: authHeaders() });
      await load();
    } catch (e) { console.error(e); }
    finally { setRetraining(false); }
  };

  const handleScan = async () => {
    setScanning(true);
    try {
      await fetch(`${API_BASE}/api/agent/breaking/scan`, { method: "POST", headers: authHeaders() });
      await load();
    } catch (e) { console.error(e); }
    finally { setScanning(false); }
  };

  const handleLearn = async () => {
    setLearning(true);
    try {
      await fetch(`${API_BASE}/api/agent/learn`, { method: "POST", headers: authHeaders() });
      await load();
    } catch (e) { console.error(e); }
    finally { setLearning(false); }
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

  // Compute deltas
  const usersDelta = calcDelta(data.platform.active_users_24h, data.platform.prev_active_users_24h);
  const interactionsDelta = calcDelta(data.platform.interactions_24h, data.platform.prev_interactions_24h);

  // Health status
  const healthChecks = [
    { label: isHe ? "סוכן פעיל" : "Agent Active", ok: data.health.agent_active },
    { label: isHe ? "צנרת נתונים" : "Data Pipeline", ok: data.health.data_pipeline_ok },
    { label: "ML Model", ok: data.ml_model.status === "trained" && (data.health.ml_freshness_hours === null || data.health.ml_freshness_hours < 168) },
  ];
  const overallHealth = healthChecks.every(h => h.ok) ? "green" : healthChecks.some(h => h.ok) ? "amber" : "red";

  // ML feature importance from metadata
  const featureImportance: { name: string; importance: number }[] = [];
  if (data.ml_model.metadata && (data.ml_model.metadata as Record<string, unknown>).feature_importance) {
    const fi = (data.ml_model.metadata as Record<string, unknown>).feature_importance as Record<string, number>;
    Object.entries(fi).forEach(([name, importance]) => {
      featureImportance.push({ name, importance });
    });
    featureImportance.sort((a, b) => b.importance - a.importance);
  }

  return (
    <div className="space-y-3">
      {/* ═══ HEADER ═══ */}
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
          {/* Auto-refresh toggle */}
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-medium transition ${
              autoRefresh
                ? "bg-green-500/20 text-green-400"
                : "bg-[#1e293b] text-[#475569]"
            }`}
          >
            <div className={`w-1.5 h-1.5 rounded-full ${autoRefresh ? "bg-green-400 animate-pulse" : "bg-[#475569]"}`} />
            {autoRefresh ? "LIVE" : "PAUSED"}
          </button>
          <span className="text-[9px] text-[#475569]">
            {new Date(data.generated_at).toLocaleTimeString()}
          </span>
          <button onClick={() => load()} className="p-1.5 rounded-lg hover:bg-[#1e293b] transition text-[#64748b] hover:text-amber-400">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* ═══ FIX 1: SYSTEM HEALTH STATUS BAR ═══ */}
      <div className={`flex items-center gap-3 p-2.5 rounded-xl border ${
        overallHealth === "green"
          ? "bg-green-500/5 border-green-500/20"
          : overallHealth === "amber"
          ? "bg-amber-500/5 border-amber-500/20"
          : "bg-red-500/5 border-red-500/20"
      }`}>
        <div className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${
          overallHealth === "green" ? "bg-green-400" :
          overallHealth === "amber" ? "bg-amber-400 animate-pulse" :
          "bg-red-400 animate-pulse"
        }`} />
        <div className="flex items-center gap-4 flex-1 overflow-x-auto">
          {healthChecks.map((h) => (
            <div key={h.label} className="flex items-center gap-1.5 whitespace-nowrap">
              {h.ok
                ? <CheckCircle className="w-3 h-3 text-green-400" />
                : <XCircle className="w-3 h-3 text-red-400" />
              }
              <span className={`text-[10px] font-medium ${h.ok ? "text-green-400" : "text-red-400"}`}>
                {h.label}
              </span>
            </div>
          ))}
        </div>
        <span className="text-[9px] text-[#475569] whitespace-nowrap">
          {isHe ? "עסקה אחרונה" : "Last trade"}: {timeAgo(data.health.last_trade_at)}
        </span>
      </div>

      {/* ═══ FIX 6: QUICK ACTIONS PANEL ═══ */}
      <div className="flex gap-2 overflow-x-auto pb-0.5">
        <QuickAction
          label={isHe ? "למידה" : "Learn"}
          icon={<Brain className="w-3.5 h-3.5" />}
          loading={learning}
          onClick={handleLearn}
          color="violet"
        />
        <QuickAction
          label={isHe ? "אימון ML" : "Retrain ML"}
          icon={<Database className="w-3.5 h-3.5" />}
          loading={retraining}
          onClick={handleRetrain}
          color="cyan"
        />
        <QuickAction
          label={isHe ? "סריקת חדשות" : "Scan News"}
          icon={<Search className="w-3.5 h-3.5" />}
          loading={scanning}
          onClick={handleScan}
          color="amber"
        />
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
          {/* FIX 2: Key Metrics with Delta Indicators */}
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
              delta={usersDelta}
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

          {/* FIX 4: Performance Sparkline Chart */}
          {data.performance.length > 0 && (
            <Section title={isHe ? "ביצועים (60 יום)" : "Performance (60d)"} icon={<TrendingUp className="w-3.5 h-3.5" />}>
              <PerformanceChart data={data.performance} isHe={isHe} />
            </Section>
          )}

          {/* Outcome Averages */}
          <Section title={isHe ? "ממוצע תוצאות עסקאות" : "Avg Trade Outcomes"} icon={<BarChart3 className="w-3.5 h-3.5" />}>
            <div className="grid grid-cols-3 gap-2">
              <OutcomeCard label="1 Day" value={data.agent.outcomes.avg_1d} count={data.agent.outcomes.count_1d} />
              <OutcomeCard label="7 Days" value={data.agent.outcomes.avg_7d} count={data.agent.outcomes.count_7d} />
              <OutcomeCard label="30 Days" value={data.agent.outcomes.avg_30d} count={data.agent.outcomes.count_30d} />
            </div>
          </Section>

          {/* ML Model + Feature Importance */}
          <Section title={isHe ? "מודל ML" : "ML Model Status"} icon={<Database className="w-3.5 h-3.5" />}>
            <div className="p-3 rounded-lg bg-[#0f172a]">
              <div className="flex items-center justify-between">
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
                      {data.health.ml_freshness_hours !== null && (
                        <span className="ms-1">({Math.round(data.health.ml_freshness_hours)}h ago)</span>
                      )}
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
              </div>

              {/* FIX 8: ML Feature Importance Visualization */}
              {featureImportance.length > 0 && (
                <div className="mt-3 pt-3 border-t border-[#1e293b]">
                  <h4 className="text-[10px] text-[#475569] uppercase font-medium mb-2">
                    {isHe ? "חשיבות פיצ'רים" : "Feature Importance"}
                  </h4>
                  <div className="space-y-1">
                    {featureImportance.slice(0, 8).map((f) => {
                      const maxImp = featureImportance[0]?.importance || 1;
                      const pct = Math.round((f.importance / maxImp) * 100);
                      return (
                        <div key={f.name} className="flex items-center gap-2">
                          <span className="text-[9px] text-[#94a3b8] w-28 truncate font-mono">{f.name}</span>
                          <div className="flex-1 h-1.5 rounded-full bg-[#1e293b] overflow-hidden">
                            <div
                              className="h-full rounded-full bg-gradient-to-r from-violet-500 to-fuchsia-500"
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                          <span className="text-[9px] text-[#64748b] w-10 text-end">{(f.importance * 100).toFixed(1)}%</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </Section>

          {/* FIX 7: Agent Activity Timeline */}
          {data.timeline.length > 0 && (
            <Section title={isHe ? "ציר זמן פעילות" : "Activity Timeline"} icon={<Clock className="w-3.5 h-3.5" />}>
              <div className="space-y-0.5 max-h-64 overflow-y-auto">
                {data.timeline.map((ev, i) => (
                  <div key={i} className="flex items-start gap-2.5 py-1.5 border-b border-[#1e293b]/50 last:border-0">
                    <div className="mt-0.5">
                      {ev.event_type === "trade" ? (
                        <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[8px] font-bold ${
                          ev.detail === "buy" ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"
                        }`}>
                          {ev.detail === "buy" ? "B" : "S"}
                        </div>
                      ) : ev.event_type === "breaking" ? (
                        <div className="w-5 h-5 rounded-full flex items-center justify-center bg-amber-500/20">
                          <Zap className="w-3 h-3 text-amber-400" />
                        </div>
                      ) : (
                        <div className="w-5 h-5 rounded-full flex items-center justify-center bg-violet-500/20">
                          <Activity className="w-3 h-3 text-violet-400" />
                        </div>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono font-bold text-cyan-400">{ev.ticker}</span>
                        <span className="text-[10px] text-[#94a3b8]">
                          {ev.event_type === "trade"
                            ? `${ev.detail?.toUpperCase()} — ${ev.confidence ? `${(ev.confidence * 100).toFixed(0)}% conf` : ""}`
                            : ev.event_type === "breaking"
                            ? (ev.detail ? ev.detail.slice(0, 50) : "Alert")
                            : `Weight → ${ev.detail}`
                          }
                        </span>
                      </div>
                      <span className="text-[9px] text-[#475569]">{timeAgo(ev.event_time)}</span>
                    </div>
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
          {/* Portfolio Summary */}
          <div className="grid grid-cols-3 gap-2">
            <MetricCard
              label={isHe ? "מזומן" : "Cash"}
              value={`$${data.agent.portfolio.cash.toLocaleString()}`}
              icon={<Target className="w-4 h-4 text-green-400" />}
            />
            <MetricCard
              label={isHe ? "שווי שוק" : "Market Value"}
              value={`$${data.agent.portfolio.market_value.toLocaleString()}`}
              icon={<BarChart3 className="w-4 h-4 text-cyan-400" />}
            />
            <MetricCard
              label={isHe ? "רווח/הפסד" : "Total P&L"}
              value={`${data.agent.portfolio.pnl >= 0 ? "+" : ""}$${data.agent.portfolio.pnl.toLocaleString()}`}
              subColor={data.agent.portfolio.pnl >= 0 ? "text-green-400" : "text-red-400"}
              icon={data.agent.portfolio.pnl >= 0
                ? <TrendingUp className="w-4 h-4 text-green-400" />
                : <TrendingDown className="w-4 h-4 text-red-400" />
              }
            />
          </div>

          {/* Agent Holdings */}
          <Section title={isHe ? "אחזקות סוכן" : "Agent Holdings"} icon={<Target className="w-3.5 h-3.5" />}>
            {data.agent.holdings.length === 0 ? (
              <p className="text-xs text-[#475569] text-center py-4">{isHe ? "אין אחזקות" : "No holdings"}</p>
            ) : (
              <div className="space-y-1">
                <div className="hidden md:grid grid-cols-6 gap-2 text-[9px] text-[#475569] font-medium px-2 uppercase">
                  <span>Ticker</span><span>Qty</span><span>Avg Cost</span><span>Current</span><span>P&L</span><span>Value</span>
                </div>
                {data.agent.holdings.map((h) => (
                  <div key={h.ticker} className="p-2 rounded-lg bg-[#0f172a]">
                    {/* Desktop row */}
                    <div className="hidden md:grid grid-cols-6 gap-2 text-xs">
                      <span className="font-mono font-bold text-cyan-400">{h.ticker}</span>
                      <span className="text-[#94a3b8]">{h.quantity}</span>
                      <span className="text-[#94a3b8]">${h.avg_cost.toFixed(2)}</span>
                      <span className="text-white">${h.current_price.toFixed(2)}</span>
                      <span className={h.pnl_pct >= 0 ? "text-green-400" : "text-red-400"}>
                        {h.pnl_pct >= 0 ? "+" : ""}{h.pnl_pct.toFixed(1)}%
                      </span>
                      <span className="text-[#94a3b8]">${h.market_value.toLocaleString()}</span>
                    </div>
                    {/* Mobile card */}
                    <div className="md:hidden">
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-mono font-bold text-cyan-400">{h.ticker}</span>
                        <span className={`font-medium ${h.pnl_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
                          {h.pnl_pct >= 0 ? "+" : ""}{h.pnl_pct.toFixed(1)}%
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-[10px] text-[#64748b]">
                        <span>{h.quantity} @ ${h.avg_cost.toFixed(2)}</span>
                        <span className="text-[#94a3b8]">${h.market_value.toLocaleString()}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Section>

          {/* FIX 3: Trades with Expandable Rows */}
          <Section title={isHe ? `כל העסקאות (${data.agent.trades.total})` : `All Trades (${data.agent.trades.total})`} icon={<Activity className="w-3.5 h-3.5" />}>
            <div className="space-y-1 max-h-[500px] overflow-y-auto">
              {data.agent.recent_trades.map((t, i) => (
                <div key={i} className="rounded-lg bg-[#0f172a] overflow-hidden">
                  {/* Summary row — always visible */}
                  <button
                    onClick={() => setExpandedTrade(expandedTrade === i ? null : i)}
                    className="w-full flex items-center justify-between p-2 hover:bg-[#1e293b]/50 transition text-start"
                  >
                    <div className="flex items-center gap-2">
                      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                        t.action === "buy" ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"
                      }`}>
                        {t.action.toUpperCase()}
                      </span>
                      <span className="font-mono text-xs font-bold text-cyan-400">{t.ticker}</span>
                      <span className="text-[10px] text-[#64748b]">x{t.quantity}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-white">{(t.confidence * 100).toFixed(0)}%</span>
                      {t.pnl_pct !== null && (
                        <span className={`text-[10px] font-medium ${t.pnl_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
                          {t.pnl_pct >= 0 ? "+" : ""}{t.pnl_pct.toFixed(1)}%
                        </span>
                      )}
                      {expandedTrade === i
                        ? <ChevronUp className="w-3 h-3 text-[#475569]" />
                        : <ChevronDown className="w-3 h-3 text-[#475569]" />
                      }
                    </div>
                  </button>
                  {/* Expanded detail */}
                  {expandedTrade === i && (
                    <div className="px-3 pb-2.5 pt-0.5 border-t border-[#1e293b] space-y-1.5">
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-[10px]">
                        <div>
                          <span className="text-[#475569]">{isHe ? "כניסה" : "Entry"}: </span>
                          <span className="text-white">${t.entry_price.toFixed(2)}</span>
                        </div>
                        {t.exit_price && (
                          <div>
                            <span className="text-[#475569]">{isHe ? "יציאה" : "Exit"}: </span>
                            <span className="text-white">${t.exit_price.toFixed(2)}</span>
                          </div>
                        )}
                        <div>
                          <span className="text-[#475569]">{isHe ? "סטטוס" : "Status"}: </span>
                          <span className={t.is_open ? "text-amber-400" : "text-green-400"}>
                            {t.is_open ? (isHe ? "פתוח" : "OPEN") : (isHe ? "סגור" : "CLOSED")}
                          </span>
                        </div>
                        {t.opened_at && (
                          <div>
                            <span className="text-[#475569]">{isHe ? "נפתח" : "Opened"}: </span>
                            <span className="text-[#94a3b8]">{new Date(t.opened_at).toLocaleDateString()}</span>
                          </div>
                        )}
                      </div>
                      {/* Outcome bars */}
                      <div className="flex gap-2">
                        <OutcomeBadge label="1d" value={t.outcome_1d} />
                        <OutcomeBadge label="7d" value={t.outcome_7d} />
                        <OutcomeBadge label="30d" value={t.outcome_30d} />
                      </div>
                    </div>
                  )}
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
                    {w.updated_at && (
                      <div className="text-[8px] text-[#334155] mt-1">
                        {isHe ? "עודכן" : "Updated"}: {timeAgo(w.updated_at)}
                      </div>
                    )}
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
          {/* FIX 2: Interaction Stats with Deltas */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            <MetricCard
              label={isHe ? "אינטראקציות 24h" : "Interactions 24h"}
              value={data.platform.interactions_24h.toLocaleString()}
              delta={interactionsDelta}
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

// ═══════════════════════════════════════════
// Helper Components
// ═══════════════════════════════════════════

function MetricCard({ label, value, sub, subColor, icon, delta }: {
  label: string;
  value: string;
  sub?: string;
  subColor?: string;
  icon?: React.ReactNode;
  delta?: { pct: number; direction: "up" | "down" | "flat" };
}) {
  return (
    <div className="bg-[#111827] rounded-xl border border-[#334155] p-3">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[9px] text-[#64748b] uppercase font-medium">{label}</span>
        {icon}
      </div>
      <div className="flex items-baseline gap-2">
        <div className="text-lg font-bold text-white">{value}</div>
        {delta && delta.direction !== "flat" && (
          <span className={`flex items-center gap-0.5 text-[10px] font-medium ${
            delta.direction === "up" ? "text-green-400" : "text-red-400"
          }`}>
            {delta.direction === "up" ? "↑" : "↓"}{Math.abs(delta.pct)}%
          </span>
        )}
      </div>
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

function OutcomeBadge({ label, value }: { label: string; value: number | null }) {
  return (
    <div className={`flex items-center gap-1 px-2 py-0.5 rounded text-[10px] ${
      value === null
        ? "bg-[#1e293b] text-[#475569]"
        : value >= 0
        ? "bg-green-500/10 text-green-400"
        : "bg-red-500/10 text-red-400"
    }`}>
      <span className="font-medium">{label}</span>
      <span>{value !== null ? `${value > 0 ? "+" : ""}${value.toFixed(1)}%` : "—"}</span>
    </div>
  );
}

function QuickAction({ label, icon, loading, onClick, color }: {
  label: string;
  icon: React.ReactNode;
  loading: boolean;
  onClick: () => void;
  color: "violet" | "cyan" | "amber";
}) {
  const colors = {
    violet: "bg-violet-500/15 text-violet-400 hover:bg-violet-500/25 border-violet-500/20",
    cyan: "bg-cyan-500/15 text-cyan-400 hover:bg-cyan-500/25 border-cyan-500/20",
    amber: "bg-amber-500/15 text-amber-400 hover:bg-amber-500/25 border-amber-500/20",
  };
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition whitespace-nowrap disabled:opacity-40 ${colors[color]}`}
    >
      {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : icon}
      {label}
    </button>
  );
}

// FIX 4: SVG Performance Sparkline Chart
function PerformanceChart({ data, isHe }: { data: AdminData["performance"]; isHe: boolean }) {
  // Reverse so oldest is on the left
  const sorted = [...data].reverse();
  if (sorted.length < 2) return null;

  const values = sorted.map((p) => p.cumulative_pnl_pct);
  const benchmarks = sorted.map((p) => p.benchmark_pnl_pct);
  const minVal = Math.min(...values, ...benchmarks.filter((b): b is number => b !== null), 0);
  const maxVal = Math.max(...values, ...benchmarks.filter((b): b is number => b !== null), 0);
  const range = maxVal - minVal || 1;

  const W = 600;
  const H = 120;
  const padY = 8;

  const toY = (v: number) => padY + ((maxVal - v) / range) * (H - padY * 2);
  const toX = (i: number) => (i / (sorted.length - 1)) * W;

  const portfolioPath = sorted
    .map((_, i) => `${i === 0 ? "M" : "L"} ${toX(i).toFixed(1)} ${toY(values[i]).toFixed(1)}`)
    .join(" ");

  const benchPath = sorted
    .filter((_, i) => benchmarks[i] !== null)
    .map((_, idx) => {
      const origIdx = sorted.findIndex((__, i) => {
        let count = 0;
        for (let j = 0; j <= i; j++) { if (benchmarks[j] !== null) count++; }
        return count === idx + 1;
      });
      return `${idx === 0 ? "M" : "L"} ${toX(origIdx).toFixed(1)} ${toY(benchmarks[origIdx]!).toFixed(1)}`;
    })
    .join(" ");

  // Fill area under portfolio line
  const fillPath = `${portfolioPath} L ${toX(sorted.length - 1).toFixed(1)} ${toY(0).toFixed(1)} L ${toX(0).toFixed(1)} ${toY(0).toFixed(1)} Z`;

  const lastVal = values[values.length - 1];
  const lastBench = benchmarks[benchmarks.length - 1];

  return (
    <div>
      <div className="flex items-center gap-4 mb-2">
        <div className="flex items-center gap-1.5 text-[10px]">
          <div className="w-3 h-0.5 rounded bg-cyan-400" />
          <span className="text-[#94a3b8]">{isHe ? "תיק" : "Portfolio"}: <span className={`font-medium ${lastVal >= 0 ? "text-green-400" : "text-red-400"}`}>{lastVal >= 0 ? "+" : ""}{lastVal.toFixed(2)}%</span></span>
        </div>
        {lastBench !== null && (
          <div className="flex items-center gap-1.5 text-[10px]">
            <div className="w-3 h-0.5 rounded bg-amber-400/50" />
            <span className="text-[#94a3b8]">SPY: <span className="text-[#64748b]">{lastBench >= 0 ? "+" : ""}{lastBench.toFixed(2)}%</span></span>
          </div>
        )}
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-28" preserveAspectRatio="none">
        {/* Zero line */}
        <line x1="0" y1={toY(0)} x2={W} y2={toY(0)} stroke="#334155" strokeWidth="0.5" strokeDasharray="4 4" />

        {/* Fill under portfolio */}
        <path d={fillPath} fill={lastVal >= 0 ? "rgba(34,211,238,0.06)" : "rgba(239,68,68,0.06)"} />

        {/* Benchmark line */}
        {benchPath && (
          <path d={benchPath} fill="none" stroke="#f59e0b" strokeWidth="1" strokeOpacity="0.35" />
        )}

        {/* Portfolio line */}
        <path d={portfolioPath} fill="none" stroke={lastVal >= 0 ? "#22d3ee" : "#ef4444"} strokeWidth="1.5" />

        {/* Regime dots */}
        {sorted.map((p, i) => {
          if (p.regime === "volatile") {
            return <circle key={i} cx={toX(i)} cy={toY(values[i])} r="2" fill="#ef4444" opacity="0.5" />;
          }
          return null;
        })}
      </svg>
      <div className="flex justify-between text-[8px] text-[#475569] mt-0.5">
        <span>{sorted[0]?.date}</span>
        <span>{sorted[sorted.length - 1]?.date}</span>
      </div>
    </div>
  );
}
