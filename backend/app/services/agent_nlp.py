"""
Financial NLP sentiment analyzer for TrendVest.

A rule-based sentiment engine that scores financial text WITHOUT external APIs.
This runs on any text — Reddit titles, blog descriptions, news headlines.

Approach: Lexicon-based with financial domain specialization.
- Curated list of ~200 bullish/bearish financial terms
- Negation handling ("not bullish" → bearish)
- Intensity modifiers ("very bullish" vs "slightly bullish")
- Ticker-adjacent context ("NVDA crushed earnings" = bullish for NVDA)

Honest note: This is NOT comparable to GPT/Claude-level understanding.
It catches obvious sentiment ("stock crashes", "beat estimates") but misses
sarcasm, nuance, and context. Still, it's a massive upgrade from raw
mention counting — and it works without API limits.
"""

from __future__ import annotations

import re
from typing import Optional

# ── Bullish lexicon ──
# Scored 0.1 (weak) to 1.0 (very bullish)
BULLISH_TERMS: dict[str, float] = {
    # Strong bullish
    "moon": 0.8, "mooning": 0.9, "rocket": 0.7, "skyrocket": 0.9,
    "surge": 0.8, "surging": 0.8, "soar": 0.8, "soaring": 0.8,
    "rally": 0.7, "rallying": 0.7, "breakout": 0.7, "breakthrough": 0.7,
    "boom": 0.7, "booming": 0.7, "explode": 0.7, "exploding": 0.7,
    "all-time high": 0.8, "ath": 0.7, "new high": 0.7,
    # Earnings & fundamentals
    "beat": 0.7, "beats": 0.7, "beat estimates": 0.8, "crushed": 0.8,
    "outperform": 0.7, "outperforms": 0.7, "outperforming": 0.7,
    "exceeded expectations": 0.8, "above consensus": 0.7,
    "record revenue": 0.8, "record profit": 0.8, "record earnings": 0.8,
    "guidance raised": 0.8, "upgraded": 0.7, "upgrade": 0.7,
    "strong earnings": 0.7, "earnings beat": 0.8, "eps beat": 0.8,
    "revenue beat": 0.7, "top line beat": 0.7, "bottom line beat": 0.7,
    # Growth
    "growth": 0.5, "growing": 0.5, "accelerating": 0.6,
    "expansion": 0.5, "expanding": 0.5, "scaling": 0.5,
    "bullish": 0.7, "bull": 0.5, "long": 0.4,
    "buy": 0.5, "buying": 0.5, "accumulate": 0.6,
    "upside": 0.6, "potential": 0.4, "opportunity": 0.5,
    # Market structure
    "short squeeze": 0.7, "gamma squeeze": 0.7,
    "undervalued": 0.6, "cheap": 0.4, "bargain": 0.6, "discount": 0.5,
    "oversold": 0.5, "bounce": 0.5, "recovery": 0.5, "recovering": 0.5,
    "golden cross": 0.6, "breakout volume": 0.6,
    # Positive general
    "strong": 0.4, "impressive": 0.5, "solid": 0.4, "excellent": 0.5,
    "amazing": 0.5, "incredible": 0.5, "massive": 0.4,
    "profit": 0.4, "profitable": 0.5, "innovation": 0.4,
    "momentum": 0.4, "positive": 0.4, "optimistic": 0.5,
    "confidence": 0.4, "promising": 0.5,
    # AI / Tech specific
    "ai revolution": 0.6, "game changer": 0.6, "disruptive": 0.5,
    "market leader": 0.5, "dominant": 0.5, "moat": 0.5,
}

