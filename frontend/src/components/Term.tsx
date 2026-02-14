"use client";

import { useState, useRef } from "react";
import { useI18n } from "@/i18n/context";

interface GlossaryEntry {
  he: string;
  en: string;
}

const glossary: Record<string, GlossaryEntry> = {
  "heat-score": {
    he: "ציון המבטא את עוצמת הטרנד — מבוסס על אזכורים, חיפושים ומומנטום מחיר. ככל שהציון גבוה יותר, הנושא חם יותר.",
    en: "A score reflecting trend intensity — based on mentions, searches, and price momentum. Higher score = hotter topic.",
  },
  momentum: {
    he: "קצב השינוי במחיר או בפופולריות של נכס. מומנטום חיובי = מגמת עלייה, שלילי = ירידה.",
    en: "Rate of change in price or popularity. Positive momentum = uptrend, negative = downtrend.",
  },
  sentiment: {
    he: "ניתוח הסנטימנט (חיובי/שלילי/ניטרלי) של חדשות ורשתות חברתיות סביב מניה או נושא.",
    en: "Analysis of positive/negative/neutral tone in news and social media around a stock or topic.",
  },
  "p-e": {
    he: "יחס מחיר-לרווח: מחיר המניה חלקי הרווח למניה. יחס גבוה עשוי להעיד על ציפייה לצמיחה או על תמחור יתר.",
    en: "Price-to-Earnings ratio: stock price divided by earnings per share. High P/E may indicate growth expectations or overvaluation.",
  },
  "market-cap": {
    he: "שווי שוק: מספר המניות הקיימות כפול מחיר המניה. משקף את הגודל הכולל של החברה בשוק.",
    en: "Market capitalization: total shares outstanding times share price. Reflects a company's total market size.",
  },
  etf: {
    he: "קרן סל נסחרת: מכשיר פיננסי שעוקב אחר מדד, סקטור או סל מניות. נסחר בבורסה כמו מניה רגילה.",
    en: "Exchange-Traded Fund: a financial instrument tracking an index, sector, or basket of stocks. Traded on exchanges like a regular stock.",
  },
  "paper-trading": {
    he: "מסחר וירטואלי (דמה): סימולציה של מסחר בכסף מדומה, ללא סיכון פיננסי. מיועד ללמידה ותרגול.",
    en: "Simulated trading with virtual money, without financial risk. Designed for learning and practice.",
  },
};

const termLabels: Record<string, GlossaryEntry> = {
  "heat-score": { he: "ציון חום", en: "Heat Score" },
  momentum: { he: "מומנטום", en: "Momentum" },
  sentiment: { he: "סנטימנט", en: "Sentiment" },
  "p-e": { he: "P/E", en: "P/E" },
  "market-cap": { he: "שווי שוק", en: "Market Cap" },
  etf: { he: "ETF", en: "ETF" },
  "paper-trading": { he: "מסחר דמה", en: "Paper Trading" },
};

interface Props {
  termKey: string;
  children: React.ReactNode;
}

export default function Term({ termKey, children }: Props) {
  const { locale } = useI18n();
  const [show, setShow] = useState(false);
  const timeoutRef = useRef<number | null>(null);

  const entry = glossary[termKey];
  const label = termLabels[termKey];
  if (!entry) return <>{children}</>;

  const handleMouseEnter = () => {
    if (timeoutRef.current !== null) window.clearTimeout(timeoutRef.current);
    setShow(true);
  };

  const handleMouseLeave = () => {
    timeoutRef.current = window.setTimeout(() => setShow(false), 150);
  };

  return (
    <span
      className="relative inline-block cursor-help"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <span className="border-b border-dotted border-cyan-400">{children}</span>
      {show && (
        <div className="absolute z-50 bottom-full start-0 mb-2 w-64 bg-[#1e293b] border border-[#334155] rounded-lg p-3 shadow-xl pointer-events-auto">
          <div className="text-xs font-bold text-cyan-400 mb-1">
            {label ? label[locale] : termKey}
          </div>
          <p className="text-xs text-[#cbd5e1] leading-relaxed">{entry[locale]}</p>
          <div className="absolute top-full start-4 w-2 h-2 bg-[#1e293b] border-b border-e border-[#334155] rotate-45 -translate-y-1" />
        </div>
      )}
    </span>
  );
}
