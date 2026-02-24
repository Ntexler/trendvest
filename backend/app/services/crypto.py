"""
Crypto market data service for TrendVest.
Uses CoinGecko API (free, no key needed) for real-time crypto prices,
market data, and trending coins.
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

try:
    import requests
except ImportError:
    requests = None

# Cache
_crypto_cache: dict[str, dict] = {}
CACHE_TTL = 300  # 5 minutes

COINGECKO_BASE = "https://api.coingecko.com/api/v3"

# Top coins to track
TRACKED_COINS = {
    "bitcoin": {"symbol": "BTC", "name": "Bitcoin", "name_he": "ביטקוין"},
    "ethereum": {"symbol": "ETH", "name": "Ethereum", "name_he": "את'ריום"},
    "binancecoin": {"symbol": "BNB", "name": "BNB", "name_he": "BNB"},
    "solana": {"symbol": "SOL", "name": "Solana", "name_he": "סולנה"},
    "ripple": {"symbol": "XRP", "name": "XRP", "name_he": "XRP"},
    "cardano": {"symbol": "ADA", "name": "Cardano", "name_he": "קרדאנו"},
    "dogecoin": {"symbol": "DOGE", "name": "Dogecoin", "name_he": "דוג'קוין"},
    "polkadot": {"symbol": "DOT", "name": "Polkadot", "name_he": "פולקדוט"},
    "avalanche-2": {"symbol": "AVAX", "name": "Avalanche", "name_he": "אוולנצ'"},
    "chainlink": {"symbol": "LINK", "name": "Chainlink", "name_he": "צ'יינלינק"},
    "tron": {"symbol": "TRX", "name": "TRON", "name_he": "TRON"},
    "uniswap": {"symbol": "UNI", "name": "Uniswap", "name_he": "יוניסוואפ"},
}

# Stablecoins (tracked separately)
STABLECOINS = {
    "tether": {"symbol": "USDT", "name": "Tether"},
    "usd-coin": {"symbol": "USDC", "name": "USD Coin"},
    "dai": {"symbol": "DAI", "name": "Dai"},
}


def _get(endpoint: str, params: dict = None) -> dict | list | None:
    """Make a GET request to CoinGecko API."""
    if requests is None:
        return None
    try:
        resp = requests.get(
            f"{COINGECKO_BASE}{endpoint}",
            params=params,
            headers={"Accept": "application/json"},
            timeout=10,
        )
        if resp.status_code == 429:
            time.sleep(2)  # Rate limit — wait and skip
            return None
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"CoinGecko API error: {e}")
        return None


def get_crypto_prices(vs_currency: str = "usd") -> list[dict]:
    """
    Get current prices for all tracked cryptocurrencies.

    Returns:
        List of coin dicts with price, change, market cap, volume
    """
    cache_key = f"crypto_prices:{vs_currency}"
    now = time.time()

    if cache_key in _crypto_cache:
        cached = _crypto_cache[cache_key]
        if now - cached["time"] < CACHE_TTL:
            return cached["data"]

    coin_ids = ",".join(list(TRACKED_COINS.keys()) + list(STABLECOINS.keys()))
    data = _get("/simple/price", params={
        "ids": coin_ids,
        "vs_currencies": vs_currency,
        "include_24hr_change": "true",
        "include_24hr_vol": "true",
        "include_market_cap": "true",
        "include_last_updated_at": "true",
    })

    if not data:
        return []

    results = []
    for coin_id, info in TRACKED_COINS.items():
        coin_data = data.get(coin_id)
        if not coin_data:
            continue
        results.append({
            "id": coin_id,
            "symbol": info["symbol"],
            "name": info["name"],
            "name_he": info["name_he"],
            "price": coin_data.get(vs_currency, 0),
            "change_24h_pct": round(coin_data.get(f"{vs_currency}_24h_change", 0), 2),
            "market_cap": coin_data.get(f"{vs_currency}_market_cap", 0),
            "volume_24h": coin_data.get(f"{vs_currency}_24h_vol", 0),
            "last_updated": coin_data.get("last_updated_at", 0),
            "is_stablecoin": False,
        })

    # Add stablecoins
    for coin_id, info in STABLECOINS.items():
        coin_data = data.get(coin_id)
        if not coin_data:
            continue
        results.append({
            "id": coin_id,
            "symbol": info["symbol"],
            "name": info["name"],
            "name_he": info["name"],
            "price": coin_data.get(vs_currency, 0),
            "change_24h_pct": round(coin_data.get(f"{vs_currency}_24h_change", 0), 2),
            "market_cap": coin_data.get(f"{vs_currency}_market_cap", 0),
            "volume_24h": coin_data.get(f"{vs_currency}_24h_vol", 0),
            "last_updated": coin_data.get("last_updated_at", 0),
            "is_stablecoin": True,
        })

    # Sort by market cap
    results.sort(key=lambda x: x.get("market_cap", 0), reverse=True)

    _crypto_cache[cache_key] = {"time": now, "data": results}
    return results


def get_crypto_market_overview() -> dict:
    """Get global crypto market overview."""
    cache_key = "crypto_global"
    now = time.time()

    if cache_key in _crypto_cache:
        cached = _crypto_cache[cache_key]
        if now - cached["time"] < CACHE_TTL:
            return cached["data"]

    data = _get("/global")
    if not data or "data" not in data:
        return {}

    global_data = data["data"]
    result = {
        "total_market_cap_usd": global_data.get("total_market_cap", {}).get("usd", 0),
        "total_volume_24h_usd": global_data.get("total_volume", {}).get("usd", 0),
        "bitcoin_dominance": round(global_data.get("market_cap_percentage", {}).get("btc", 0), 1),
        "ethereum_dominance": round(global_data.get("market_cap_percentage", {}).get("eth", 0), 1),
        "active_cryptocurrencies": global_data.get("active_cryptocurrencies", 0),
        "markets": global_data.get("markets", 0),
        "market_cap_change_24h_pct": round(global_data.get("market_cap_change_percentage_24h_usd", 0), 2),
    }

    _crypto_cache[cache_key] = {"time": now, "data": result}
    return result


def get_trending_coins() -> list[dict]:
    """Get trending coins on CoinGecko (most searched in last 24h)."""
    cache_key = "crypto_trending"
    now = time.time()

    if cache_key in _crypto_cache:
        cached = _crypto_cache[cache_key]
        if now - cached["time"] < CACHE_TTL:
            return cached["data"]

    data = _get("/search/trending")
    if not data or "coins" not in data:
        return []

    results = []
    for item in data["coins"][:10]:
        coin = item.get("item", {})
        results.append({
            "id": coin.get("id", ""),
            "symbol": coin.get("symbol", ""),
            "name": coin.get("name", ""),
            "market_cap_rank": coin.get("market_cap_rank"),
            "price_btc": coin.get("price_btc", 0),
            "score": coin.get("score", 0),
            "thumb": coin.get("thumb", ""),
        })

    _crypto_cache[cache_key] = {"time": now, "data": results}
    return results


def get_coin_history(coin_id: str, days: int = 30, vs_currency: str = "usd") -> list[dict]:
    """Get price history for a specific coin."""
    cache_key = f"crypto_history:{coin_id}:{days}:{vs_currency}"
    now = time.time()

    if cache_key in _crypto_cache:
        cached = _crypto_cache[cache_key]
        if now - cached["time"] < CACHE_TTL:
            return cached["data"]

    data = _get(f"/coins/{coin_id}/market_chart", params={
        "vs_currency": vs_currency,
        "days": str(days),
    })

    if not data or "prices" not in data:
        return []

    results = [
        {"timestamp": int(p[0]), "price": round(p[1], 2)}
        for p in data["prices"]
    ]

    _crypto_cache[cache_key] = {"time": now, "data": results}
    return results