# ── Bearish lexicon ──
BEARISH_TERMS: dict[str, float] = {
    # Strong bearish
    "crash": 0.9, "crashing": 0.9, "collapse": 0.9, "collapsing": 0.9,
    "plunge": 0.8, "plunging": 0.8, "tank": 0.8, "tanking": 0.8,
    "dump": 0.7, "dumping": 0.7, "sell-off": 0.8, "selloff": 0.8,
    "freefall": 0.9, "free fall": 0.9, "bloodbath": 0.8,
    "circuit breaker": 0.9, "flash crash": 0.9,
    # Earnings & fundamentals
    "miss": 0.7, "misses": 0.7, "missed estimates": 0.8, "missed": 0.6,
    "underperform": 0.7, "underperforms": 0.7, "underperforming": 0.7,
    "below expectations": 0.7, "below consensus": 0.7,
    "guidance cut": 0.8, "lowered guidance": 0.8, "guidance lowered": 0.8,
    "downgrade": 0.7, "downgraded": 0.7,
    "revenue miss": 0.7, "earnings miss": 0.8, "eps miss": 0.8,
    "weak earnings": 0.7, "disappointing": 0.6,
    # Decline
    "decline": 0.5, "declining": 0.5, "shrinking": 0.6,
    "contraction": 0.6, "contracting": 0.6, "slowing": 0.5,
    "bearish": 0.7, "bear": 0.5, "short": 0.4,
    "sell": 0.5, "selling": 0.5, "avoid": 0.5,
    "downside": 0.6, "risk": 0.3, "risky": 0.4,
    # Market structure
    "overvalued": 0.6, "expensive": 0.4, "bubble": 0.7,
    "overbought": 0.5, "death cross": 0.6,
    "margin call": 0.7, "liquidation": 0.7,
    # Negative general
    "weak": 0.4, "poor": 0.5, "terrible": 0.6, "awful": 0.6,
    "loss": 0.5, "losses": 0.5, "losing": 0.5,
    "debt": 0.3, "bankrupt": 0.9, "bankruptcy": 0.9, "insolvent": 0.8,
    "layoffs": 0.6, "layoff": 0.6, "restructuring": 0.4,
    "recession": 0.7, "stagflation": 0.7, "inflation": 0.4,
    "fraud": 0.9, "scandal": 0.7, "investigation": 0.5,
    "lawsuit": 0.5, "fine": 0.4, "penalty": 0.4, "sec probe": 0.7,
    "negative": 0.4, "pessimistic": 0.5, "fear": 0.5, "panic": 0.7,
    "warning": 0.5, "caution": 0.4, "concern": 0.3,
}

# ── Negation words ──
NEGATION_WORDS = {
    "not", "no", "never", "neither", "nor", "don't", "doesn't",
    "didn't", "won't", "wouldn't", "can't", "cannot", "isn't",
    "aren't", "wasn't", "weren't", "hardly", "barely", "scarcely",
}

# ── Intensity modifiers ──
INTENSIFIERS: dict[str, float] = {
    "very": 1.3, "extremely": 1.5, "incredibly": 1.4,
    "absolutely": 1.4, "highly": 1.3, "significantly": 1.3,
    "massive": 1.3, "huge": 1.3, "enormous": 1.3,
}
DIMINISHERS: dict[str, float] = {
    "slightly": 0.6, "somewhat": 0.7, "barely": 0.5,
    "a bit": 0.6, "a little": 0.6, "marginally": 0.6,
    "possibly": 0.7, "maybe": 0.7, "might": 0.7,
}


