"use client";
import { useState } from "react";
import { useI18n } from "@/i18n/context";
import { getCommodities, getCommodityImpact, getSupplyChain, getSupplyChainTips } from "@/lib/api";
import type { CommodityPrice, CommodityImpact, SupplyChain, SupplyChainStage, SupplyChainTip } from "@/lib/types";
import {
  ChevronRight,
  ChevronDown,
  ChevronLeft,
  Loader2,
  Link2,
  MapPin,
  Building2,
  AlertTriangle,
  Pickaxe,
  Zap,
  Wheat,
  Cpu,
  Factory,
  Shield,
  FlaskConical,
  CloudCog,
  Lightbulb,
  RefreshCw,
} from "lucide-react";

// Icons per category
const categoryIcons: Record<string, React.ReactNode> = {
  metals: <Pickaxe className="w-4 h-4" />,
  energy: <Zap className="w-4 h-4" />,
  agriculture: <Wheat className="w-4 h-4" />,
  industrial: <Factory className="w-4 h-4" />,
};

const chainIcons: Record<string, React.ReactNode> = {
  semiconductors: <Cpu className="w-4 h-4" />,
  ev_batteries: <Zap className="w-4 h-4" />,
  energy: <Zap className="w-4 h-4" />,
  food: <Wheat className="w-4 h-4" />,
  cybersecurity: <Shield className="w-4 h-4" />,
  ai_cloud: <CloudCog className="w-4 h-4" />,
  pharma: <FlaskConical className="w-4 h-4" />,
};

const categoryColors: Record<string, string> = {
  metals: "text-amber-400 bg-amber-500/15 border-amber-500/30",
  energy: "text-orange-400 bg-orange-500/15 border-orange-500/30",
  agriculture: "text-green-400 bg-green-500/15 border-green-500/30",
  industrial: "text-blue-400 bg-blue-500/15 border-blue-500/30",
};

type View = "commodities" | "impacts" | "chain";

interface Props {
  onStockClick?: (ticker: string) => void;
}

