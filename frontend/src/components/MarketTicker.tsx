"use client";

import { useI18n } from "@/i18n/context";

interface TickerItem {
  label: { he: string; en: string };
  value: string;
  change: number;
}

const mockData: TickerItem[] = [
  { label: { he: "S&P 500", en: "S&P 500" }, value: "5,842", change: 0.34 },
  { label: { he: "VIX", en: "VIX" }, value: "14.2", change: -2.1 },
  { label: { he: "ביטקוין", en: "Bitcoin" }, value: "$97,450", change: 1.82 },
  { label: { he: "פחד/חמדנות", en: "Fear/Greed" }, value: "62", change: 3.0 },
];

export default function MarketTicker() {
  const { locale, t } = useI18n();

  return (
    <div className="bg-[#080b12] border-b border-[#1e293b] overflow-hidden">
      <div className="max-w-7xl mx-auto px-4 h-7 flex items-center justify-between gap-6">
        <div className="flex items-center gap-6 overflow-x-auto no-scrollbar">
          {mockData.map((item, i) => (
            <div key={i} className="flex items-center gap-1.5 shrink-0">
              <span className="text-[10px] text-[#64748b]">
                {item.label[locale]}
              </span>
              <span className="text-[10px] font-mono text-[#94a3b8]">
                {item.value}
              </span>
              <span
                className={`text-[10px] font-mono ${
                  item.change >= 0 ? "text-green-400" : "text-red-400"
                }`}
              >
                {item.change >= 0 ? "+" : ""}
                {item.change.toFixed(2)}%
              </span>
            </div>
          ))}
        </div>
        <span className="text-[9px] text-[#475569] shrink-0 hidden sm:block">
          {t("ticker.disclaimer" as any)}
        </span>
      </div>
    </div>
  );
}
