"use client";
import { useState, useEffect, useCallback, useRef } from "react";
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
  getExpenseCategories,
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
  Filter,
  Edit3,
  Save,
  X,
  Camera,
  RefreshCw,
  FileText,
  AlertCircle,
} from "lucide-react";

// Category labels (Hebrew)
const CATEGORY_LABELS: Record<string, { he: string; en: string }> = {
  office_supplies: { he: "ציוד משרדי", en: "Office Supplies" },
  travel: { he: "נסיעות", en: "Travel" },
  meals: { he: "ארוחות עסקיות", en: "Business Meals" },
  phone_internet: { he: "טלפון ואינטרנט", en: "Phone & Internet" },
  software: { he: "תוכנה ומנויים", en: "Software & Subscriptions" },
  professional_services: { he: "שירותים מקצועיים", en: "Professional Services" },
  insurance: { he: "ביטוח", en: "Insurance" },
  rent: { he: "שכירות", en: "Rent" },
  utilities: { he: "חשמל/מים/גז", en: "Utilities" },
  vehicle: { he: "רכב", en: "Vehicle" },
  education: { he: "השתלמות מקצועית", en: "Education" },
  marketing: { he: "שיווק ופרסום", en: "Marketing" },
  equipment: { he: "ציוד וחומרים", en: "Equipment" },
  medical: { he: "הוצאות רפואיות", en: "Medical" },
  donations: { he: "תרומות", en: "Donations" },
  other: { he: "אחר", en: "Other" },
};

const STATUS_ICONS: Record<string, typeof CheckCircle> = {
  verified: CheckCircle,
  rejected: XCircle,
  pending: Clock,
  exported: Download,
};

const STATUS_COLORS: Record<string, string> = {
  verified: "text-green-400",
  rejected: "text-red-400",
  pending: "text-yellow-400",
  exported: "text-cyan-400",
};

type Tab = "list" | "scan" | "email" | "manual" | "export";

