"use client";

import React, { createContext, useContext, useState, useCallback, useEffect } from "react";

type Mode = "beginner" | "expert";

interface ModeContextValue {
  mode: Mode;
  isBeginner: boolean;
  isExpert: boolean;
  toggleMode: () => void;
}

const ModeContext = createContext<ModeContextValue | null>(null);

export function ModeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setMode] = useState<Mode>("beginner");

  useEffect(() => {
    const saved = localStorage.getItem("trendvest_mode");
    if (saved === "beginner" || saved === "expert") {
      setMode(saved);
    }
  }, []);

  const toggleMode = useCallback(() => {
    setMode((prev) => {
      const next = prev === "beginner" ? "expert" : "beginner";
      localStorage.setItem("trendvest_mode", next);
      return next;
    });
  }, []);

  return (
    <ModeContext.Provider
      value={{ mode, isBeginner: mode === "beginner", isExpert: mode === "expert", toggleMode }}
    >
      {children}
    </ModeContext.Provider>
  );
}

export function useMode() {
  const ctx = useContext(ModeContext);
  if (!ctx) throw new Error("useMode must be used within ModeProvider");
  return ctx;
}
