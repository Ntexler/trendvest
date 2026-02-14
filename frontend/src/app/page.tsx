"use client";
import { useState, useCallback } from "react";
import { I18nProvider, useI18n } from "@/i18n/context";
import { useWatchlist } from "@/hooks/useWatchlist";
import TopBar from "@/components/TopBar";
import MobileMenu from "@/components/MobileMenu";
import Dashboard from "@/components/Dashboard";
import NewsFeed from "@/components/NewsFeed";
import Screener from "@/components/Screener";
import PaperTrading from "@/components/PaperTrading";
import Watchlist from "@/components/Watchlist";
import StockProfile from "@/components/StockProfile";
import ChatBot from "@/components/ChatBot";

function AppContent() {
  const { t } = useI18n();
  const [page, setPage] = useState("trends");
  const [selectedStock, setSelectedStock] = useState<string | null>(null);
  const { watchlist, addTicker, removeTicker, isWatched } = useWatchlist();

  const toggleWatch = useCallback(
    (ticker: string) => {
      if (isWatched(ticker)) {
        removeTicker(ticker);
      } else {
        addTicker(ticker);
      }
    },
    [isWatched, addTicker, removeTicker]
  );

  const handleStockClick = useCallback((ticker: string) => {
    setSelectedStock(ticker);
  }, []);

  return (
    <div className="min-h-screen pb-20 md:pb-0">
      <TopBar />

      {/* Desktop Sidebar Nav */}
      <div className="hidden md:flex max-w-7xl mx-auto">
        <nav className="w-48 shrink-0 p-4 space-y-1 sticky top-14 h-[calc(100vh-3.5rem)]">
          {["trends", "news", "screener", "trade", "watchlist"].map((p) => (
            <button
              key={p}
              onClick={() => setPage(p)}
              className={`w-full text-start px-4 py-2 rounded-lg transition text-sm font-medium ${
                page === p
                  ? "bg-cyan-500/10 text-cyan-400"
                  : "text-[#94a3b8] hover:bg-[#1e293b] hover:text-white"
              }`}
            >
              {t(`nav.${p}` as any)}
            </button>
          ))}
        </nav>

        <main className="flex-1 p-6 min-w-0">
          {page === "trends" && (
            <Dashboard
              onStockClick={handleStockClick}
              isWatched={isWatched}
              toggleWatch={toggleWatch}
            />
          )}
          {page === "news" && <NewsFeed />}
          {page === "screener" && (
            <Screener
              onStockClick={handleStockClick}
              isWatched={isWatched}
              toggleWatch={toggleWatch}
            />
          )}
          {page === "trade" && <PaperTrading onStockClick={handleStockClick} />}
          {page === "watchlist" && (
            <Watchlist
              watchlist={watchlist}
              removeTicker={removeTicker}
              onStockClick={handleStockClick}
            />
          )}
        </main>
      </div>

      {/* Mobile Content */}
      <main className="md:hidden p-4">
        {page === "trends" && (
          <Dashboard
            onStockClick={handleStockClick}
            isWatched={isWatched}
            toggleWatch={toggleWatch}
          />
        )}
        {page === "news" && <NewsFeed />}
        {page === "screener" && (
          <Screener
            onStockClick={handleStockClick}
            isWatched={isWatched}
            toggleWatch={toggleWatch}
          />
        )}
        {page === "trade" && <PaperTrading onStockClick={handleStockClick} />}
        {page === "watchlist" && (
          <Watchlist
            watchlist={watchlist}
            removeTicker={removeTicker}
            onStockClick={handleStockClick}
          />
        )}
      </main>

      <MobileMenu activePage={page} onNavigate={setPage} />

      {/* Stock Profile Modal */}
      {selectedStock && (
        <StockProfile
          ticker={selectedStock}
          onClose={() => setSelectedStock(null)}
          isWatched={isWatched(selectedStock)}
          toggleWatch={() => toggleWatch(selectedStock)}
          onTrade={() => {
            setSelectedStock(null);
            setPage("trade");
          }}
          onStockClick={(t) => setSelectedStock(t)}
        />
      )}

      {/* AI Chatbot */}
      <ChatBot context={page === "trends" ? undefined : undefined} />
    </div>
  );
}

export default function Home() {
  return (
    <I18nProvider>
      <AppContent />
    </I18nProvider>
  );
}
