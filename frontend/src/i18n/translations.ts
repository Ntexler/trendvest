const translations = {
  // Navigation
  "nav.trends": { he: "טרנדים", en: "Trends" },
  "nav.news": { he: "חדשות", en: "News" },
  "nav.screener": { he: "סקרינר", en: "Screener" },
  "nav.trade": { he: "תרגול", en: "Practice" },
  "nav.watchlist": { he: "מעקב", en: "Watchlist" },

  // Dashboard
  "dashboard.title": { he: "מגמות חמות", en: "Hot Trends" },
  "dashboard.topMovers": { he: "מובילי השינוי", en: "Top Movers" },
  "dashboard.allSectors": { he: "כל הסקטורים", en: "All Sectors" },
  "dashboard.noTopics": { he: "אין נושאים להצגה", en: "No topics to show" },

  // Stock
  "stock.price": { he: "מחיר", en: "Price" },
  "stock.change": { he: "שינוי", en: "Change" },
  "stock.readMore": { he: "קרא עוד", en: "Read More" },
  "stock.sector": { he: "סקטור", en: "Sector" },
  "stock.industry": { he: "ענף", en: "Industry" },
  "stock.employees": { he: "עובדים", en: "Employees" },
  "stock.marketCap": { he: "שווי שוק", en: "Market Cap" },
  "stock.website": { he: "אתר", en: "Website" },
  "stock.addWatchlist": { he: "הוסף למעקב", en: "Add to Watchlist" },
  "stock.removeWatchlist": { he: "הסר ממעקב", en: "Remove from Watchlist" },

  // News
  "news.title": { he: "חדשות", en: "News" },
  "news.latest": { he: "חדשות אחרונות", en: "Latest News" },
  "news.noArticles": { he: "אין חדשות להצגה", en: "No articles to show" },

  // Screener
  "screener.title": { he: "סקרינר מניות", en: "Stock Screener" },
  "screener.search": { he: "חפש מניה...", en: "Search stock..." },
  "screener.sortBy": { he: "מיין לפי", en: "Sort by" },
  "screener.maxPrice": { he: "מחיר מקסימלי", en: "Max Price" },

  // Trading
  "trade.title": { he: "תרגול מסחר", en: "Practice Trading" },
  "trade.disclaimer": {
    he: "זהו מצב תרגול עם כסף וירטואלי בלבד. רווחים מדומים אינם מבטיחים תוצאות במסחר אמיתי. אין בכך ייעוץ השקעות — למטרות לימוד בלבד.",
    en: "This is practice mode with virtual money only. Simulated gains do not guarantee real trading results. Not investment advice — for educational purposes only.",
  },
  "trade.cash": { he: "מזומן", en: "Cash" },
  "trade.totalValue": { he: "שווי כולל", en: "Total Value" },
  "trade.pnl": { he: "רווח/הפסד", en: "P&L" },
  "trade.buy": { he: "קנה", en: "Buy" },
  "trade.sell": { he: "מכור", en: "Sell" },
  "trade.quantity": { he: "כמות", en: "Quantity" },
  "trade.execute": { he: "בצע עסקה", en: "Execute Trade" },
  "trade.history": { he: "היסטוריית עסקאות", en: "Trade History" },
  "trade.holdings": { he: "אחזקות", en: "Holdings" },
  "trade.noHoldings": { he: "אין אחזקות עדיין", en: "No holdings yet" },
  "trade.startTrading": { he: "התחל לסחור", en: "Start Trading" },

  // Watchlist
  "watchlist.title": { he: "רשימת מעקב", en: "Watchlist" },
  "watchlist.empty": { he: "הרשימה ריקה", en: "Watchlist is empty" },
  "watchlist.addTip": {
    he: 'לחץ על ⭐ ליד מניה כדי להוסיף למעקב',
    en: 'Click ⭐ next to a stock to add to watchlist',
  },

  // Chat
  "chat.title": { he: "עוזר AI", en: "AI Assistant" },
  "chat.placeholder": { he: "שאל שאלה...", en: "Ask a question..." },
  "chat.remaining": { he: "שאלות נותרו", en: "questions remaining" },
  "chat.send": { he: "שלח", en: "Send" },

  // General
  "general.loading": { he: "טוען...", en: "Loading..." },
  "general.error": { he: "שגיאה", en: "Error" },
  "general.close": { he: "סגור", en: "Close" },
  "general.cancel": { he: "ביטול", en: "Cancel" },
  "general.confirm": { he: "אישור", en: "Confirm" },
} as const;

export type TranslationKey = keyof typeof translations;
export default translations;