export default function SupplyChainExplorer({ onStockClick }: Props) {
  const { locale } = useI18n();
  const [view, setView] = useState<View>("commodities");
  const [loading, setLoading] = useState(false);

  // Data
  const [commodities, setCommodities] = useState<CommodityPrice[] | null>(null);
  const [selectedCommodity, setSelectedCommodity] = useState<CommodityPrice | null>(null);
  const [impacts, setImpacts] = useState<CommodityImpact[]>([]);
  const [selectedChain, setSelectedChain] = useState<string | null>(null);
  const [chainData, setChainData] = useState<SupplyChain | null>(null);
  const [expandedStage, setExpandedStage] = useState<string | null>(null);

  // Tips
  const [tips, setTips] = useState<SupplyChainTip[]>([]);
  const [tipIdx, setTipIdx] = useState(0);
  const [tipsLoading, setTipsLoading] = useState(false);

  const loadTips = async (params?: { commodity?: string; chain?: string; category?: string }) => {
    setTipsLoading(true);
    try {
      const data = await getSupplyChainTips({ ...params, limit: 5 });
      setTips(data.tips);
      setTipIdx(0);
    } catch (e) {
      console.error(e);
    } finally {
      setTipsLoading(false);
    }
  };

  const nextTip = () => {
    if (tips.length > 0) setTipIdx((prev) => (prev + 1) % tips.length);
  };

  // 1. Load commodities list
  const loadCommodities = async () => {
    if (commodities) return;
    setLoading(true);
    try {
      const data = await getCommodities();
      setCommodities(data.commodities);
      if (tips.length === 0) loadTips();
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  // 2. Click commodity → show which chains it affects
  const selectCommodity = async (commodity: CommodityPrice) => {
    setSelectedCommodity(commodity);
    setLoading(true);
    try {
      const data = await getCommodityImpact(commodity.key);
      setImpacts(data.impacts);
      setView("impacts");
      loadTips({ commodity: commodity.key, category: commodity.category });
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  // 3. Click chain → show full chain with stages
  const selectChain = async (chainKey: string) => {
    setSelectedChain(chainKey);
    setLoading(true);
    try {
      const data = await getSupplyChain(chainKey) as SupplyChain;
      setChainData(data);
      setView("chain");
      loadTips({ chain: chainKey });
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const goBack = () => {
    if (view === "chain") {
      setView("impacts");
      setChainData(null);
      setExpandedStage(null);
    } else if (view === "impacts") {
      setView("commodities");
      setSelectedCommodity(null);
      setImpacts([]);
    }
  };

  // ── RENDER: Commodities list ──
  const renderCommodities = () => {
    if (!commodities) {
      loadCommodities();
      return (
        <div className="flex items-center justify-center py-4 text-[#64748b] text-sm">
          <Loader2 className="w-4 h-4 animate-spin me-2" />
          {locale === "he" ? "טוען סחורות..." : "Loading commodities..."}
        </div>
      );
    }

    // Group by category
    const groups: Record<string, CommodityPrice[]> = {};
    for (const c of commodities) {
      if (!groups[c.category]) groups[c.category] = [];
      groups[c.category].push(c);
    }

    const categoryNames: Record<string, { he: string; en: string }> = {
      metals: { he: "מתכות", en: "Metals" },
      energy: { he: "אנרגיה", en: "Energy" },
      agriculture: { he: "חקלאות", en: "Agriculture" },
      industrial: { he: "תעשייתי", en: "Industrial" },
    };

    return (
      <div className="space-y-3">
        <p className="text-[10px] text-[#64748b]">
          {locale === "he"
            ? "לחץ על סחורה לראות אילו שרשראות אספקה היא משפיעה"
            : "Click a commodity to see which supply chains it affects"}
        </p>
        {Object.entries(groups).map(([cat, items]) => (
          <div key={cat}>
            <div className="flex items-center gap-1.5 mb-1.5 text-xs text-[#94a3b8] font-medium">
              {categoryIcons[cat]}
              {locale === "he" ? categoryNames[cat]?.he : categoryNames[cat]?.en}
            </div>
            <div className="space-y-1">
              {items.map((c) => (
                <button
                  key={c.key}
                  onClick={() => selectCommodity(c)}
                  className="w-full flex items-center justify-between p-2 rounded-lg bg-[#0f172a] hover:bg-[#1e293b] border border-[#1e293b] hover:border-[#334155] transition text-start group"
                >
                  <div className="flex items-center gap-2">
                    <span className={`w-6 h-6 rounded-md flex items-center justify-center text-xs border ${categoryColors[c.category]}`}>
                      {categoryIcons[c.category]}
                    </span>
                    <div>
                      <span className="text-sm text-white font-medium">
                        {locale === "he" ? c.name_he : c.name}
                      </span>
                      {c.price !== null && (
                        <span className="text-xs text-[#64748b] ms-2">
                          ${c.price.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {c.change_pct !== null && (
                      <span className={`text-xs tabular-nums font-medium ${c.change_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
                        {c.change_pct >= 0 ? "+" : ""}{c.change_pct.toFixed(2)}%
                      </span>
                    )}
                    <ChevronRight className="w-3.5 h-3.5 text-[#475569] group-hover:text-white transition" />
                  </div>
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    );
  };

  // ── RENDER: Impacts (which chains does this commodity affect?) ──
  const renderImpacts = () => {
    if (!selectedCommodity) return null;

    return (
      <div className="space-y-3">
        {/* Commodity header */}
        <div className="flex items-center gap-2 p-2 rounded-lg bg-[#0f172a] border border-[#1e293b]">
          <span className={`w-8 h-8 rounded-lg flex items-center justify-center border ${categoryColors[selectedCommodity.category]}`}>
            {categoryIcons[selectedCommodity.category]}
          </span>
          <div>
            <div className="text-white font-semibold text-sm">
              {locale === "he" ? selectedCommodity.name_he : selectedCommodity.name}
            </div>
            {selectedCommodity.price !== null && (
              <div className="text-xs text-[#94a3b8]">
                ${selectedCommodity.price.toLocaleString(undefined, { maximumFractionDigits: 2 })} {selectedCommodity.unit}
                {selectedCommodity.change_pct !== null && (
                  <span className={`ms-2 ${selectedCommodity.change_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
                    {selectedCommodity.change_pct >= 0 ? "+" : ""}{selectedCommodity.change_pct.toFixed(2)}%
                  </span>
                )}
              </div>
            )}
          </div>
        </div>

        <p className="text-xs text-[#94a3b8]">
          {locale === "he"
            ? `${selectedCommodity.name_he} משפיע/ה על ${impacts.length} שרשראות אספקה. לחץ לפירוט:`
            : `${selectedCommodity.name} affects ${impacts.length} supply chains. Click to explore:`}
        </p>

        {impacts.length === 0 && (
          <p className="text-sm text-[#64748b] text-center py-4">
            {locale === "he" ? "לא נמצאו שרשראות מושפעות" : "No affected chains found"}
          </p>
        )}

        {/* Group by chain */}
        {(() => {
          const chains: Record<string, CommodityImpact[]> = {};
          for (const imp of impacts) {
            if (!chains[imp.chain]) chains[imp.chain] = [];
            chains[imp.chain].push(imp);
          }

          return Object.entries(chains).map(([chainKey, stages]) => (
            <button
              key={chainKey}
              onClick={() => selectChain(chainKey)}
              className="w-full p-3 rounded-lg bg-[#0f172a] border border-[#1e293b] hover:border-cyan-500/30 transition text-start group"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="w-6 h-6 rounded-md bg-cyan-500/15 text-cyan-400 flex items-center justify-center">
                    {chainIcons[chainKey] || <Link2 className="w-3.5 h-3.5" />}
                  </span>
                  <span className="text-sm font-semibold text-white group-hover:text-cyan-400 transition">
                    {locale === "he" ? stages[0].chain_name_he : stages[0].chain_name}
                  </span>
                </div>
                <ChevronRight className="w-4 h-4 text-[#475569] group-hover:text-cyan-400 transition" />
              </div>

              <div className="space-y-1">
                {stages.map((s, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs">
                    <span className="text-[#64748b]">{locale === "he" ? s.stage_name_he : s.stage_name}</span>
                    {s.israeli_companies.length > 0 && (
                      <span className="px-1 py-0.5 rounded bg-blue-500/15 text-blue-400 text-[9px] font-medium">
                        IL: {s.israeli_companies.join(", ")}
                      </span>
                    )}
                  </div>
                ))}
              </div>

              {/* Affected companies preview */}
              <div className="flex flex-wrap gap-1 mt-2">
                {stages.flatMap(s => s.companies).slice(0, 6).map((ticker, i) => (
                  <span key={i} className="px-1.5 py-0.5 rounded bg-[#1e293b] text-[10px] font-mono text-cyan-400">
                    {ticker}
                  </span>
                ))}
                {stages.flatMap(s => s.companies).length > 6 && (
                  <span className="text-[10px] text-[#64748b]">
                    +{stages.flatMap(s => s.companies).length - 6}
                  </span>
                )}
              </div>
            </button>
          ));
        })()}
      </div>
    );
  };

  // ── RENDER: Full chain detail (all stages) ──
  const renderChain = () => {
    if (!chainData) return null;

    return (
      <div className="space-y-3">
        {/* Chain header */}
        <div className="p-2 rounded-lg bg-[#0f172a] border border-cyan-500/20">
          <div className="flex items-center gap-2">
            <span className="w-8 h-8 rounded-lg bg-cyan-500/15 text-cyan-400 flex items-center justify-center">
              {chainIcons[selectedChain || ""] || <Link2 className="w-4 h-4" />}
            </span>
            <div>
              <div className="text-white font-semibold text-sm">
                {locale === "he" ? chainData.name_he : chainData.name}
              </div>
              <div className="text-[10px] text-[#94a3b8]">
                {chainData.stages.length} {locale === "he" ? "שלבים" : "stages"}
              </div>
            </div>
          </div>
        </div>

        {/* Stages — vertical timeline */}
        <div className="relative">
          {/* Vertical connector line */}
          <div className="absolute start-4 top-4 bottom-4 w-px bg-gradient-to-b from-cyan-500/50 via-[#334155] to-[#1e293b]" />

          <div className="space-y-2">
            {chainData.stages.map((stage, i) => {
              const isExpanded = expandedStage === stage.stage;
              const hasIsrael = (stage.israeli_companies && stage.israeli_companies.length > 0) || stage.israeli_connection;
              // Highlight the stage that uses the selected commodity
              const usesSelectedCommodity = selectedCommodity && stage.commodities?.includes(selectedCommodity.key);

              return (
                <button
                  key={stage.stage}
                  onClick={() => setExpandedStage(isExpanded ? null : stage.stage)}
                  className={`w-full text-start relative ps-10 pe-3 py-2 rounded-lg border transition ${
                    usesSelectedCommodity
                      ? "bg-amber-500/5 border-amber-500/20 hover:border-amber-500/40"
                      : "bg-[#0f172a] border-[#1e293b] hover:border-[#334155]"
                  }`}
                >
                  {/* Stage number circle */}
                  <div className={`absolute start-1.5 top-2.5 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                    usesSelectedCommodity
                      ? "bg-amber-500 text-black"
                      : hasIsrael
                      ? "bg-blue-500 text-white"
                      : "bg-[#334155] text-white"
                  }`}>
                    {i + 1}
                  </div>

                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-sm font-medium text-white">
                        {locale === "he" ? stage.name_he : stage.name}
                      </span>
                      {hasIsrael && (
                        <span className="ms-2 px-1 py-0.5 rounded bg-blue-500/15 text-blue-400 text-[9px] font-medium">
                          IL
                        </span>
                      )}
                      {usesSelectedCommodity && (
                        <span className="ms-1 px-1 py-0.5 rounded bg-amber-500/15 text-amber-400 text-[9px] font-medium">
                          {locale === "he" ? selectedCommodity.name_he : selectedCommodity.name}
                        </span>
                      )}
                    </div>
                    {isExpanded ? (
                      <ChevronDown className="w-3.5 h-3.5 text-[#64748b]" />
                    ) : (
                      <ChevronRight className="w-3.5 h-3.5 text-[#64748b]" />
                    )}
                  </div>

                  {/* Regions preview (always shown) */}
                  {stage.regions && (
                    <div className="flex items-center gap-1 mt-1 text-[10px] text-[#64748b]">
                      <MapPin className="w-2.5 h-2.5" />
                      {stage.regions.join(", ")}
                    </div>
                  )}

                  {/* Expanded detail */}
                  {isExpanded && (
                    <div className="mt-2 space-y-2 border-t border-[#1e293b] pt-2" onClick={(e) => e.stopPropagation()}>
                      {/* Commodities */}
                      {stage.commodities && stage.commodities.length > 0 && (
                        <div>
                          <span className="text-[10px] text-[#64748b] block mb-1">
                            {locale === "he" ? "חומרי גלם:" : "Raw materials:"}
                          </span>
                          <div className="flex flex-wrap gap-1">
                            {stage.commodities.map((c) => (
                              <span key={c} className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                                c === selectedCommodity?.key
                                  ? "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                                  : "bg-[#1e293b] text-[#94a3b8]"
                              }`}>
                                {c}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Countries */}
                      {stage.countries && stage.countries.length > 0 && (
                        <div>
                          <span className="text-[10px] text-[#64748b] block mb-1">
                            {locale === "he" ? "מדינות:" : "Countries:"}
                          </span>
                          <span className="text-xs text-[#94a3b8]">{stage.countries.join(", ")}</span>
                        </div>
                      )}

                      {/* Companies */}
                      {stage.companies && stage.companies.length > 0 && (
                        <div>
                          <span className="text-[10px] text-[#64748b] block mb-1">
                            {locale === "he" ? "חברות:" : "Companies:"}
                          </span>
                          <div className="flex flex-wrap gap-1">
                            {stage.companies.map((ticker) => (
                              <button
                                key={ticker}
                                onClick={() => onStockClick?.(ticker)}
                                className="px-1.5 py-0.5 rounded bg-[#1e293b] hover:bg-cyan-500/15 text-cyan-400 text-[10px] font-mono font-medium transition cursor-pointer"
                              >
                                {ticker}
                              </button>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Israeli companies (highlighted) */}
                      {stage.israeli_companies && stage.israeli_companies.length > 0 && (
                        <div className="p-2 rounded bg-blue-500/10 border border-blue-500/20">
                          <span className="text-[10px] text-blue-400 font-medium block mb-1">
                            {locale === "he" ? "חברות ישראליות:" : "Israeli companies:"}
                          </span>
                          <div className="flex flex-wrap gap-1">
                            {stage.israeli_companies.map((ticker) => (
                              <button
                                key={ticker}
                                onClick={() => onStockClick?.(ticker)}
                                className="px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-300 text-[10px] font-mono font-medium hover:bg-blue-500/30 transition cursor-pointer"
                              >
                                {ticker}
                              </button>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Israeli connection note */}
                      {stage.israeli_connection && (
                        <div className="p-2 rounded bg-blue-500/10 border border-blue-500/20">
                          <span className="text-[10px] text-blue-400 font-medium block mb-0.5">
                            {locale === "he" ? "הקשר לישראל:" : "Israel connection:"}
                          </span>
                          <span className="text-xs text-blue-200">{stage.israeli_connection}</span>
                        </div>
                      )}

                      {/* Notes */}
                      {stage.notes && (
                        <p className="text-[10px] text-[#94a3b8] italic">{stage.notes}</p>
                      )}
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Risk factors */}
        {chainData.risk_factors && chainData.risk_factors.length > 0 && (
          <div className="p-3 rounded-lg bg-red-500/5 border border-red-500/20">
            <div className="flex items-center gap-1.5 mb-2 text-xs text-red-400 font-semibold">
              <AlertTriangle className="w-3.5 h-3.5" />
              {locale === "he" ? "גורמי סיכון" : "Risk Factors"}
            </div>
            <div className="space-y-1.5">
              {chainData.risk_factors.map((risk, i) => (
                <div key={i} className="flex items-start gap-2 text-xs">
                  <span className={`px-1 py-0.5 rounded text-[9px] font-bold shrink-0 ${
                    risk.impact === "high"
                      ? "bg-red-500/20 text-red-400"
                      : "bg-yellow-500/20 text-yellow-400"
                  }`}>
                    {risk.impact === "high" ? (locale === "he" ? "גבוה" : "HIGH") : (locale === "he" ? "בינוני" : "MED")}
                  </span>
                  <span className="text-[#e2e8f0]">{risk.factor}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <section className="bg-[#111827] rounded-xl border border-[#334155] p-4">
      {/* Header with breadcrumb navigation */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-1.5">
          {view !== "commodities" && (
            <button
              onClick={goBack}
              className="p-1 rounded hover:bg-[#1e293b] transition"
            >
              <ChevronLeft className="w-4 h-4 text-[#94a3b8]" />
            </button>
          )}
          <Link2 className="w-4 h-4 text-teal-400" />
          <h3 className="text-sm font-semibold text-white">
            {view === "commodities" && (locale === "he" ? "שרשרת אספקה" : "Supply Chain")}
            {view === "impacts" && selectedCommodity && (
              <span>
                {locale === "he" ? selectedCommodity.name_he : selectedCommodity.name}
                <span className="text-[#64748b] font-normal"> → </span>
                {locale === "he" ? "שרשראות" : "Chains"}
              </span>
            )}
            {view === "chain" && chainData && (
              <span className="line-clamp-1">
                {locale === "he" ? chainData.name_he : chainData.name}
              </span>
            )}
          </h3>
        </div>

        {/* Breadcrumb dots */}
        <div className="flex gap-1">
          {["commodities", "impacts", "chain"].map((v) => (
            <div
              key={v}
              className={`w-1.5 h-1.5 rounded-full ${view === v ? "bg-teal-400" : "bg-[#334155]"}`}
            />
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-6 text-[#64748b] text-sm">
          <Loader2 className="w-4 h-4 animate-spin me-2" />
          {locale === "he" ? "טוען..." : "Loading..."}
        </div>
      ) : (
        <>
          {view === "commodities" && renderCommodities()}
          {view === "impacts" && renderImpacts()}
          {view === "chain" && renderChain()}
        </>
      )}

      {/* "Did you know?" tip card */}
      {tips.length > 0 && !loading && (
        <div className="mt-3 p-3 rounded-lg bg-gradient-to-r from-amber-500/10 to-orange-500/10 border border-amber-500/20">
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-400">
              <Lightbulb className="w-3.5 h-3.5" />
              {locale === "he" ? "הידעת?" : "Did you know?"}
            </div>
            <button
              onClick={nextTip}
              className="p-1 rounded hover:bg-amber-500/15 transition text-amber-400/60 hover:text-amber-400"
              title={locale === "he" ? "טיפ הבא" : "Next tip"}
            >
              <RefreshCw className="w-3 h-3" />
            </button>
          </div>
          <p className="text-xs text-[#e2e8f0] leading-relaxed">
            {locale === "he" ? tips[tipIdx].tip_he : tips[tipIdx].tip_en}
          </p>
          {tips[tipIdx].companies && tips[tipIdx].companies!.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {tips[tipIdx].companies!.map((ticker) => (
                <button
                  key={ticker}
                  onClick={() => onStockClick?.(ticker)}
                  className="px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300 text-[10px] font-mono font-medium hover:bg-amber-500/25 transition cursor-pointer"
                >
                  {ticker}
                </button>
              ))}
            </div>
          )}
          {tips.length > 1 && (
            <div className="flex gap-1 mt-2 justify-center">
              {tips.map((_, i) => (
                <button
                  key={i}
                  onClick={() => setTipIdx(i)}
                  className={`w-1.5 h-1.5 rounded-full transition ${i === tipIdx ? "bg-amber-400" : "bg-amber-500/30"}`}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