def analyze_text_sentiment(text: str) -> dict:
    """
    Analyze sentiment of a single text (headline, title, description).

    Returns:
        {
            "score": float (-1.0 to +1.0),
            "label": "bullish" | "bearish" | "neutral",
            "confidence": float (0 to 1),
            "bullish_matches": [...],
            "bearish_matches": [...],
        }
    """
    if not text:
        return {"score": 0.0, "label": "neutral", "confidence": 0.0,
                "bullish_matches": [], "bearish_matches": []}

    text_lower = text.lower()
    words = text_lower.split()

    bullish_score = 0.0
    bearish_score = 0.0
    bullish_matches = []
    bearish_matches = []

    # Check multi-word phrases first (longer phrases take priority)
    for phrase, score in sorted(BULLISH_TERMS.items(), key=lambda x: -len(x[0])):
        if phrase in text_lower:
            # Check for negation (look at 2 words before the match)
            idx = text_lower.find(phrase)
            prefix = text_lower[max(0, idx - 20):idx]
            prefix_words = prefix.split()

            if any(w in NEGATION_WORDS for w in prefix_words[-2:]):
                bearish_score += score * 0.8
                bearish_matches.append(f"NOT {phrase}")
            else:
                # Check for intensifiers/diminishers
                modifier = 1.0
                for w in prefix_words[-2:]:
                    if w in INTENSIFIERS:
                        modifier = INTENSIFIERS[w]
                    elif w in DIMINISHERS:
                        modifier = DIMINISHERS[w]
                bullish_score += score * modifier
                bullish_matches.append(phrase)

    for phrase, score in sorted(BEARISH_TERMS.items(), key=lambda x: -len(x[0])):
        if phrase in text_lower:
            idx = text_lower.find(phrase)
            prefix = text_lower[max(0, idx - 20):idx]
            prefix_words = prefix.split()

            if any(w in NEGATION_WORDS for w in prefix_words[-2:]):
                bullish_score += score * 0.8
                bullish_matches.append(f"NOT {phrase}")
            else:
                modifier = 1.0
                for w in prefix_words[-2:]:
                    if w in INTENSIFIERS:
                        modifier = INTENSIFIERS[w]
                    elif w in DIMINISHERS:
                        modifier = DIMINISHERS[w]
                bearish_score += score * modifier
                bearish_matches.append(phrase)

    # Normalize
    total = bullish_score + bearish_score
    if total == 0:
        return {"score": 0.0, "label": "neutral", "confidence": 0.0,
                "bullish_matches": [], "bearish_matches": []}

    # Score: positive = bullish, negative = bearish
    raw_score = (bullish_score - bearish_score) / max(total, 1)
    confidence = min(1.0, total / 3.0)  # 3+ total term weight = full confidence

    if raw_score > 0.1:
        label = "bullish"
    elif raw_score < -0.1:
        label = "bearish"
    else:
        label = "neutral"

    return {
        "score": round(raw_score, 3),
        "label": label,
        "confidence": round(confidence, 2),
        "bullish_matches": bullish_matches[:5],
        "bearish_matches": bearish_matches[:5],
    }


def analyze_texts_batch(texts: list[str]) -> dict:
    """
    Analyze sentiment across multiple texts (e.g., all Reddit titles for a topic).

    Returns aggregated sentiment with breakdown.
    """
    if not texts:
        return {
            "avg_score": 0.0, "label": "neutral", "confidence": 0.0,
            "count": 0, "bullish_count": 0, "bearish_count": 0, "neutral_count": 0,
        }

    scores = []
    bullish_count = 0
    bearish_count = 0
    neutral_count = 0

    for text in texts:
        result = analyze_text_sentiment(text)
        scores.append(result["score"])
        if result["label"] == "bullish":
            bullish_count += 1
        elif result["label"] == "bearish":
            bearish_count += 1
        else:
            neutral_count += 1

    avg_score = sum(scores) / len(scores) if scores else 0.0
    confidence = min(1.0, len(texts) / 10.0)  # 10+ texts = full confidence

    if avg_score > 0.1:
        label = "bullish"
    elif avg_score < -0.1:
        label = "bearish"
    else:
        label = "neutral"

    return {
        "avg_score": round(avg_score, 3),
        "label": label,
        "confidence": round(confidence, 2),
        "count": len(texts),
        "bullish_count": bullish_count,
        "bearish_count": bearish_count,
        "neutral_count": neutral_count,
    }


def extract_ticker_sentiment(text: str, tickers: list[str]) -> dict[str, dict]:
    """
    Extract sentiment specifically tied to mentioned tickers.
    "NVDA crushed earnings but INTC disappointed" →
        NVDA: bullish, INTC: bearish
    """
    results = {}
    text_lower = text.lower()

    for ticker in tickers:
        ticker_upper = ticker.upper()
        ticker_lower = ticker.lower()

        # Find if ticker is mentioned
        if ticker_upper not in text and ticker_lower not in text_lower:
            continue

        # Get text window around ticker mention (±50 chars)
        idx = text.upper().find(ticker_upper)
        if idx == -1:
            continue

        window_start = max(0, idx - 50)
        window_end = min(len(text), idx + len(ticker) + 50)
        window = text[window_start:window_end]

        sentiment = analyze_text_sentiment(window)
        results[ticker_upper] = sentiment

    return results
