"""
Commodity and Forex data service for TrendVest.
Uses yfinance for commodity futures and forex rates,
plus FRED for additional macroeconomic commodity data.
"""
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

try:
    import yfinance as yf
except ImportError:
    yf = None

# Cache
_commodity_cache: dict[str, dict] = {}
CACHE_TTL = 600  # 10 minutes

# ── Commodities via yfinance ticker symbols ──

COMMODITIES = {
    # Metals
    "gold": {
        "ticker": "GC=F", "name": "Gold", "name_he": "זהב",
        "category": "metals", "unit": "$/oz",
        "supply_chain": ["jewelry", "electronics", "central_banks", "investment"],
    },
    "silver": {
        "ticker": "SI=F", "name": "Silver", "name_he": "כסף",
        "category": "metals", "unit": "$/oz",
        "supply_chain": ["electronics", "solar_panels", "jewelry", "industrial"],
    },
    "copper": {
        "ticker": "HG=F", "name": "Copper", "name_he": "נחושת",
        "category": "metals", "unit": "$/lb",
        "supply_chain": ["semiconductors", "ev_batteries", "construction", "power_grid", "electronics"],
    },
    "platinum": {
        "ticker": "PL=F", "name": "Platinum", "name_he": "פלטינום",
        "category": "metals", "unit": "$/oz",
        "supply_chain": ["automotive_catalysts", "hydrogen_fuel_cells", "jewelry"],
    },
    # Energy
    "crude_oil": {
        "ticker": "CL=F", "name": "Crude Oil (WTI)", "name_he": "נפט גולמי",
        "category": "energy", "unit": "$/bbl",
        "supply_chain": ["transportation", "plastics", "chemicals", "aviation"],
    },
    "brent_oil": {
        "ticker": "BZ=F", "name": "Brent Crude", "name_he": "ברנט",
        "category": "energy", "unit": "$/bbl",
        "supply_chain": ["europe_energy", "shipping", "petrochemicals"],
    },
    "natural_gas": {
        "ticker": "NG=F", "name": "Natural Gas", "name_he": "גז טבעי",
        "category": "energy", "unit": "$/MMBtu",
        "supply_chain": ["electricity", "heating", "fertilizers", "israel_gas"],
    },
    "uranium": {
        "ticker": "URA", "name": "Uranium (ETF)", "name_he": "אורניום",
        "category": "energy", "unit": "ETF price",
        "supply_chain": ["nuclear_energy", "medical_isotopes"],
    },
    # Agricultural
    "wheat": {
        "ticker": "ZW=F", "name": "Wheat", "name_he": "חיטה",
        "category": "agriculture", "unit": "cents/bu",
        "supply_chain": ["food_production", "bread", "livestock_feed"],
    },
    "corn": {
        "ticker": "ZC=F", "name": "Corn", "name_he": "תירס",
        "category": "agriculture", "unit": "cents/bu",
        "supply_chain": ["ethanol", "livestock_feed", "food_production"],
    },
    "soybeans": {
        "ticker": "ZS=F", "name": "Soybeans", "name_he": "סויה",
        "category": "agriculture", "unit": "cents/bu",
        "supply_chain": ["animal_feed", "biodiesel", "food_products"],
    },
    "coffee": {
        "ticker": "KC=F", "name": "Coffee", "name_he": "קפה",
        "category": "agriculture", "unit": "cents/lb",
        "supply_chain": ["consumer_goods", "restaurants", "retail"],
    },
    "cocoa": {
        "ticker": "CC=F", "name": "Cocoa", "name_he": "קקאו",
        "category": "agriculture", "unit": "$/ton",
        "supply_chain": ["chocolate", "consumer_goods", "confectionery"],
    },
    "sugar": {
        "ticker": "SB=F", "name": "Sugar", "name_he": "סוכר",
        "category": "agriculture", "unit": "cents/lb",
        "supply_chain": ["food_production", "ethanol", "consumer_goods"],
    },
    "cotton": {
        "ticker": "CT=F", "name": "Cotton", "name_he": "כותנה",
        "category": "agriculture", "unit": "cents/lb",
        "supply_chain": ["textiles", "apparel", "fashion"],
    },
    "orange_juice": {
        "ticker": "OJ=F", "name": "Orange Juice", "name_he": "מיץ תפוזים",
        "category": "agriculture", "unit": "cents/lb",
        "supply_chain": ["beverages", "food_production"],
    },
    "live_cattle": {
        "ticker": "LE=F", "name": "Live Cattle", "name_he": "בקר",
        "category": "agriculture", "unit": "cents/lb",
        "supply_chain": ["meat_production", "restaurants", "retail"],
    },
    "lumber": {
        "ticker": "LBS=F", "name": "Lumber", "name_he": "עצים",
        "category": "agriculture", "unit": "$/mbf",
        "supply_chain": ["construction", "housing", "furniture"],
    },
    # Industrial / Battery / Metals
    "lithium": {
        "ticker": "LIT", "name": "Lithium (ETF)", "name_he": "ליתיום",
        "category": "industrial", "unit": "ETF price",
        "supply_chain": ["ev_batteries", "smartphones", "energy_storage"],
    },
    "palladium": {
        "ticker": "PA=F", "name": "Palladium", "name_he": "פלדיום",
        "category": "metals", "unit": "$/oz",
        "supply_chain": ["automotive_catalysts", "electronics", "dentistry"],
    },
    "nickel": {
        "ticker": "NICK.L", "name": "Nickel (ETF)", "name_he": "ניקל",
        "category": "industrial", "unit": "ETF price",
        "supply_chain": ["ev_batteries", "stainless_steel", "aerospace"],
    },
    "cobalt": {
        "ticker": "LIT", "name": "Cobalt (via Lithium ETF)", "name_he": "קובלט",
        "category": "industrial", "unit": "ETF proxy",
        "supply_chain": ["ev_batteries", "superalloys", "magnets"],
    },
    "tin": {
        "ticker": "JJT", "name": "Tin (ETN)", "name_he": "בדיל",
        "category": "metals", "unit": "ETN price",
        "supply_chain": ["soldering", "electronics", "semiconductors", "canning"],
    },
    "aluminum": {
        "ticker": "JJU", "name": "Aluminum (ETN)", "name_he": "אלומיניום",
        "category": "metals", "unit": "ETN price",
        "supply_chain": ["automotive", "aerospace", "packaging", "construction"],
    },
    # Energy additions
    "gasoline": {
        "ticker": "RB=F", "name": "Gasoline (RBOB)", "name_he": "בנזין",
        "category": "energy", "unit": "$/gal",
        "supply_chain": ["transportation", "consumer", "refining"],
    },
    "heating_oil": {
        "ticker": "HO=F", "name": "Heating Oil", "name_he": "סולר",
        "category": "energy", "unit": "$/gal",
        "supply_chain": ["heating", "diesel", "transportation"],
    },
    "carbon": {
        "ticker": "KRBN", "name": "Carbon Credits (ETF)", "name_he": "קרדיט פחמן",
        "category": "energy", "unit": "ETF price",
        "supply_chain": ["emissions_trading", "esg", "industrial_regulation"],
    },
}

