"use client";
import { useState, useRef, useEffect } from "react";
import { HelpCircle, Loader2 } from "lucide-react";
import { useI18n } from "@/i18n/context";
import { explainTerm } from "@/lib/api";

const cache = new Map<string, string>();

interface Props {
  term: string;
  children: React.ReactNode;
}

export default function ExplainTooltip({ term, children }: Props) {
  const { t, locale } = useI18n();
  const [open, setOpen] = useState(false);
  const [explanation, setExplanation] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [open]);

  const handleClick = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (open) {
      setOpen(false);
      return;
    }
    setOpen(true);
    const cacheKey = `${term}:${locale}`;
    if (cache.has(cacheKey)) {
      setExplanation(cache.get(cacheKey)!);
      return;
    }
    setLoading(true);
    try {
      const res = await explainTerm(term, locale);
      cache.set(cacheKey, res.explanation);
      setExplanation(res.explanation);
    } catch {
      setExplanation(t("explain.error"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative inline-flex items-center gap-1" ref={ref}>
      {children}
      <button
        onClick={handleClick}
        className="text-[#64748b] hover:text-cyan-400 transition"
        title={t("explain.tapToLearn")}
      >
        <HelpCircle className="w-3 h-3" />
      </button>
      {open && (
        <div className="absolute z-50 bottom-full mb-2 start-0 w-64 bg-[#1e293b] border border-[#334155] rounded-lg p-3 shadow-xl">
          {loading ? (
            <div className="flex items-center gap-2 text-xs text-[#94a3b8]">
              <Loader2 className="w-3 h-3 animate-spin" />
              {t("explain.loading")}
            </div>
          ) : (
            <p className="text-xs text-[#cbd5e1] leading-relaxed">{explanation}</p>
          )}
        </div>
      )}
    </div>
  );
}
