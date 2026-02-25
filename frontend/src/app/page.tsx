"use client";
import { useState, useCallback } from "react";
import { I18nProvider, useI18n } from "@/i18n/context";
import { ModeProvider } from "@/contexts/ModeContext";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import { useWatchlist } from "@/hooks/useWatchlist";
import MarketTicker from "@/components/MarketTicker";
import TopBar from "@/components/TopBar";
import MobileMenu from "@/components/MobileMenu";
import TrendFeed from "@/components/TrendFeed";
import Screener from "@/components/Screener";
import PaperTrading from "@/components/PaperTrading";
import Watchlist from "@/components/Watchlist";
import StockProfile from "@/components/StockProfile";
import ChatBot from "@/components/ChatBot";
import AgentDashboard from "@/components/AgentDashboard";
import AdminDashboard from "@/components/AdminDashboard";
import AuthPage from "@/components/AuthPage";
import { LogOut, Shield } from "lucide-react";

function AppContent() {
  const { t } = useI18n();
  const { user, loading, isAdmin, logout } = useAuth();
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

  const handleBuy = useCallback((ticker: string) => {
    setSelectedStock(null);
    setPage("trade");
  }, []);

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  // Not authenticated — show login
  if (!user) {
    return <AuthPage />;
  }

  // Nav items — hide admin for non-admins
  const navItems = ["trends", "screener", "trade", "watchlist", "agent"];
  if (isAdmin) navItems.push("admin");

  return (
    <div className="min-h-screen pb-20 md:pb-0">
      <MarketTicker />
      <TopBar />

      {/* Desktop Sidebar Nav */}
      <div className="hidden md:flex max-w-7xl mx-auto">
        <nav className="w-48 shrink-0 p-4 space-y-1 sticky top-14 h-[calc(100vh-3.5rem)]">
          {navItems.map((p) => (
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

          {/* User info + logout at bottom */}
          <div className="!mt-auto pt-4 border-t border-[#1e293b]">
            <div className="flex items-center gap-2 px-4 py-2">
              <div className="w-6 h-6 rounded-full bg-cyan-500/20 flex items-center justify-center">
                <span className="text-[10px] font-bold text-cyan-400">
                  {(user.display_name || user.email)[0].toUpperCase()}
                </span>
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-xs text-white truncate">{user.display_name || user.email}</div>
                {isAdmin && (
                  <div className="flex items-center gap-1 text-[9px] text-amber-400">
                    <Shield className="w-2.5 h-2.5" />
                    Admin
                  </div>
                )}
              </div>
              <button
                onClick={logout}
                className="p-1 rounded hover:bg-[#1e293b] text-[#64748b] hover:text-red-400 transition"
                title="Logout"
              >
                <LogOut className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </nav>

        <main className="flex-1 p-6 min-w-0">
          {page === "trends" && (
            <TrendFeed
              onStockClick={handleStockClick}
              isWatched={isWatched}
              toggleWatch={toggleWatch}
            />
          )}
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
              onBuy={handleBuy}
            />
          )}
          {page === "agent" && <AgentDashboard onStockClick={handleStockClick} />}
          {page === "admin" && isAdmin && <AdminDashboard />}
        </main>
      </div>

      {/* Mobile Content */}
      <main className="md:hidden p-4">
        {page === "trends" && (
          <TrendFeed
            onStockClick={handleStockClick}
            isWatched={isWatched}
            toggleWatch={toggleWatch}
          />
        )}
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
            onBuy={handleBuy}
          />
        )}
        {page === "agent" && <AgentDashboard onStockClick={handleStockClick} />}
        {page === "admin" && isAdmin && <AdminDashboard />}
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
      <ModeProvider>
        <AuthProvider>
          <AppContent />
        </AuthProvider>
      </ModeProvider>
    </I18nProvider>
  );
}
