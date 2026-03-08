"use client";
import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { useI18n } from "@/i18n/context";
import type { ExpenseReceipt, ExpenseSummary } from "@/lib/types";
import {
  getExpenseSummary,
  scanReceipt,
  addManualReceipt,
  deleteReceipt,
  updateReceipt,
  exportReceipts,
  scanEmails,
  testEmailConnection,
} from "@/lib/api";
import {
  Receipt,
  Upload,
  Mail,
  Plus,
  Trash2,
  Download,
  CheckCircle,
  XCircle,
  Clock,
  Edit3,
  Save,
  X,
  Camera,
  RefreshCw,
  FileText,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Shield,
  ShieldCheck,
  Eye,
  EyeOff,
  Smartphone,
  Zap,
  PieChart,
  ArrowUpDown,
  Search,
} from "lucide-react";

// ── Constants ──

const CATEGORY_LABELS: Record<string, { he: string; en: string; emoji: string; color: string }> = {
  office_supplies: { he: "ציוד משרדי", en: "Office", emoji: "📎", color: "#3b82f6" },
  travel: { he: "נסיעות", en: "Travel", emoji: "✈️", color: "#8b5cf6" },
  meals: { he: "ארוחות", en: "Meals", emoji: "🍽️", color: "#f59e0b" },
  phone_internet: { he: "טלפון", en: "Phone", emoji: "📱", color: "#06b6d4" },
  software: { he: "תוכנה", en: "Software", emoji: "💻", color: "#6366f1" },
  professional_services: { he: "שירותים", en: "Services", emoji: "👔", color: "#ec4899" },
  insurance: { he: "ביטוח", en: "Insurance", emoji: "🛡️", color: "#14b8a6" },
  rent: { he: "שכירות", en: "Rent", emoji: "🏠", color: "#f97316" },
  utilities: { he: "חשבונות", en: "Utilities", emoji: "⚡", color: "#eab308" },
  vehicle: { he: "רכב", en: "Vehicle", emoji: "🚗", color: "#ef4444" },
  education: { he: "לימודים", en: "Education", emoji: "📚", color: "#a855f7" },
  marketing: { he: "שיווק", en: "Marketing", emoji: "📢", color: "#f43f5e" },
  equipment: { he: "ציוד", en: "Equipment", emoji: "🔧", color: "#78716c" },
  medical: { he: "רפואי", en: "Medical", emoji: "🏥", color: "#22c55e" },
  donations: { he: "תרומות", en: "Donations", emoji: "🤝", color: "#d946ef" },
  other: { he: "אחר", en: "Other", emoji: "📋", color: "#64748b" },
};

type View = "home" | "scan" | "email" | "manual" | "detail" | "export";

// ── Donut Chart Component ──

function DonutChart({
  data,
  total,
  locale,
}: {
  data: Record<string, number>;
  total: number;
  locale: string;
}) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  if (entries.length === 0)
    return null;

  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;

  return (
    <div className="flex items-center gap-4">
      <svg viewBox="0 0 100 100" className="w-24 h-24 shrink-0 -rotate-90">
        {entries.map(([cat, amount]) => {
          const pct = total > 0 ? amount / total : 0;
          const dashLength = pct * circumference;
          const color = CATEGORY_LABELS[cat]?.color || "#64748b";
          const segment = (
            <circle
              key={cat}
              cx="50"
              cy="50"
              r={radius}
              fill="none"
              stroke={color}
              strokeWidth="16"
              strokeDasharray={`${dashLength} ${circumference - dashLength}`}
              strokeDashoffset={-offset}
              className="transition-all duration-500"
            />
          );
          offset += dashLength;
          return segment;
        })}
        <circle cx="50" cy="50" r="30" fill="#0f172a" />
      </svg>
      <div className="flex flex-wrap gap-x-3 gap-y-1">
        {entries.slice(0, 5).map(([cat, amount]) => (
          <div key={cat} className="flex items-center gap-1.5">
            <div
              className="w-2 h-2 rounded-full shrink-0"
              style={{ backgroundColor: CATEGORY_LABELS[cat]?.color || "#64748b" }}
            />
            <span className="text-[10px] text-[#94a3b8]">
              {CATEGORY_LABELS[cat]?.[locale as "he" | "en"] || cat}
            </span>
            <span className="text-[10px] font-medium text-white">
              ₪{Math.round(amount).toLocaleString()}
            </span>
          </div>
        ))}
        {entries.length > 5 && (
          <span className="text-[10px] text-[#475569]">
            +{entries.length - 5} {locale === "he" ? "עוד" : "more"}
          </span>
        )}
      </div>
    </div>
  );
}

// ── Progress Ring (confidence) ──