# ── Forex pairs ──

FOREX_PAIRS = {
    "USD/ILS": {
        "ticker": "USDILS=X", "name": "US Dollar / Israeli Shekel",
        "name_he": "דולר / שקל", "category": "major",
    },
    "EUR/USD": {
        "ticker": "EURUSD=X", "name": "Euro / US Dollar",
        "name_he": "אירו / דולר", "category": "major",
    },
    "GBP/USD": {
        "ticker": "GBPUSD=X", "name": "British Pound / US Dollar",
        "name_he": "ליש״ט / דולר", "category": "major",
    },
    "USD/JPY": {
        "ticker": "USDJPY=X", "name": "US Dollar / Japanese Yen",
        "name_he": "דולר / ין", "category": "major",
    },
    "USD/CNY": {
        "ticker": "USDCNY=X", "name": "US Dollar / Chinese Yuan",
        "name_he": "דולר / יואן", "category": "major",
    },
    "EUR/ILS": {
        "ticker": "EURILS=X", "name": "Euro / Israeli Shekel",
        "name_he": "אירו / שקל", "category": "israel",
    },
    "GBP/ILS": {
        "ticker": "GBPILS=X", "name": "British Pound / Israeli Shekel",
        "name_he": "ליש״ט / שקל", "category": "israel",
    },
    "BTC/USD": {
        "ticker": "BTC-USD", "name": "Bitcoin / US Dollar",
        "name_he": "ביטקוין / דולר", "category": "crypto",
    },
    "ETH/USD": {
        "ticker": "ETH-USD", "name": "Ethereum / US Dollar",
        "name_he": "את'ריום / דולר", "category": "crypto",
    },
}

# ── Bond yields (via yfinance) ──

BOND_YIELDS = {
    "us_2y": {
        "ticker": "^IRX", "name": "US 13-Week T-Bill", "name_he": "אג״ח ארה״ב 13 שבועות",
        "maturity": "3m",
    },
    "us_5y": {
        "ticker": "^FVX", "name": "US 5-Year Treasury", "name_he": "אג״ח ארה״ב 5 שנים",
        "maturity": "5y",
    },
    "us_10y": {
        "ticker": "^TNX", "name": "US 10-Year Treasury", "name_he": "אג״ח ארה״ב 10 שנים",
        "maturity": "10y",
    },
    "us_30y": {
        "ticker": "^TYX", "name": "US 30-Year Treasury", "name_he": "אג״ח ארה״ב 30 שנה",
        "maturity": "30y",
    },
}