export default function ExpenseReceipts() {
  const { t, locale } = useI18n();
  const isHe = locale === "he";

  const [tab, setTab] = useState<Tab>("list");
  const [summary, setSummary] = useState<ExpenseSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [filterCategory, setFilterCategory] = useState("");
  const [filterDeductible, setFilterDeductible] = useState<boolean | undefined>(undefined);

  // Edit state
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editData, setEditData] = useState<Partial<ExpenseReceipt>>({});

  // Scan state
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<string>("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Email state
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

  // Manual entry state
  const [manualEntry, setManualEntry] = useState({
    vendor_name: "",
    amount: "",
    currency: "ILS",
    receipt_date: "",
    receipt_number: "",
    description: "",
    category: "other",
    tax_deductible: false,
  });

  const loadSummary = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await getExpenseSummary();
      setSummary(data);
    } catch (err) {
      setError(isHe ? "שגיאה בטעינת נתונים" : "Error loading data");
    } finally {
      setLoading(false);
    }
  }, [isHe]);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  // ── Image Scan ──

  const handleFileUpload = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      setScanning(true);
      setScanResult("");

      try {
        const reader = new FileReader();
        reader.onload = async () => {
          const base64 = (reader.result as string).split(",")[1];
          const mediaType = file.type || "image/jpeg";

          try {
            const result = await scanReceipt(base64, mediaType, file.name);
            if (result.is_receipt) {
              setScanResult(
                isHe
                  ? `✓ קבלה זוהתה! ספק: ${(result.data as any)?.vendor_name || "לא ידוע"}, סכום: ₪${(result.data as any)?.amount || 0}`
                  : `✓ Receipt detected! Vendor: ${(result.data as any)?.vendor_name || "Unknown"}, Amount: ₪${(result.data as any)?.amount || 0}`
              );
              await loadSummary();
            } else {
              setScanResult(isHe ? "✗ לא זוהתה קבלה בתמונה" : "✗ No receipt detected in image");
            }
          } catch (err) {
            setScanResult(isHe ? "שגיאה בסריקה" : "Scan error");
          }
          setScanning(false);
        };
        reader.readAsDataURL(file);
      } catch {
        setScanning(false);
        setScanResult(isHe ? "שגיאה בקריאת הקובץ" : "File read error");
      }
    },
    [isHe, loadSummary]
  );

  // ── Email Scan ──

  const handleTestEmail = useCallback(async () => {
    setEmailTesting(true);
    setEmailResult("");
    try {
      const result = await testEmailConnection(emailConfig);
      setEmailResult(
        result.success
          ? isHe
            ? `✓ חיבור הצליח! ${result.message_count} הודעות נמצאו`
            : `✓ Connected! ${result.message_count} messages found`
          : isHe
            ? `✗ חיבור נכשל: ${result.error}`
            : `✗ Connection failed: ${result.error}`
      );
    } catch {
      setEmailResult(isHe ? "שגיאה בבדיקת חיבור" : "Connection test error");
    }
    setEmailTesting(false);
  }, [emailConfig, isHe]);

  const handleScanEmails = useCallback(async () => {
    setEmailScanning(true);
    setEmailResult("");
    try {
      const result = await scanEmails(emailConfig);
      setEmailResult(
        isHe
          ? `✓ נסרקו ${result.emails_scanned} מיילים, נמצאו ${result.receipts_found} קבלות`
          : `✓ Scanned ${result.emails_scanned} emails, found ${result.receipts_found} receipts`
      );
      if (result.receipts_found > 0) await loadSummary();
    } catch {
      setEmailResult(isHe ? "שגיאה בסריקת מיילים" : "Email scan error");
    }
    setEmailScanning(false);
  }, [emailConfig, isHe, loadSummary]);

  // ── Manual Entry ──

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
        receipt_date: "",
        receipt_number: "",
        description: "",
        category: "other",
        tax_deductible: false,
      });
      await loadSummary();
      setTab("list");
    } catch {
      setError(isHe ? "שגיאה בשמירה" : "Save error");
    }
    setLoading(false);
  }, [manualEntry, isHe, loadSummary]);

  // ── Receipt Actions ──

  const handleDelete = useCallback(
    async (id: number) => {
      try {
        await deleteReceipt(id);
        await loadSummary();
      } catch {
        setError(isHe ? "שגיאה במחיקה" : "Delete error");
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
        setError(isHe ? "שגיאה בעדכון" : "Update error");
      }
    },
    [editData, isHe, loadSummary]
  );

  const handleExport = useCallback(
    async (format: "json" | "csv") => {
      try {
        const result = await exportReceipts(format, filterDeductible === true);
        if (format === "csv" && result.data) {
          const blob = new Blob(["\uFEFF" + result.data], { type: "text/csv;charset=utf-8" });
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = `receipts_export_${new Date().toISOString().split("T")[0]}.csv`;
          a.click();
          URL.revokeObjectURL(url);
        } else {
          const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = `receipts_export_${new Date().toISOString().split("T")[0]}.json`;
          a.click();
          URL.revokeObjectURL(url);
        }
      } catch {
        setError(isHe ? "שגיאה בייצוא" : "Export error");
      }
    },
    [filterDeductible, isHe]
  );

  // ── Filter receipts ──

  const filteredReceipts = (summary?.receipts || []).filter((r) => {
    if (filterCategory && r.category !== filterCategory) return false;
    if (filterDeductible !== undefined && r.tax_deductible !== filterDeductible) return false;
    return true;
  });

  // ── Tab button ──
  const TabBtn = ({ id, icon: Icon, label }: { id: Tab; icon: typeof Receipt; label: string }) => (
    <button
      onClick={() => setTab(id)}
      className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition ${
        tab === id ? "bg-cyan-500/20 text-cyan-400" : "text-[#94a3b8] hover:bg-[#1e293b] hover:text-white"
      }`}
    >
      <Icon className="w-4 h-4" />
      {label}
    </button>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <Receipt className="w-6 h-6 text-cyan-400" />
          {isHe ? "בוט קבלות הוצאות" : "Expense Receipt Bot"}
        </h2>
        <button
          onClick={loadSummary}
          className="p-2 rounded-lg hover:bg-[#1e293b] text-[#94a3b8] hover:text-white transition"
        >
          <RefreshCw className={`w-5 h-5 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-[#1e293b] rounded-xl p-4">
            <div className="text-[#94a3b8] text-xs mb-1">{isHe ? "סה״כ קבלות" : "Total Receipts"}</div>
            <div className="text-2xl font-bold text-white">{summary.total_receipts}</div>
          </div>
          <div className="bg-[#1e293b] rounded-xl p-4">
            <div className="text-[#94a3b8] text-xs mb-1">{isHe ? "סה״כ הוצאות" : "Total Expenses"}</div>
            <div className="text-2xl font-bold text-white">
              ₪{summary.total_amount.toLocaleString()}
            </div>
          </div>
          <div className="bg-[#1e293b] rounded-xl p-4">
            <div className="text-[#94a3b8] text-xs mb-1">{isHe ? "ניתן לניכוי" : "Tax Deductible"}</div>
            <div className="text-2xl font-bold text-green-400">
              ₪{summary.tax_deductible_amount.toLocaleString()}
            </div>
          </div>
          <div className="bg-[#1e293b] rounded-xl p-4">
            <div className="text-[#94a3b8] text-xs mb-1">{isHe ? "קטגוריות" : "Categories"}</div>
            <div className="text-2xl font-bold text-cyan-400">
              {Object.keys(summary.by_category).length}
            </div>
          </div>
        </div>
      )}

      {/* Category breakdown */}
      {summary && Object.keys(summary.by_category).length > 0 && (
        <div className="bg-[#1e293b] rounded-xl p-4">
          <h3 className="text-sm font-medium text-[#94a3b8] mb-3">
            {isHe ? "פילוח לפי קטגוריה" : "By Category"}
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {Object.entries(summary.by_category).map(([cat, amount]) => (
              <div key={cat} className="flex justify-between items-center px-3 py-2 bg-[#0f172a] rounded-lg">
                <span className="text-xs text-[#94a3b8]">
                  {CATEGORY_LABELS[cat]?.[locale] || cat}
                </span>
                <span className="text-sm font-medium text-white">₪{amount.toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex flex-wrap gap-2">
        <TabBtn id="list" icon={FileText} label={isHe ? "רשימה" : "List"} />
        <TabBtn id="scan" icon={Camera} label={isHe ? "סרוק תמונה" : "Scan Image"} />
        <TabBtn id="email" icon={Mail} label={isHe ? "סרוק מיילים" : "Scan Emails"} />
        <TabBtn id="manual" icon={Plus} label={isHe ? "הוספה ידנית" : "Add Manual"} />
        <TabBtn id="export" icon={Download} label={isHe ? "ייצוא" : "Export"} />
      </div>

      {error && (
        <div className="flex items-center gap-2 text-red-400 bg-red-400/10 px-4 py-2 rounded-lg text-sm">
          <AlertCircle className="w-4 h-4" />
          {error}
          <button onClick={() => setError("")} className="mr-auto">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* ═══ LIST TAB ═══ */}
      {tab === "list" && (
        <div className="space-y-4">
          {/* Filters */}
          <div className="flex flex-wrap gap-3 items-center">
            <Filter className="w-4 h-4 text-[#94a3b8]" />
            <select
              value={filterCategory}
              onChange={(e) => setFilterCategory(e.target.value)}
              className="bg-[#0f172a] text-white text-sm px-3 py-2 rounded-lg border border-[#334155]"
            >
              <option value="">{isHe ? "כל הקטגוריות" : "All Categories"}</option>
              {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
                <option key={key} value={key}>
                  {label[locale]}
                </option>
              ))}
            </select>
            <select
              value={filterDeductible === undefined ? "" : String(filterDeductible)}
              onChange={(e) =>
                setFilterDeductible(e.target.value === "" ? undefined : e.target.value === "true")
              }
              className="bg-[#0f172a] text-white text-sm px-3 py-2 rounded-lg border border-[#334155]"
            >
              <option value="">{isHe ? "הכל" : "All"}</option>
              <option value="true">{isHe ? "ניתן לניכוי" : "Deductible"}</option>
              <option value="false">{isHe ? "לא לניכוי" : "Non-deductible"}</option>
            </select>
            <span className="text-xs text-[#94a3b8]">
              {filteredReceipts.length} {isHe ? "קבלות" : "receipts"}
            </span>
          </div>

          {/* Receipt List */}
          {filteredReceipts.length === 0 ? (
            <div className="text-center py-12 text-[#94a3b8]">
              <Receipt className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>{isHe ? "אין קבלות להצגה" : "No receipts to show"}</p>
              <p className="text-xs mt-1">
                {isHe ? "סרוק תמונה, מייל, או הוסף ידנית" : "Scan an image, email, or add manually"}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {filteredReceipts.map((r) => {
                const StatusIcon = STATUS_ICONS[r.status] || Clock;
                const isEditing = editingId === r.id;

                return (
                  <div
                    key={r.id}
                    className="bg-[#1e293b] rounded-xl p-4 flex flex-col md:flex-row md:items-center gap-3"
                  >
                    {/* Status icon */}
                    <StatusIcon
                      className={`w-5 h-5 shrink-0 ${STATUS_COLORS[r.status] || "text-gray-400"}`}
                    />

                    {/* Main info */}
                    <div className="flex-1 min-w-0">
                      {isEditing ? (
                        <div className="space-y-2">
                          <input
                            value={editData.vendor_name ?? r.vendor_name}
                            onChange={(e) => setEditData({ ...editData, vendor_name: e.target.value })}
                            className="w-full bg-[#0f172a] text-white text-sm px-3 py-1.5 rounded border border-[#334155]"
                            placeholder={isHe ? "שם ספק" : "Vendor name"}
                          />
                          <div className="flex gap-2">
                            <input
                              type="number"
                              value={editData.amount ?? r.amount}
                              onChange={(e) =>
                                setEditData({ ...editData, amount: parseFloat(e.target.value) })
                              }
                              className="w-32 bg-[#0f172a] text-white text-sm px-3 py-1.5 rounded border border-[#334155]"
                            />
                            <select
                              value={editData.category ?? r.category}
                              onChange={(e) => setEditData({ ...editData, category: e.target.value })}
                              className="bg-[#0f172a] text-white text-sm px-3 py-1.5 rounded border border-[#334155]"
                            >
                              {Object.entries(CATEGORY_LABELS).map(([k, v]) => (
                                <option key={k} value={k}>
                                  {v[locale]}
                                </option>
                              ))}
                            </select>
                            <label className="flex items-center gap-1 text-xs text-[#94a3b8]">
                              <input
                                type="checkbox"
                                checked={editData.tax_deductible ?? r.tax_deductible}
                                onChange={(e) =>
                                  setEditData({ ...editData, tax_deductible: e.target.checked })
                                }
                                className="accent-cyan-400"
                              />
                              {isHe ? "לניכוי" : "Deductible"}
                            </label>
                          </div>
                        </div>
                      ) : (
                        <>
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-white truncate">{r.vendor_name || (isHe ? "ספק לא ידוע" : "Unknown vendor")}</span>
                            {r.tax_deductible && (
                              <span className="text-[10px] bg-green-500/20 text-green-400 px-1.5 py-0.5 rounded">
                                {isHe ? "לניכוי" : "Deductible"}
                              </span>
                            )}
                            <span className="text-[10px] bg-[#0f172a] text-[#94a3b8] px-1.5 py-0.5 rounded">
                              {CATEGORY_LABELS[r.category]?.[locale] || r.category}
                            </span>
                            {r.source_type !== "manual" && (
                              <span className="text-[10px] bg-cyan-500/10 text-cyan-400 px-1.5 py-0.5 rounded">
                                {r.source_type === "email" ? "📧" : r.source_type === "screenshot" ? "📸" : "📤"}
                              </span>
                            )}
                          </div>
                          <div className="text-xs text-[#94a3b8] mt-0.5">
                            {r.description && <span>{r.description} · </span>}
                            {r.receipt_date && <span>{r.receipt_date} · </span>}
                            {r.receipt_number && <span>#{r.receipt_number}</span>}
                          </div>
                        </>
                      )}
                    </div>

                    {/* Amount */}
                    <div className="text-lg font-bold text-white shrink-0">
                      {r.currency === "ILS" ? "₪" : r.currency === "USD" ? "$" : r.currency}
                      {r.amount.toLocaleString()}
                    </div>

                    {/* Confidence */}
                    {r.confidence_score > 0 && r.confidence_score < 1 && (
                      <div className="text-[10px] text-[#94a3b8]">{Math.round(r.confidence_score * 100)}%</div>
                    )}

                    {/* Actions */}
                    <div className="flex gap-1 shrink-0">
                      {isEditing ? (
                        <>
                          <button
                            onClick={() => handleSaveEdit(r.id)}
                            className="p-1.5 rounded hover:bg-green-500/20 text-green-400"
                          >
                            <Save className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => {
                              setEditingId(null);
                              setEditData({});
                            }}
                            className="p-1.5 rounded hover:bg-[#334155] text-[#94a3b8]"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            onClick={() => {
                              setEditingId(r.id);
                              setEditData({});
                            }}
                            className="p-1.5 rounded hover:bg-[#334155] text-[#94a3b8] hover:text-white"
                          >
                            <Edit3 className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDelete(r.id)}
                            className="p-1.5 rounded hover:bg-red-500/20 text-[#94a3b8] hover:text-red-400"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ═══ SCAN TAB ═══ */}
      {tab === "scan" && (
        <div className="bg-[#1e293b] rounded-xl p-6 space-y-4">
          <h3 className="text-lg font-medium text-white flex items-center gap-2">
            <Camera className="w-5 h-5 text-cyan-400" />
            {isHe ? "סריקת צילום מסך / תמונת קבלה" : "Scan Screenshot / Receipt Image"}
          </h3>
          <p className="text-sm text-[#94a3b8]">
            {isHe
              ? "העלה צילום מסך או תמונה של קבלה. ה-AI יזהה אוטומטית את פרטי הקבלה."
              : "Upload a screenshot or photo of a receipt. AI will automatically identify receipt details."}
          </p>

          <div
            className="border-2 border-dashed border-[#334155] rounded-xl p-8 text-center cursor-pointer hover:border-cyan-400/50 transition"
            onClick={() => fileInputRef.current?.click()}
          >
            <Upload className="w-10 h-10 mx-auto mb-3 text-[#94a3b8]" />
            <p className="text-[#94a3b8]">
              {isHe ? "לחץ להעלאת תמונה או גרור לכאן" : "Click to upload or drag and drop"}
            </p>
            <p className="text-xs text-[#475569] mt-1">JPG, PNG, WebP</p>
          </div>

          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={handleFileUpload}
          />

          {scanning && (
            <div className="flex items-center gap-2 text-cyan-400">
              <RefreshCw className="w-4 h-4 animate-spin" />
              {isHe ? "סורק קבלה עם AI..." : "Scanning receipt with AI..."}
            </div>
          )}

          {scanResult && (
            <div
              className={`px-4 py-3 rounded-lg text-sm ${
                scanResult.startsWith("✓")
                  ? "bg-green-500/10 text-green-400"
                  : "bg-yellow-500/10 text-yellow-400"
              }`}
            >
              {scanResult}
            </div>
          )}
        </div>
      )}

      {/* ═══ EMAIL TAB ═══ */}
      {tab === "email" && (
        <div className="bg-[#1e293b] rounded-xl p-6 space-y-4">
          <h3 className="text-lg font-medium text-white flex items-center gap-2">
            <Mail className="w-5 h-5 text-cyan-400" />
            {isHe ? "סריקת מיילים לקבלות" : "Scan Emails for Receipts"}
          </h3>
          <p className="text-sm text-[#94a3b8]">
            {isHe
              ? "חבר את תיבת המייל שלך כדי לזהות אוטומטית קבלות וחשבוניות דיגיטליות."
              : "Connect your email inbox to automatically identify digital receipts and invoices."}
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-[#94a3b8] block mb-1">
                {isHe ? "כתובת מייל" : "Email Address"}
              </label>
              <input
                type="email"
                value={emailConfig.email_address}
                onChange={(e) => setEmailConfig({ ...emailConfig, email_address: e.target.value })}
                className="w-full bg-[#0f172a] text-white text-sm px-3 py-2 rounded-lg border border-[#334155]"
                placeholder="user@gmail.com"
              />
            </div>
            <div>
              <label className="text-xs text-[#94a3b8] block mb-1">
                {isHe ? "סיסמת אפליקציה" : "App Password"}
              </label>
              <input
                type="password"
                value={emailConfig.password}
                onChange={(e) => setEmailConfig({ ...emailConfig, password: e.target.value })}
                className="w-full bg-[#0f172a] text-white text-sm px-3 py-2 rounded-lg border border-[#334155]"
                placeholder={isHe ? "סיסמת אפליקציה של גוגל" : "Google App Password"}
              />
            </div>
            <div>
              <label className="text-xs text-[#94a3b8] block mb-1">
                {isHe ? "שרת IMAP" : "IMAP Server"}
              </label>
              <input
                value={emailConfig.imap_server}
                onChange={(e) => setEmailConfig({ ...emailConfig, imap_server: e.target.value })}
                className="w-full bg-[#0f172a] text-white text-sm px-3 py-2 rounded-lg border border-[#334155]"
              />
            </div>
            <div>
              <label className="text-xs text-[#94a3b8] block mb-1">
                {isHe ? "ימים אחורה" : "Days Back"}
              </label>
              <input
                type="number"
                value={emailConfig.days_back}
                onChange={(e) => setEmailConfig({ ...emailConfig, days_back: parseInt(e.target.value) || 30 })}
                className="w-full bg-[#0f172a] text-white text-sm px-3 py-2 rounded-lg border border-[#334155]"
                min={1}
                max={365}
              />
            </div>
          </div>

          <div className="flex gap-3">
            <button
              onClick={handleTestEmail}
              disabled={emailTesting || !emailConfig.email_address || !emailConfig.password}
              className="px-4 py-2 bg-[#334155] text-white rounded-lg text-sm hover:bg-[#475569] disabled:opacity-50 flex items-center gap-2"
            >
              {emailTesting ? <RefreshCw className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
              {isHe ? "בדוק חיבור" : "Test Connection"}
            </button>
            <button
              onClick={handleScanEmails}
              disabled={emailScanning || !emailConfig.email_address || !emailConfig.password}
              className="px-4 py-2 bg-cyan-500 text-white rounded-lg text-sm hover:bg-cyan-600 disabled:opacity-50 flex items-center gap-2"
            >
              {emailScanning ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Mail className="w-4 h-4" />}
              {isHe ? "סרוק מיילים" : "Scan Emails"}
            </button>
          </div>

          <p className="text-[10px] text-[#475569]">
            {isHe
              ? "* לגימייל: יש להשתמש ב-App Password (הגדרות → אבטחה → סיסמאות אפליקציה). הסיסמה לא נשמרת בשרת."
              : "* For Gmail: Use App Password (Settings → Security → App Passwords). Password is not stored on server."}
          </p>

          {emailResult && (
            <div
              className={`px-4 py-3 rounded-lg text-sm ${
                emailResult.startsWith("✓")
                  ? "bg-green-500/10 text-green-400"
                  : "bg-red-500/10 text-red-400"
              }`}
            >
              {emailResult}
            </div>
          )}
        </div>
      )}

      {/* ═══ MANUAL TAB ═══ */}
      {tab === "manual" && (
        <div className="bg-[#1e293b] rounded-xl p-6 space-y-4">
          <h3 className="text-lg font-medium text-white flex items-center gap-2">
            <Plus className="w-5 h-5 text-cyan-400" />
            {isHe ? "הוספת קבלה ידנית" : "Add Receipt Manually"}
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-[#94a3b8] block mb-1">
                {isHe ? "שם ספק *" : "Vendor Name *"}
              </label>
              <input
                value={manualEntry.vendor_name}
                onChange={(e) => setManualEntry({ ...manualEntry, vendor_name: e.target.value })}
                className="w-full bg-[#0f172a] text-white text-sm px-3 py-2 rounded-lg border border-[#334155]"
                placeholder={isHe ? "שם העסק" : "Business name"}
              />
            </div>
            <div>
              <label className="text-xs text-[#94a3b8] block mb-1">
                {isHe ? "סכום *" : "Amount *"}
              </label>
              <div className="flex gap-2">
                <input
                  type="number"
                  step="0.01"
                  value={manualEntry.amount}
                  onChange={(e) => setManualEntry({ ...manualEntry, amount: e.target.value })}
                  className="flex-1 bg-[#0f172a] text-white text-sm px-3 py-2 rounded-lg border border-[#334155]"
                  placeholder="0.00"
                />
                <select
                  value={manualEntry.currency}
                  onChange={(e) => setManualEntry({ ...manualEntry, currency: e.target.value })}
                  className="bg-[#0f172a] text-white text-sm px-3 py-2 rounded-lg border border-[#334155]"
                >
                  <option value="ILS">₪ ILS</option>
                  <option value="USD">$ USD</option>
                  <option value="EUR">€ EUR</option>
                </select>
              </div>
            </div>
            <div>
              <label className="text-xs text-[#94a3b8] block mb-1">
                {isHe ? "תאריך" : "Date"}
              </label>
              <input
                type="date"
                value={manualEntry.receipt_date}
                onChange={(e) => setManualEntry({ ...manualEntry, receipt_date: e.target.value })}
                className="w-full bg-[#0f172a] text-white text-sm px-3 py-2 rounded-lg border border-[#334155]"
              />
            </div>
            <div>
              <label className="text-xs text-[#94a3b8] block mb-1">
                {isHe ? "מספר קבלה" : "Receipt Number"}
              </label>
              <input
                value={manualEntry.receipt_number}
                onChange={(e) => setManualEntry({ ...manualEntry, receipt_number: e.target.value })}
                className="w-full bg-[#0f172a] text-white text-sm px-3 py-2 rounded-lg border border-[#334155]"
              />
            </div>
            <div>
              <label className="text-xs text-[#94a3b8] block mb-1">
                {isHe ? "קטגוריה" : "Category"}
              </label>
              <select
                value={manualEntry.category}
                onChange={(e) => setManualEntry({ ...manualEntry, category: e.target.value })}
                className="w-full bg-[#0f172a] text-white text-sm px-3 py-2 rounded-lg border border-[#334155]"
              >
                {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
                  <option key={key} value={key}>
                    {label[locale]}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-end">
              <label className="flex items-center gap-2 text-sm text-[#94a3b8] cursor-pointer">
                <input
                  type="checkbox"
                  checked={manualEntry.tax_deductible}
                  onChange={(e) =>
                    setManualEntry({ ...manualEntry, tax_deductible: e.target.checked })
                  }
                  className="accent-cyan-400 w-4 h-4"
                />
                {isHe ? "ניתן לניכוי מס" : "Tax Deductible"}
              </label>
            </div>
          </div>

          <div>
            <label className="text-xs text-[#94a3b8] block mb-1">
              {isHe ? "תיאור" : "Description"}
            </label>
            <input
              value={manualEntry.description}
              onChange={(e) => setManualEntry({ ...manualEntry, description: e.target.value })}
              className="w-full bg-[#0f172a] text-white text-sm px-3 py-2 rounded-lg border border-[#334155]"
              placeholder={isHe ? "תיאור ההוצאה" : "Expense description"}
            />
          </div>

          <button
            onClick={handleManualSubmit}
            disabled={!manualEntry.vendor_name || !manualEntry.amount || loading}
            className="px-6 py-2.5 bg-cyan-500 text-white rounded-lg text-sm font-medium hover:bg-cyan-600 disabled:opacity-50 flex items-center gap-2"
          >
            <Save className="w-4 h-4" />
            {isHe ? "שמור קבלה" : "Save Receipt"}
          </button>
        </div>
      )}

      {/* ═══ EXPORT TAB ═══ */}
      {tab === "export" && (
        <div className="bg-[#1e293b] rounded-xl p-6 space-y-4">
          <h3 className="text-lg font-medium text-white flex items-center gap-2">
            <Download className="w-5 h-5 text-cyan-400" />
            {isHe ? "ייצוא לחשבונית ירוקה / מס הכנסה" : "Export for Green Invoice / Tax Authority"}
          </h3>
          <p className="text-sm text-[#94a3b8]">
            {isHe
              ? "ייצא את כל הקבלות בפורמט מתאים להגשה למס הכנסה או להעלאה לחשבונית ירוקה."
              : "Export all receipts in a format suitable for tax filing or Green Invoice upload."}
          </p>

          <div className="flex items-center gap-3 mb-4">
            <label className="flex items-center gap-2 text-sm text-[#94a3b8] cursor-pointer">
              <input
                type="checkbox"
                checked={filterDeductible === true}
                onChange={(e) => setFilterDeductible(e.target.checked ? true : undefined)}
                className="accent-cyan-400 w-4 h-4"
              />
              {isHe ? "רק ניתנות לניכוי" : "Deductible only"}
            </label>
          </div>

          <div className="flex gap-3">
            <button
              onClick={() => handleExport("csv")}
              className="px-6 py-3 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 flex items-center gap-2"
            >
              <Download className="w-4 h-4" />
              {isHe ? "ייצוא CSV (אקסל)" : "Export CSV (Excel)"}
            </button>
            <button
              onClick={() => handleExport("json")}
              className="px-6 py-3 bg-[#334155] text-white rounded-lg text-sm font-medium hover:bg-[#475569] flex items-center gap-2"
            >
              <Download className="w-4 h-4" />
              {isHe ? "ייצוא JSON" : "Export JSON"}
            </button>
          </div>

          <div className="bg-[#0f172a] rounded-lg p-4 text-sm text-[#94a3b8]">
            <p className="font-medium text-white mb-2">
              {isHe ? "טיפים להגשת מס" : "Tax Filing Tips"}
            </p>
            <ul className="space-y-1 list-disc list-inside text-xs">
              {isHe ? (
                <>
                  <li>וודא שכל הקבלות כוללות מספר עוסק מורשה / ח.פ.</li>
                  <li>קבלות מעל ₪5,000 דורשות אישור רואה חשבון</li>
                  <li>שמור את הקבלות המקוריות (דיגיטליות או פיזיות) ל-7 שנים</li>
                  <li>הקובץ תומך בייבוא לחשבונית ירוקה ולתוכנות הנה"ח נפוצות</li>
                </>
              ) : (
                <>
                  <li>Ensure all receipts include a business registration number</li>
                  <li>Receipts over ₪5,000 require accountant approval</li>
                  <li>Keep original receipts (digital or physical) for 7 years</li>
                  <li>The file supports import to Green Invoice and common accounting software</li>
                </>
              )}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
