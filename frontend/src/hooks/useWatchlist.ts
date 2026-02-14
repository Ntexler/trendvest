"use client";
import { useState, useEffect, useCallback } from "react";

const STORAGE_KEY = "trendvest_watchlist";

export function useWatchlist() {
  const [watchlist, setWatchlist] = useState<string[]>([]);

  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) setWatchlist(JSON.parse(saved));
  }, []);

  const save = (list: string[]) => {
    setWatchlist(list);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
  };

  const addTicker = useCallback((ticker: string) => {
    setWatchlist((prev) => {
      if (prev.includes(ticker)) return prev;
      const next = [...prev, ticker];
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const removeTicker = useCallback((ticker: string) => {
    setWatchlist((prev) => {
      const next = prev.filter((t) => t !== ticker);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const isWatched = useCallback(
    (ticker: string) => watchlist.includes(ticker),
    [watchlist]
  );

  return { watchlist, addTicker, removeTicker, isWatched };
}