def _fetch_yf_price(ticker: str) -> dict | None:
    """Fetch current price from yfinance."""
    if yf is None:
        return None
    try:
        t = yf.Ticker(ticker)
        info = t.fast_info
        price = getattr(info, "last_price", None) or getattr(info, "previous_close", None)
        prev_close = getattr(info, "previous_close", None)
        if price is None:
            return None
        change = round(price - prev_close, 4) if prev_close else 0
        change_pct = round((change / prev_close) * 100, 2) if prev_close else 0
        return {
            "price": round(price, 4),
            "previous_close": round(prev_close, 4) if prev_close else None,
            "change": change,
            "change_pct": change_pct,
        }
    except Exception as e:
        print(f"yfinance error for {ticker}: {e}")
        return None


def get_commodity_prices(category: Optional[str] = None) -> list[dict]:
    """
    Get current commodity prices.

    Args:
        category: Filter by category (metals, energy, agriculture, industrial)

    Returns:
        List of commodity dicts with price, change, supply chain info
    """
    cache_key = f"commodities:{category or 'all'}"
    now = time.time()

    if cache_key in _commodity_cache:
        cached = _commodity_cache[cache_key]
        if now - cached["time"] < CACHE_TTL:
            return cached["data"]

    items = COMMODITIES
    if category:
        items = {k: v for k, v in items.items() if v["category"] == category}

    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {}
        for key, info in items.items():
            futures[executor.submit(_fetch_yf_price, info["ticker"])] = (key, info)

        for future in as_completed(futures):
            key, info = futures[future]
            try:
                price_data = future.result()
                result = {
                    "key": key,
                    "name": info["name"],
                    "name_he": info["name_he"],
                    "category": info["category"],
                    "unit": info["unit"],
                    "supply_chain": info["supply_chain"],
                    "ticker": info["ticker"],
                }
                if price_data:
                    result.update(price_data)
                else:
                    result.update({"price": None, "change": None, "change_pct": None})
                results.append(result)
            except Exception:
                pass

    results.sort(key=lambda x: x.get("category", ""))

    _commodity_cache[cache_key] = {"time": now, "data": results}
    return results


def get_forex_rates(category: Optional[str] = None) -> list[dict]:
    """
    Get current forex rates.

    Args:
        category: Filter by category (major, israel, crypto)

    Returns:
        List of forex pair dicts with rate and change
    """
    cache_key = f"forex:{category or 'all'}"
    now = time.time()

    if cache_key in _commodity_cache:
        cached = _commodity_cache[cache_key]
        if now - cached["time"] < CACHE_TTL:
            return cached["data"]

    pairs = FOREX_PAIRS
    if category:
        pairs = {k: v for k, v in pairs.items() if v["category"] == category}

    results = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {}
        for pair_name, info in pairs.items():
            futures[executor.submit(_fetch_yf_price, info["ticker"])] = (pair_name, info)

        for future in as_completed(futures):
            pair_name, info = futures[future]
            try:
                price_data = future.result()
                result = {
                    "pair": pair_name,
                    "name": info["name"],
                    "name_he": info["name_he"],
                    "category": info["category"],
                    "ticker": info["ticker"],
                }
                if price_data:
                    result["rate"] = price_data["price"]
                    result["change"] = price_data["change"]
                    result["change_pct"] = price_data["change_pct"]
                else:
                    result["rate"] = None
                    result["change"] = None
                    result["change_pct"] = None
                results.append(result)
            except Exception:
                pass

    _commodity_cache[cache_key] = {"time": now, "data": results}
    return results


def get_bond_yields() -> list[dict]:
    """Get US Treasury bond yields across the curve."""
    cache_key = "bond_yields"
    now = time.time()

    if cache_key in _commodity_cache:
        cached = _commodity_cache[cache_key]
        if now - cached["time"] < CACHE_TTL:
            return cached["data"]

    results = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}
        for key, info in BOND_YIELDS.items():
            futures[executor.submit(_fetch_yf_price, info["ticker"])] = (key, info)

        for future in as_completed(futures):
            key, info = futures[future]
            try:
                price_data = future.result()
                result = {
                    "key": key,
                    "name": info["name"],
                    "name_he": info["name_he"],
                    "maturity": info["maturity"],
                }
                if price_data:
                    result["yield_pct"] = price_data["price"]
                    result["change"] = price_data["change"]
                    result["change_pct"] = price_data["change_pct"]
                else:
                    result["yield_pct"] = None
                    result["change"] = None
                    result["change_pct"] = None
                results.append(result)
            except Exception:
                pass

    # Sort by maturity
    maturity_order = {"3m": 0, "5y": 1, "10y": 2, "30y": 3}
    results.sort(key=lambda x: maturity_order.get(x.get("maturity", ""), 99))

    _commodity_cache[cache_key] = {"time": now, "data": results}
    return results


def get_market_overview() -> dict:
    """Get a full overview: commodities + forex + bonds."""
    return {
        "commodities": get_commodity_prices(),
        "forex": get_forex_rates(),
        "bonds": get_bond_yields(),
    }