function ConfidenceRing({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const r = 10;
  const c = 2 * Math.PI * r;
  const dash = pct / 100 * c;
  const color = pct >= 80 ? "#22c55e" : pct >= 50 ? "#eab308" : "#ef4444";

  return (
    <div className="relative w-7 h-7 shrink-0" title={`${pct}%`}>
      <svg viewBox="0 0 24 24" className="w-full h-full -rotate-90">
        <circle cx="12" cy="12" r={r} fill="none" stroke="#1e293b" strokeWidth="2.5" />
        <circle
          cx="12"
          cy="12"
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="2.5"
          strokeDasharray={`${dash} ${c - dash}`}
          strokeLinecap="round"
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-[7px] font-bold text-white">
        {pct}
      </span>
    </div>
  );
}

// ══════════════════════════════════════
// MAIN COMPONENT
// ══════════════════════════════════════

export default function ExpenseReceipts() {
  const { locale } = useI18n();
  const isHe = locale === "he";
  const L = (he: string, en: string) => (isHe ? he : en);

  const [view, setView] = useState<View>("home");
  const [summary, setSummary] = useState<ExpenseSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortAsc, setSortAsc] = useState(false);
  const [filterCat, setFilterCat] = useState("");
  const [showFilters, setShowFilters] = useState(false);

  // Detail / edit
  const [selectedReceipt, setSelectedReceipt] = useState<ExpenseReceipt | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editData, setEditData] = useState<Partial<ExpenseReceipt>>({});

  // Scan
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<string>("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);

  // Email
  const [emailConfig, setEmailConfig] = useState({
    email_address: "",
    imap_server: "imap.gmail.com",
    imap_port: 993,
    password: "",
    days_back: 30,
  });
  const [emailTesting, setEmailTesting] = useState(false);
  const [emailScanning, setEmailScanning] = useState(false);
  const [emailResult, setEmailResult] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  // Manual entry
  const [manualEntry, setManualEntry] = useState({
    vendor_name: "",
    amount: "",
    currency: "ILS",
    receipt_date: new Date().toISOString().split("T")[0],
    receipt_number: "",
    description: "",
    category: "other",
    tax_deductible: false,
  });

  // ── Data Loading ──

  const loadSummary = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await getExpenseSummary();
      setSummary(data);
    } catch {
      setError(L("שגיאה בטעינת נתונים", "Error loading data"));
    } finally {
      setLoading(false);
    }
  }, [isHe]);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  // ── Filtered & sorted receipts ──

  const filteredReceipts = useMemo(() => {
    let list = summary?.receipts || [];
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      list = list.filter(
        (r) =>
          r.vendor_name.toLowerCase().includes(q) ||
          r.description.toLowerCase().includes(q) ||
          r.receipt_number.toLowerCase().includes(q)
      );
    }
    if (filterCat) {
      list = list.filter((r) => r.category === filterCat);
    }
    if (sortAsc) {
      list = [...list].sort((a, b) => a.amount - b.amount);
    }
    return list;
  }, [summary, searchQuery, filterCat, sortAsc]);

  // ── Image Scan ──

  const processFile = useCallback(
    async (file: File) => {
      setScanning(true);
      setScanResult("");
      setView("scan");

      const reader = new FileReader();
      reader.onload = async () => {
        const base64 = (reader.result as string).split(",")[1];
        const mediaType = file.type || "image/jpeg";
        try {
          const result = await scanReceipt(base64, mediaType, file.name);
          if (result.is_receipt) {
            const d = result.data as Record<string, unknown>;
            setScanResult(
              L(
                `קבלה זוהתה! ${d?.vendor_name || ""} · ₪${d?.amount || 0}`,
                `Receipt found! ${d?.vendor_name || ""} · ₪${d?.amount || 0}`
              )
            );
            await loadSummary();
          } else {
            setScanResult(L("לא זוהתה קבלה בתמונה", "No receipt detected"));
          }
        } catch {
          setScanResult(L("שגיאה בסריקה", "Scan error"));
        }
        setScanning(false);
      };
      reader.readAsDataURL(file);
    },
    [isHe, loadSummary]
  );

  const handleFileUpload = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) processFile(file);
    },
    [processFile]
  );

  // ── Email ──

  const handleTestEmail = useCallback(async () => {
    setEmailTesting(true);
    setEmailResult("");
    try {
      const r = await testEmailConnection(emailConfig);
      setEmailResult(
        r.success
          ? L(`חיבור הצליח! ${r.message_count} הודעות`, `Connected! ${r.message_count} messages`)
          : L(`חיבור נכשל: ${r.error}`, `Failed: ${r.error}`)
      );
    } catch {
      setEmailResult(L("שגיאת חיבור", "Connection error"));
    }
    setEmailTesting(false);
  }, [emailConfig, isHe]);

  const handleScanEmails = useCallback(async () => {
    setEmailScanning(true);
    setEmailResult("");
    try {
      const r = await scanEmails(emailConfig);
      setEmailResult(
        L(
          `נסרקו ${r.emails_scanned} מיילים, נמצאו ${r.receipts_found} קבלות`,
          `Scanned ${r.emails_scanned} emails, found ${r.receipts_found} receipts`
        )
      );
      if (r.receipts_found > 0) await loadSummary();
    } catch {
      setEmailResult(L("שגיאה בסריקה", "Scan error"));
    }
    setEmailScanning(false);
  }, [emailConfig, isHe, loadSummary]);

  // ── Manual ──

  const handleManualSubmit = useCallback(async () => {
    if (!manualEntry.vendor_name || !manualEntry.amount) return;
    setLoading(true);
    try {
      await addManualReceipt({
        ...manualEntry,
        amount: parseFloat(manualEntry.amount),
      });
      setManualEntry({
        vendor_name: "",
        amount: "",
        currency: "ILS",
        receipt_date: new Date().toISOString().split("T")[0],
        receipt_number: "",
        description: "",
        category: "other",
        tax_deductible: false,
      });
      await loadSummary();
      setView("home");
    } catch {
      setError(L("שגיאה בשמירה", "Save error"));
    }
    setLoading(false);
  }, [manualEntry, isHe, loadSummary]);

  // ── Actions ──

  const handleDelete = useCallback(
    async (id: number) => {
      try {
        await deleteReceipt(id);
        setSelectedReceipt(null);
        setView("home");
        await loadSummary();
      } catch {
        setError(L("שגיאה במחיקה", "Delete error"));
      }
    },
    [isHe, loadSummary]
  );

  const handleSaveEdit = useCallback(
    async (id: number) => {
      try {
        await updateReceipt(id, editData);
        setEditingId(null);
        setEditData({});
        await loadSummary();
      } catch {
        setError(L("שגיאה בעדכון", "Update error"));
      }
    },
    [editData, isHe, loadSummary]
  );

  const handleExport = useCallback(
    async (format: "json" | "csv") => {
      try {
        const result = await exportReceipts(format);
        const content = format === "csv" && result.data
          ? "\uFEFF" + result.data
          : JSON.stringify(result, null, 2);
        const blob = new Blob([content], {
          type: format === "csv" ? "text/csv;charset=utf-8" : "application/json",
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `receipts_${new Date().toISOString().split("T")[0]}.${format}`;
        a.click();
        URL.revokeObjectURL(url);
      } catch {
        setError(L("שגיאה בייצוא", "Export error"));
      }
    },
    [isHe]
  );

  // ── Formatters ──

  const fmtDate = (d: string | null) => {
    if (!d) return "";
    try {
      return new Date(d).toLocaleDateString(isHe ? "he-IL" : "en-US", {
        day: "numeric",
        month: "short",
      });
    } catch {
      return d;
    }
  };

  const fmtCurrency = (amount: number, currency = "ILS") => {
    const sym = currency === "ILS" ? "₪" : currency === "USD" ? "$" : currency === "EUR" ? "€" : currency;
    return `${sym}${amount.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
  };

  // ── Swipe to delete ──
  const [swipingId, setSwipingId] = useState<number | null>(null);

  // ══════════════════════════════════════
  // RENDER
  // ══════════════════════════════════════

  return (
    <div className="relative min-h-[calc(100vh-8rem)] pb-24">
      {/* ── Error Toast ── */}
      {error && (
        <div className="fixed top-4 left-4 right-4 z-50 bg-red-500/90 backdrop-blur text-white px-4 py-3 rounded-2xl flex items-center gap-2 text-sm shadow-lg animate-in slide-in-from-top">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span className="flex-1">{error}</span>
          <button onClick={() => setError("")}>
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* ═══════════════════════════════════════
           HOME VIEW
         ═══════════════════════════════════════ */}
      {view === "home" && (
        <div className="space-y-4">
          {/* ── Header ── */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-white">{L("הקבלות שלי", "My Receipts")}</h1>
              <p className="text-xs text-[#64748b] mt-0.5">{L("סריקה · קטלוג · ייצוא למס", "Scan · Catalog · Tax Export")}</p>
            </div>
            <button
              onClick={loadSummary}
              className="p-2.5 rounded-xl bg-[#1e293b] active:bg-[#334155] transition"
            >
              <RefreshCw className={`w-5 h-5 text-cyan-400 ${loading ? "animate-spin" : ""}`} />
            </button>
          </div>

          {/* ── Summary Hero Card ── */}
          {summary && (
            <div className="bg-gradient-to-br from-cyan-500/20 via-[#1e293b] to-[#1e293b] rounded-2xl p-5 space-y-4">
              <div className="flex justify-between items-start">
                <div>
                  <div className="text-xs text-cyan-300/70 mb-1">{L("סה״כ הוצאות", "Total Expenses")}</div>
                  <div className="text-3xl font-bold text-white tracking-tight">
                    ₪{summary.total_amount.toLocaleString()}
                  </div>
                </div>
                <div className="text-left">
                  <div className="text-xs text-green-400/70 mb-1">{L("להחזר מס", "Tax Refund")}</div>
                  <div className="text-xl font-bold text-green-400">
                    ₪{summary.tax_deductible_amount.toLocaleString()}
                  </div>
                </div>
              </div>

              {/* Stats row */}
              <div className="flex gap-3">
                <div className="flex-1 bg-white/5 rounded-xl px-3 py-2 text-center">
                  <div className="text-lg font-bold text-white">{summary.total_receipts}</div>
                  <div className="text-[10px] text-[#94a3b8]">{L("קבלות", "Receipts")}</div>
                </div>
                <div className="flex-1 bg-white/5 rounded-xl px-3 py-2 text-center">
                  <div className="text-lg font-bold text-cyan-400">
                    {Object.keys(summary.by_category).length}
                  </div>
                  <div className="text-[10px] text-[#94a3b8]">{L("קטגוריות", "Categories")}</div>
                </div>
                <div className="flex-1 bg-white/5 rounded-xl px-3 py-2 text-center">
                  <div className="text-lg font-bold text-green-400">
                    {summary.total_amount > 0
                      ? Math.round((summary.tax_deductible_amount / summary.total_amount) * 100)
                      : 0}
                    %
                  </div>
                  <div className="text-[10px] text-[#94a3b8]">{L("לניכוי", "Deductible")}</div>
                </div>
              </div>

              {/* Donut chart */}
              {Object.keys(summary.by_category).length > 0 && (
                <DonutChart data={summary.by_category} total={summary.total_amount} locale={locale} />
              )}
            </div>
          )}

          {/* ── Quick Actions Grid ── */}
          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={() => cameraInputRef.current?.click()}
              className="bg-cyan-500/10 border border-cyan-500/20 rounded-2xl p-4 flex flex-col items-center gap-2 active:bg-cyan-500/20 transition"
            >
              <div className="w-12 h-12 bg-cyan-500/20 rounded-2xl flex items-center justify-center">
                <Camera className="w-6 h-6 text-cyan-400" />
              </div>
              <span className="text-sm font-medium text-white">{L("צלם קבלה", "Snap Receipt")}</span>
              <span className="text-[10px] text-[#64748b]">{L("מצלמת הנייד", "Phone camera")}</span>
            </button>

            <button
              onClick={() => fileInputRef.current?.click()}
              className="bg-purple-500/10 border border-purple-500/20 rounded-2xl p-4 flex flex-col items-center gap-2 active:bg-purple-500/20 transition"
            >
              <div className="w-12 h-12 bg-purple-500/20 rounded-2xl flex items-center justify-center">
                <Upload className="w-6 h-6 text-purple-400" />
              </div>
              <span className="text-sm font-medium text-white">{L("העלה תמונה", "Upload Image")}</span>
              <span className="text-[10px] text-[#64748b]">{L("מהגלריה", "From gallery")}</span>
            </button>

            <button
              onClick={() => setView("email")}
              className="bg-amber-500/10 border border-amber-500/20 rounded-2xl p-4 flex flex-col items-center gap-2 active:bg-amber-500/20 transition"
            >
              <div className="w-12 h-12 bg-amber-500/20 rounded-2xl flex items-center justify-center">
                <Mail className="w-6 h-6 text-amber-400" />
              </div>
              <span className="text-sm font-medium text-white">{L("סרוק מיילים", "Scan Emails")}</span>
              <span className="text-[10px] text-[#64748b]">{L("חשבוניות דיגיטליות", "Digital invoices")}</span>
            </button>

            <button
              onClick={() => setView("manual")}
              className="bg-emerald-500/10 border border-emerald-500/20 rounded-2xl p-4 flex flex-col items-center gap-2 active:bg-emerald-500/20 transition"
            >
              <div className="w-12 h-12 bg-emerald-500/20 rounded-2xl flex items-center justify-center">
                <Edit3 className="w-6 h-6 text-emerald-400" />
              </div>
              <span className="text-sm font-medium text-white">{L("הוסף ידנית", "Add Manual")}</span>
              <span className="text-[10px] text-[#64748b]">{L("הזנה ידנית", "Manual entry")}</span>
            </button>
          </div>

          {/* Hidden file inputs */}
          <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={handleFileUpload} />
          <input ref={cameraInputRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={handleFileUpload} />

          {/* ── Search + Filter bar ── */}
          {(summary?.total_receipts ?? 0) > 0 && (
            <div className="space-y-2">
              <div className="flex gap-2">
                <div className="flex-1 relative">
                  <Search className="w-4 h-4 absolute right-3 top-1/2 -translate-y-1/2 text-[#64748b]" />
                  <input
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder={L("חפש ספק, תיאור...", "Search vendor, desc...")}
                    className="w-full bg-[#1e293b] text-white text-sm pl-3 pr-10 py-2.5 rounded-xl border border-[#334155] placeholder:text-[#475569]"
                  />
                </div>
                <button
                  onClick={() => setSortAsc(!sortAsc)}
                  className={`p-2.5 rounded-xl border transition ${
                    sortAsc ? "bg-cyan-500/20 border-cyan-500/30 text-cyan-400" : "bg-[#1e293b] border-[#334155] text-[#94a3b8]"
                  }`}
                >
                  <ArrowUpDown className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setShowFilters(!showFilters)}
                  className={`p-2.5 rounded-xl border transition ${
                    filterCat ? "bg-cyan-500/20 border-cyan-500/30 text-cyan-400" : "bg-[#1e293b] border-[#334155] text-[#94a3b8]"
                  }`}
                >
                  <PieChart className="w-4 h-4" />
                </button>
              </div>

              {/* Category filter chips */}
              {showFilters && (
                <div className="flex gap-1.5 overflow-x-auto pb-1 scrollbar-hide">
                  <button
                    onClick={() => setFilterCat("")}
                    className={`shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition ${
                      !filterCat ? "bg-cyan-500 text-white" : "bg-[#1e293b] text-[#94a3b8]"
                    }`}
                  >
                    {L("הכל", "All")}
                  </button>
                  {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
                    <button
                      key={key}
                      onClick={() => setFilterCat(filterCat === key ? "" : key)}
                      className={`shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition flex items-center gap-1 ${
                        filterCat === key ? "bg-cyan-500 text-white" : "bg-[#1e293b] text-[#94a3b8]"
                      }`}
                    >
                      <span>{label.emoji}</span>
                      {label[locale as "he" | "en"]}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── Receipt List ── */}
          {filteredReceipts.length === 0 && !loading ? (
            <div className="text-center py-16">
              <div className="w-20 h-20 bg-[#1e293b] rounded-3xl flex items-center justify-center mx-auto mb-4">
                <Receipt className="w-10 h-10 text-[#334155]" />
              </div>
              <p className="text-[#94a3b8] font-medium">{L("אין קבלות עדיין", "No receipts yet")}</p>
              <p className="text-xs text-[#475569] mt-1">
                {L("צלם, העלה, או סרוק מיילים כדי להתחיל", "Snap, upload, or scan emails to start")}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              <div className="flex items-center justify-between px-1">
                <span className="text-xs text-[#64748b]">
                  {filteredReceipts.length} {L("קבלות", "receipts")}
                </span>
                <button
                  onClick={() => setView("export")}
                  className="text-xs text-cyan-400 flex items-center gap-1"
                >
                  <Download className="w-3 h-3" />
                  {L("ייצוא", "Export")}
                </button>
              </div>

              {filteredReceipts.map((r) => {
                const cat = CATEGORY_LABELS[r.category] || CATEGORY_LABELS.other;
                const isOpen = swipingId === r.id;

                return (
                  <div key={r.id} className="relative overflow-hidden rounded-2xl">
                    {/* Swipe action */}
                    {isOpen && (
                      <div className="absolute inset-y-0 left-0 w-20 bg-red-500 flex items-center justify-center rounded-r-2xl z-0">
                        <button onClick={() => handleDelete(r.id)}>
                          <Trash2 className="w-5 h-5 text-white" />
                        </button>
                      </div>
                    )}

                    {/* Card */}
                    <div
                      className={`relative z-10 bg-[#1e293b] p-3.5 flex items-center gap-3 active:bg-[#253348] transition-all cursor-pointer ${
                        isOpen ? "translate-x-20" : ""
                      }`}
                      onClick={() => {
                        if (isOpen) {
                          setSwipingId(null);
                        } else {
                          setSelectedReceipt(r);
                          setView("detail");
                        }
                      }}
                      onContextMenu={(e) => {
                        e.preventDefault();
                        setSwipingId(isOpen ? null : r.id);
                      }}
                    >
                      {/* Category icon */}
                      <div
                        className="w-11 h-11 rounded-xl flex items-center justify-center text-xl shrink-0"
                        style={{ backgroundColor: cat.color + "20" }}
                      >
                        {cat.emoji}
                      </div>

                      {/* Info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="font-medium text-white text-sm truncate">
                            {r.vendor_name || L("ספק לא ידוע", "Unknown")}
                          </span>
                          {r.tax_deductible && (
                            <ShieldCheck className="w-3.5 h-3.5 text-green-400 shrink-0" />
                          )}
                        </div>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-[10px] text-[#64748b]">
                            {fmtDate(r.receipt_date || r.created_at)}
                          </span>
                          {r.description && (
                            <span className="text-[10px] text-[#475569] truncate max-w-[120px]">
                              {r.description}
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Amount + confidence */}
                      <div className="text-left shrink-0 flex items-center gap-2">
                        {r.confidence_score > 0 && r.confidence_score < 1 && (
                          <ConfidenceRing score={r.confidence_score} />
                        )}
                        <div>
                          <div className="text-sm font-bold text-white">{fmtCurrency(r.amount, r.currency)}</div>
                          <div className="text-[10px] text-[#64748b] text-left">
                            {r.source_type === "email" ? "📧" : r.source_type === "screenshot" ? "📸" : r.source_type === "upload" ? "📤" : "✏️"}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ═══════════════════════════════════════
           SCAN VIEW (result screen)
         ═══════════════════════════════════════ */}
      {view === "scan" && (
        <div className="space-y-6">
          <button onClick={() => setView("home")} className="flex items-center gap-2 text-[#94a3b8] text-sm">
            <ChevronDown className="w-4 h-4 rotate-90" />
            {L("חזרה", "Back")}
          </button>

          <div className="text-center space-y-4">
            {scanning ? (
              <>
                <div className="w-24 h-24 bg-cyan-500/10 rounded-3xl flex items-center justify-center mx-auto">
                  <RefreshCw className="w-10 h-10 text-cyan-400 animate-spin" />
                </div>
                <div>
                  <p className="text-white font-medium">{L("סורק עם AI...", "Scanning with AI...")}</p>
                  <p className="text-xs text-[#64748b] mt-1">{L("מזהה פרטי קבלה", "Identifying receipt details")}</p>
                </div>
                {/* Animated dots */}
                <div className="flex justify-center gap-1">
                  {[0, 1, 2].map((i) => (
                    <div
                      key={i}
                      className="w-2 h-2 bg-cyan-400 rounded-full animate-bounce"
                      style={{ animationDelay: `${i * 150}ms` }}
                    />
                  ))}
                </div>
              </>
            ) : scanResult ? (
              <>
                <div
                  className={`w-24 h-24 rounded-3xl flex items-center justify-center mx-auto ${
                    scanResult.includes("₪") ? "bg-green-500/10" : "bg-yellow-500/10"
                  }`}
                >
                  {scanResult.includes("₪") ? (
                    <CheckCircle className="w-10 h-10 text-green-400" />
                  ) : (
                    <AlertCircle className="w-10 h-10 text-yellow-400" />
                  )}
                </div>
                <p className="text-white font-medium">{scanResult}</p>
                <div className="flex gap-3 justify-center">
                  <button
                    onClick={() => {
                      setScanResult("");
                      cameraInputRef.current?.click();
                    }}
                    className="px-5 py-2.5 bg-cyan-500 text-white rounded-xl text-sm font-medium"
                  >
                    {L("סרוק עוד", "Scan More")}
                  </button>
                  <button
                    onClick={() => setView("home")}
                    className="px-5 py-2.5 bg-[#1e293b] text-white rounded-xl text-sm font-medium"
                  >
                    {L("סיום", "Done")}
                  </button>
                </div>
              </>
            ) : (
              <div className="space-y-4">
                <div className="w-24 h-24 bg-[#1e293b] rounded-3xl flex items-center justify-center mx-auto">
                  <Camera className="w-10 h-10 text-[#475569]" />
                </div>
                <p className="text-[#94a3b8]">{L("בחר תמונה לסריקה", "Choose an image to scan")}</p>
              </div>
            )}
          </div>

          {/* Hidden inputs */}
          <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={handleFileUpload} />
          <input ref={cameraInputRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={handleFileUpload} />
        </div>
      )}

      {/* ═══════════════════════════════════════
           DETAIL VIEW
         ═══════════════════════════════════════ */}
      {view === "detail" && selectedReceipt && (
        <div className="space-y-4">
          <button onClick={() => { setView("home"); setEditingId(null); }} className="flex items-center gap-2 text-[#94a3b8] text-sm">
            <ChevronDown className="w-4 h-4 rotate-90" />
            {L("חזרה", "Back")}
          </button>

          {(() => {
            const r = selectedReceipt;
            const cat = CATEGORY_LABELS[r.category] || CATEGORY_LABELS.other;
            const isEditing = editingId === r.id;

            return (
              <div className="space-y-4">
                {/* Header */}
                <div className="bg-[#1e293b] rounded-2xl p-5 text-center space-y-3">
                  <div
                    className="w-16 h-16 rounded-2xl flex items-center justify-center text-3xl mx-auto"
                    style={{ backgroundColor: cat.color + "20" }}
                  >
                    {cat.emoji}
                  </div>
                  <div>
                    {isEditing ? (
                      <input
                        value={editData.vendor_name ?? r.vendor_name}
                        onChange={(e) => setEditData({ ...editData, vendor_name: e.target.value })}
                        className="w-full bg-[#0f172a] text-white text-center text-lg font-bold px-3 py-2 rounded-xl border border-[#334155]"
                      />
                    ) : (
                      <h2 className="text-xl font-bold text-white">
                        {r.vendor_name || L("ספק לא ידוע", "Unknown Vendor")}
                      </h2>
                    )}
                  </div>

                  {isEditing ? (
                    <div className="flex gap-2 justify-center">
                      <input
                        type="number"
                        value={editData.amount ?? r.amount}
                        onChange={(e) => setEditData({ ...editData, amount: parseFloat(e.target.value) })}
                        className="w-32 bg-[#0f172a] text-white text-center text-2xl font-bold px-3 py-2 rounded-xl border border-[#334155]"
                      />
                    </div>
                  ) : (
                    <div className="text-3xl font-bold text-white">{fmtCurrency(r.amount, r.currency)}</div>
                  )}

                  {r.tax_deductible && (
                    <div className="inline-flex items-center gap-1.5 bg-green-500/10 text-green-400 px-3 py-1 rounded-full text-xs font-medium">
                      <ShieldCheck className="w-3.5 h-3.5" />
                      {L("ניתן לניכוי מס", "Tax Deductible")}
                    </div>
                  )}
                </div>

                {/* Details grid */}
                <div className="bg-[#1e293b] rounded-2xl divide-y divide-[#334155]">
                  {[
                    { label: L("קטגוריה", "Category"), value: `${cat.emoji} ${cat[locale as "he" | "en"]}` },
                    { label: L("תאריך", "Date"), value: r.receipt_date || fmtDate(r.created_at) },
                    { label: L("מספר קבלה", "Receipt #"), value: r.receipt_number || "—" },
                    { label: L("תיאור", "Description"), value: r.description || "—" },
                    { label: L("מקור", "Source"), value: r.source_type === "email" ? L("מייל", "Email") : r.source_type === "screenshot" ? L("צילום מסך", "Screenshot") : r.source_type === "upload" ? L("העלאה", "Upload") : L("ידני", "Manual") },
                    { label: L("ביטחון AI", "AI Confidence"), value: r.confidence_score > 0 ? `${Math.round(r.confidence_score * 100)}%` : "—" },
                    { label: L("סטטוס", "Status"), value: r.status === "verified" ? L("מאומת", "Verified") : r.status === "exported" ? L("יוצא", "Exported") : L("ממתין", "Pending") },
                  ].map(({ label, value }) => (
                    <div key={label} className="flex justify-between items-center px-4 py-3">
                      <span className="text-sm text-[#94a3b8]">{label}</span>
                      <span className="text-sm text-white font-medium">{value}</span>
                    </div>
                  ))}
                </div>

                {/* Edit category (when editing) */}
                {isEditing && (
                  <div className="bg-[#1e293b] rounded-2xl p-4 space-y-3">
                    <label className="text-xs text-[#94a3b8]">{L("שנה קטגוריה", "Change Category")}</label>
                    <div className="grid grid-cols-4 gap-2">
                      {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
                        <button
                          key={key}
                          onClick={() => setEditData({ ...editData, category: key })}
                          className={`p-2 rounded-xl text-center transition ${
                            (editData.category ?? r.category) === key
                              ? "bg-cyan-500/20 ring-1 ring-cyan-500"
                              : "bg-[#0f172a]"
                          }`}
                        >
                          <div className="text-lg">{label.emoji}</div>
                          <div className="text-[9px] text-[#94a3b8] mt-0.5">{label[locale as "he" | "en"]}</div>
                        </button>
                      ))}
                    </div>
                    <label className="flex items-center gap-2 text-sm text-[#94a3b8] cursor-pointer">
                      <input
                        type="checkbox"
                        checked={editData.tax_deductible ?? r.tax_deductible}
                        onChange={(e) => setEditData({ ...editData, tax_deductible: e.target.checked })}
                        className="accent-cyan-400 w-4 h-4"
                      />
                      {L("ניתן לניכוי מס", "Tax Deductible")}
                    </label>
                  </div>
                )}

                {/* Action buttons */}
                <div className="flex gap-3">
                  {isEditing ? (
                    <>
                      <button
                        onClick={() => handleSaveEdit(r.id)}
                        className="flex-1 py-3 bg-cyan-500 text-white rounded-xl text-sm font-medium flex items-center justify-center gap-2"
                      >
                        <Save className="w-4 h-4" />
                        {L("שמור", "Save")}
                      </button>
                      <button
                        onClick={() => { setEditingId(null); setEditData({}); }}
                        className="py-3 px-5 bg-[#1e293b] text-[#94a3b8] rounded-xl text-sm"
                      >
                        {L("ביטול", "Cancel")}
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        onClick={() => { setEditingId(r.id); setEditData({}); }}
                        className="flex-1 py-3 bg-[#1e293b] text-white rounded-xl text-sm font-medium flex items-center justify-center gap-2"
                      >
                        <Edit3 className="w-4 h-4" />
                        {L("ערוך", "Edit")}
                      </button>
                      <button
                        onClick={() => handleDelete(r.id)}
                        className="py-3 px-5 bg-red-500/10 text-red-400 rounded-xl text-sm flex items-center justify-center gap-2"
                      >
                        <Trash2 className="w-4 h-4" />
                        {L("מחק", "Delete")}
                      </button>
                    </>
                  )}
                </div>
              </div>
            );
          })()}
        </div>
      )}

      {/* ═══════════════════════════════════════
           EMAIL VIEW
         ═══════════════════════════════════════ */}
      {view === "email" && (
        <div className="space-y-4">
          <button onClick={() => setView("home")} className="flex items-center gap-2 text-[#94a3b8] text-sm">
            <ChevronDown className="w-4 h-4 rotate-90" />
            {L("חזרה", "Back")}
          </button>

          <div className="bg-[#1e293b] rounded-2xl p-5 space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-amber-500/20 rounded-2xl flex items-center justify-center">
                <Mail className="w-6 h-6 text-amber-400" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">{L("סריקת מיילים", "Email Scan")}</h3>
                <p className="text-xs text-[#64748b]">{L("חיפוש חשבוניות דיגיטליות", "Find digital invoices")}</p>
              </div>
            </div>

            <div className="space-y-3">
              <input
                type="email"
                value={emailConfig.email_address}
                onChange={(e) => setEmailConfig({ ...emailConfig, email_address: e.target.value })}
                className="w-full bg-[#0f172a] text-white text-sm px-4 py-3 rounded-xl border border-[#334155]"
                placeholder={L("כתובת מייל", "Email address")}
              />

              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  value={emailConfig.password}
                  onChange={(e) => setEmailConfig({ ...emailConfig, password: e.target.value })}
                  className="w-full bg-[#0f172a] text-white text-sm pl-12 pr-4 py-3 rounded-xl border border-[#334155]"
                  placeholder={L("סיסמת אפליקציה", "App password")}
                />
                <button
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-[#64748b]"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>

              <div className="flex gap-3">
                <input
                  value={emailConfig.imap_server}
                  onChange={(e) => setEmailConfig({ ...emailConfig, imap_server: e.target.value })}
                  className="flex-1 bg-[#0f172a] text-white text-sm px-4 py-3 rounded-xl border border-[#334155]"
                  placeholder="IMAP Server"
                />
                <input
                  type="number"
                  value={emailConfig.days_back}
                  onChange={(e) => setEmailConfig({ ...emailConfig, days_back: parseInt(e.target.value) || 30 })}
                  className="w-20 bg-[#0f172a] text-white text-sm px-3 py-3 rounded-xl border border-[#334155] text-center"
                  min={1}
                  max={365}
                />
              </div>
            </div>

            {/* Security note */}
            <div className="flex items-start gap-2 bg-cyan-500/5 rounded-xl p-3">
              <Shield className="w-4 h-4 text-cyan-400 mt-0.5 shrink-0" />
              <p className="text-[10px] text-[#64748b] leading-relaxed">
                {L(
                  "הסיסמה לא נשמרת בשרת. לגימייל: הגדרות → אבטחה → סיסמאות אפליקציה",
                  "Password not stored on server. For Gmail: Settings → Security → App Passwords"
                )}
              </p>
            </div>

            <div className="flex gap-3">
              <button
                onClick={handleTestEmail}
                disabled={emailTesting || !emailConfig.email_address || !emailConfig.password}
                className="flex-1 py-3 bg-[#334155] text-white rounded-xl text-sm font-medium disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {emailTesting ? <RefreshCw className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
                {L("בדיקה", "Test")}
              </button>
              <button
                onClick={handleScanEmails}
                disabled={emailScanning || !emailConfig.email_address || !emailConfig.password}
                className="flex-1 py-3 bg-amber-500 text-white rounded-xl text-sm font-medium disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {emailScanning ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
                {L("סרוק", "Scan")}
              </button>
            </div>

            {emailResult && (
              <div
                className={`px-4 py-3 rounded-xl text-sm font-medium ${
                  emailResult.includes("נמצאו") || emailResult.includes("found") || emailResult.includes("הצליח") || emailResult.includes("Connected")
                    ? "bg-green-500/10 text-green-400"
                    : "bg-red-500/10 text-red-400"
                }`}
              >
                {emailResult}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════
           MANUAL ENTRY VIEW
         ═══════════════════════════════════════ */}
      {view === "manual" && (
        <div className="space-y-4">
          <button onClick={() => setView("home")} className="flex items-center gap-2 text-[#94a3b8] text-sm">
            <ChevronDown className="w-4 h-4 rotate-90" />
            {L("חזרה", "Back")}
          </button>

          <div className="bg-[#1e293b] rounded-2xl p-5 space-y-4">
            <h3 className="text-lg font-bold text-white">{L("הוספת קבלה", "Add Receipt")}</h3>

            {/* Amount — big input */}
            <div className="text-center py-4">
              <div className="flex items-center justify-center gap-2">
                <select
                  value={manualEntry.currency}
                  onChange={(e) => setManualEntry({ ...manualEntry, currency: e.target.value })}
                  className="bg-transparent text-2xl text-[#94a3b8] font-bold appearance-none text-center w-12"
                >
                  <option value="ILS">₪</option>
                  <option value="USD">$</option>
                  <option value="EUR">€</option>
                </select>
                <input
                  type="number"
                  step="0.01"
                  value={manualEntry.amount}
                  onChange={(e) => setManualEntry({ ...manualEntry, amount: e.target.value })}
                  className="bg-transparent text-4xl font-bold text-white text-center w-48 outline-none placeholder:text-[#334155]"
                  placeholder="0"
                />
              </div>
            </div>

            <input
              value={manualEntry.vendor_name}
              onChange={(e) => setManualEntry({ ...manualEntry, vendor_name: e.target.value })}
              className="w-full bg-[#0f172a] text-white text-sm px-4 py-3 rounded-xl border border-[#334155]"
              placeholder={L("שם ספק / עסק *", "Vendor name *")}
            />

            <input
              value={manualEntry.description}
              onChange={(e) => setManualEntry({ ...manualEntry, description: e.target.value })}
              className="w-full bg-[#0f172a] text-white text-sm px-4 py-3 rounded-xl border border-[#334155]"
              placeholder={L("תיאור", "Description")}
            />

            <div className="flex gap-3">
              <input
                type="date"
                value={manualEntry.receipt_date}
                onChange={(e) => setManualEntry({ ...manualEntry, receipt_date: e.target.value })}
                className="flex-1 bg-[#0f172a] text-white text-sm px-4 py-3 rounded-xl border border-[#334155]"
              />
              <input
                value={manualEntry.receipt_number}
                onChange={(e) => setManualEntry({ ...manualEntry, receipt_number: e.target.value })}
                className="flex-1 bg-[#0f172a] text-white text-sm px-4 py-3 rounded-xl border border-[#334155]"
                placeholder={L("מס׳ קבלה", "Receipt #")}
              />
            </div>

            {/* Category grid */}
            <div>
              <label className="text-xs text-[#64748b] block mb-2">{L("קטגוריה", "Category")}</label>
              <div className="grid grid-cols-4 gap-2">
                {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
                  <button
                    key={key}
                    onClick={() => setManualEntry({ ...manualEntry, category: key })}
                    className={`p-2.5 rounded-xl text-center transition ${
                      manualEntry.category === key
                        ? "bg-cyan-500/20 ring-1 ring-cyan-500"
                        : "bg-[#0f172a] active:bg-[#1e293b]"
                    }`}
                  >
                    <div className="text-lg">{label.emoji}</div>
                    <div className="text-[9px] text-[#94a3b8] mt-0.5 truncate">{label[locale as "he" | "en"]}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* Tax deductible toggle */}
            <button
              onClick={() => setManualEntry({ ...manualEntry, tax_deductible: !manualEntry.tax_deductible })}
              className={`w-full flex items-center justify-between px-4 py-3 rounded-xl transition ${
                manualEntry.tax_deductible ? "bg-green-500/10 border border-green-500/30" : "bg-[#0f172a] border border-[#334155]"
              }`}
            >
              <div className="flex items-center gap-2">
                <ShieldCheck className={`w-5 h-5 ${manualEntry.tax_deductible ? "text-green-400" : "text-[#475569]"}`} />
                <span className={`text-sm ${manualEntry.tax_deductible ? "text-green-400" : "text-[#94a3b8]"}`}>
                  {L("ניתן לניכוי מס", "Tax Deductible")}
                </span>
              </div>
              <div className={`w-10 h-6 rounded-full relative transition ${manualEntry.tax_deductible ? "bg-green-500" : "bg-[#334155]"}`}>
                <div className={`w-4 h-4 rounded-full bg-white absolute top-1 transition-all ${manualEntry.tax_deductible ? "right-1" : "left-1"}`} />
              </div>
            </button>

            <button
              onClick={handleManualSubmit}
              disabled={!manualEntry.vendor_name || !manualEntry.amount || loading}
              className="w-full py-3.5 bg-cyan-500 text-white rounded-xl text-sm font-bold disabled:opacity-50 flex items-center justify-center gap-2 active:bg-cyan-600 transition"
            >
              {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              {L("שמור קבלה", "Save Receipt")}
            </button>
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════
           EXPORT VIEW
         ═══════════════════════════════════════ */}
      {view === "export" && (
        <div className="space-y-4">
          <button onClick={() => setView("home")} className="flex items-center gap-2 text-[#94a3b8] text-sm">
            <ChevronDown className="w-4 h-4 rotate-90" />
            {L("חזרה", "Back")}
          </button>

          <div className="bg-[#1e293b] rounded-2xl p-5 space-y-5">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-cyan-500/20 rounded-2xl flex items-center justify-center">
                <Download className="w-6 h-6 text-cyan-400" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">{L("ייצוא קבלות", "Export Receipts")}</h3>
                <p className="text-xs text-[#64748b]">{L("חשבונית ירוקה · מס הכנסה", "Green Invoice · Tax Authority")}</p>
              </div>
            </div>

            {summary && (
              <div className="bg-[#0f172a] rounded-xl p-4 space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-[#94a3b8]">{L("קבלות לייצוא", "Receipts to export")}</span>
                  <span className="text-white font-bold">{summary.total_receipts}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-[#94a3b8]">{L("סה״כ", "Total")}</span>
                  <span className="text-white font-bold">₪{summary.total_amount.toLocaleString()}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-green-400">{L("ניתן לניכוי", "Deductible")}</span>
                  <span className="text-green-400 font-bold">₪{summary.tax_deductible_amount.toLocaleString()}</span>
                </div>
              </div>
            )}

            <div className="space-y-3">
              <button
                onClick={() => handleExport("csv")}
                className="w-full py-4 bg-green-600 text-white rounded-xl font-medium flex items-center justify-center gap-2 active:bg-green-700"
              >
                <FileText className="w-5 h-5" />
                {L("הורד CSV לאקסל / חשבונית ירוקה", "Download CSV for Excel / Green Invoice")}
              </button>
              <button
                onClick={() => handleExport("json")}
                className="w-full py-4 bg-[#334155] text-white rounded-xl font-medium flex items-center justify-center gap-2 active:bg-[#475569]"
              >
                <Download className="w-5 h-5" />
                {L("הורד JSON לגיבוי", "Download JSON Backup")}
              </button>
            </div>

            {/* Tax tips */}
            <div className="bg-cyan-500/5 rounded-xl p-4 space-y-2">
              <div className="flex items-center gap-2 text-cyan-400 text-xs font-medium">
                <Shield className="w-3.5 h-3.5" />
                {L("טיפים להגשת מס", "Tax Filing Tips")}
              </div>
              <ul className="space-y-1.5 text-[11px] text-[#94a3b8] leading-relaxed">
                <li>• {L("וודא שכל הקבלות כוללות מספר עוסק מורשה / ח.פ.", "Ensure receipts include business ID")}</li>
                <li>• {L("קבלות מעל ₪5,000 דורשות אישור רו\"ח", "Receipts over ₪5,000 need CPA approval")}</li>
                <li>• {L("שמור מקוריות 7 שנים", "Keep originals for 7 years")}</li>
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════
           FAB — Floating Action Button (mobile)
         ═══════════════════════════════════════ */}
      {view === "home" && (
        <button
          onClick={() => cameraInputRef.current?.click()}
          className="fixed bottom-20 left-1/2 -translate-x-1/2 md:bottom-8 md:left-auto md:right-8 md:translate-x-0 w-14 h-14 bg-cyan-500 text-white rounded-full shadow-lg shadow-cyan-500/30 flex items-center justify-center active:scale-95 transition-transform z-40"
        >
          <Camera className="w-6 h-6" />
        </button>
      )}
    </div>
  );
}
