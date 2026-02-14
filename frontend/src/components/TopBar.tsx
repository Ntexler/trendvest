"use client";
import { useI18n } from "@/i18n/context";
import { Globe, TrendingUp } from "lucide-react";

export default function TopBar() {
  const { locale, toggleLocale, t } = useI18n();

  return (
    <header className="sticky top-0 z-50 bg-[#0a0e17]/95 backdrop-blur border-b border-[#334155]">
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-6 h-6 text-cyan-400" />
          <span className="font-bold text-lg text-white">TrendVest</span>
          <span className="text-cyan-400 text-xs font-medium bg-cyan-400/10 px-2 py-0.5 rounded">AI</span>
        </div>
        <button
          onClick={toggleLocale}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#1e293b] hover:bg-[#334155] transition text-sm font-medium"
        >
          <Globe className="w-4 h-4" />
          {locale === "he" ? "EN" : "HE"}
        </button>
      </div>
    </header>
  );
}
