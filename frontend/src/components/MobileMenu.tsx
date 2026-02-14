"use client";
import { useI18n } from "@/i18n/context";
import { TrendingUp, Newspaper, Search, BarChart3, Star } from "lucide-react";

interface Props {
  activePage: string;
  onNavigate: (page: string) => void;
}

const tabs = [
  { id: "trends", icon: TrendingUp, labelKey: "nav.trends" as const },
  { id: "news", icon: Newspaper, labelKey: "nav.news" as const },
  { id: "screener", icon: Search, labelKey: "nav.screener" as const },
  { id: "trade", icon: BarChart3, labelKey: "nav.trade" as const },
  { id: "watchlist", icon: Star, labelKey: "nav.watchlist" as const },
];

export default function MobileMenu({ activePage, onNavigate }: Props) {
  const { t } = useI18n();

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 bg-[#0a0e17]/95 backdrop-blur border-t border-[#334155] md:hidden">
      <div className="flex items-center justify-around h-16">
        {tabs.map(({ id, icon: Icon, labelKey }) => (
          <button
            key={id}
            onClick={() => onNavigate(id)}
            className={`flex flex-col items-center gap-0.5 px-3 py-1 rounded-lg transition ${
              activePage === id ? "text-cyan-400" : "text-[#94a3b8] hover:text-white"
            }`}
          >
            <Icon className="w-5 h-5" />
            <span className="text-[10px] font-medium">{t(labelKey)}</span>
          </button>
        ))}
      </div>
    </nav>
  );
}
