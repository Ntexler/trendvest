"use client";

import React, { createContext, useContext, useState, useCallback } from "react";
import translations, { type TranslationKey } from "./translations";

type Locale = "he" | "en";

interface I18nContextValue {
  locale: Locale;
  dir: "rtl" | "ltr";
  toggleLocale: () => void;
  t: (key: TranslationKey) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocale] = useState<Locale>("he");

  const toggleLocale = useCallback(() => {
    setLocale((prev) => (prev === "he" ? "en" : "he"));
  }, []);

  const dir = locale === "he" ? "rtl" : "ltr";

  const t = useCallback(
    (key: TranslationKey): string => {
      const entry = translations[key];
      return entry ? entry[locale] : key;
    },
    [locale]
  );

  return (
    <I18nContext.Provider value={{ locale, dir, toggleLocale, t }}>
      <div dir={dir} className={locale === "he" ? "font-rubik" : ""}>
        {children}
      </div>
    </I18nContext.Provider>
  );
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used within I18nProvider");
  return ctx;
}
