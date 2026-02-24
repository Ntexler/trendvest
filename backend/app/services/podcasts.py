"""
Podcast discovery & transcription service for TrendVest.
Discovers Israeli financial podcasts, transcribes episodes, and extracts insights.
"""
import os
import time
import json
import hashlib
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Optional

import requests

# Israeli financial podcast RSS feeds
PODCAST_FEEDS = {
    "hamaslul": {
        "name": "המסלול",
        "name_en": "HaMaslul",
        "description": "פודקאסט השקעות ופיננסים ישראלי",
        "rss": "https://feeds.megaphone.fm/hamaslul",
        "category": "finance",
    },
    "osim_cheshbon": {
        "name": "עושים חשבון",
        "name_en": "Osim Cheshbon",
        "description": "פודקאסט כלכלי של כלכליסט",
        "rss": "https://feeds.feedburner.com/osimheshbon",
        "category": "finance",
    },
    "geektime_podcast": {
        "name": "גיקטיים פודקאסט",
        "name_en": "Geektime Podcast",
        "description": "טכנולוגיה וסטארטאפים ישראליים",
        "rss": "https://feeds.feedburner.com/geektimepodcast",
        "category": "tech",
    },
    "two_cents": {
        "name": "הגרוש שלי",
        "name_en": "My Two Cents",
        "description": "פודקאסט על כסף וכלכלה",
        "rss": "https://feeds.megaphone.fm/ROOST5765883743",
        "category": "finance",
    },
}

# Cache for podcast episodes
_podcast_cache: dict[str, dict] = {}
CACHE_TTL = 1800  # 30 minutes


def _parse_podcast_feed(rss_url: str, podcast_key: str, podcast_name: str) -> list[dict]:
    """Parse a podcast RSS feed and return episode metadata."""
    try:
        resp = requests.get(rss_url, timeout=15, headers={
            "User-Agent": "TrendVest/1.0 (Podcast Aggregator)",
        })
        if resp.status_code != 200:
            return []

        root = ET.fromstring(resp.content)
        episodes = []

        for item in root.findall(".//item")[:10]:  # Latest 10 episodes
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            pub_date = item.findtext("pubDate", "")
            description = item.findtext("description", "").strip()

            # Get audio URL from enclosure
            enclosure = item.find("enclosure")
            audio_url = ""
            duration = ""
            if enclosure is not None:
                audio_url = enclosure.get("url", "")

            # Try itunes:duration
            itunes_duration = item.findtext("{http://www.itunes.com/dtds/podcast-1.0.dtd}duration", "")
            if itunes_duration:
                duration = itunes_duration

            # Try itunes:image
            image_url = ""
            itunes_image = item.find("{http://www.itunes.com/dtds/podcast-1.0.dtd}image")
            if itunes_image is not None:
                image_url = itunes_image.get("href", "")

            if not image_url:
                # Try channel-level itunes:image
                channel_image = root.find(".//{http://www.itunes.com/dtds/podcast-1.0.dtd}image")
                if channel_image is not None:
                    image_url = channel_image.get("href", "")

            if title:
                episodes.append({
                    "podcast_key": podcast_key,
                    "podcast_name": podcast_name,
                    "title": title,
                    "url": link or audio_url,
                    "audio_url": audio_url,
                    "published_at": pub_date,
                    "description": description[:300] if description else "",
                    "duration": duration,
                    "image_url": image_url,
                })

        return episodes
    except Exception as e:
        print(f"Podcast RSS error ({podcast_key}): {e}")
        return []


def get_podcast_episodes(
    podcast: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """
    Get recent podcast episodes.

    Args:
        podcast: Filter by specific podcast key
        category: Filter by category (finance, tech)
        limit: Max episodes to return
    """
    cache_key = f"pods:{podcast or 'all'}:{category or 'all'}:{limit}"
    now = time.time()

    if cache_key in _podcast_cache:
        cached = _podcast_cache[cache_key]
        if now - cached["time"] < CACHE_TTL:
            return cached["data"]

    feeds_to_fetch = []
    for key, config in PODCAST_FEEDS.items():
        if podcast and key != podcast:
            continue
        if category and config["category"] != category:
            continue
        feeds_to_fetch.append((config["rss"], key, config["name"]))

    all_episodes = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(_parse_podcast_feed, rss, key, name): key
            for rss, key, name in feeds_to_fetch
        }
        for future in as_completed(futures):
            try:
                all_episodes.extend(future.result())
            except Exception:
                pass

    # Sort by published_at (newest first)
    all_episodes.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    result = all_episodes[:limit]

    _podcast_cache[cache_key] = {"time": now, "data": result}
    return result


async def transcribe_episode(audio_url: str, language: str = "he") -> Optional[dict]:
    """
    Transcribe a podcast episode using OpenAI Whisper API or local whisper.

    Returns:
        {
            "text": "full transcription...",
            "segments": [{"start": 0.0, "end": 5.2, "text": "..."}],
            "language": "he"
        }
    """
    api_key = os.getenv("OPENAI_API_KEY", "")

    if not api_key:
        return None

    try:
        # Download audio to temp file (max 25MB for Whisper API)
        resp = requests.get(audio_url, timeout=60, stream=True)
        if resp.status_code != 200:
            return None

        # Check content length
        content_length = int(resp.headers.get("content-length", 0))
        if content_length > 25 * 1024 * 1024:
            print(f"Audio too large for Whisper API: {content_length} bytes")
            return None

        audio_data = resp.content

        # Call OpenAI Whisper API
        whisper_resp = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": ("episode.mp3", audio_data, "audio/mpeg")},
            data={
                "model": "whisper-1",
                "language": language,
                "response_format": "verbose_json",
            },
            timeout=300,
        )

        if whisper_resp.status_code != 200:
            print(f"Whisper API error: {whisper_resp.status_code}")
            return None

        result = whisper_resp.json()
        return {
            "text": result.get("text", ""),
            "segments": result.get("segments", []),
            "language": result.get("language", language),
        }
    except Exception as e:
        print(f"Transcription error: {e}")
        return None


async def analyze_transcript(transcript_text: str, language: str = "he") -> Optional[dict]:
    """
    Analyze a podcast transcript using Anthropic API to extract financial insights.

    Returns:
        {
            "summary": "...",
            "key_topics": ["AI stocks", "Inflation"],
            "mentioned_stocks": ["NVDA", "AAPL"],
            "sentiment": "bullish",
            "key_quotes": ["..."]
        }
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or not transcript_text:
        return None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        prompt = f"""Analyze this financial podcast transcript and extract:
1. A brief summary (2-3 sentences)
2. Key topics discussed (list)
3. Any stock tickers mentioned
4. Overall market sentiment (bullish/bearish/neutral)
5. Key quotes worth highlighting (2-3 max)

Respond in {"Hebrew" if language == "he" else "English"}.
Respond in valid JSON format.

Transcript:
{transcript_text[:8000]}"""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text
        # Try to parse as JSON
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            return {"summary": response_text, "key_topics": [], "mentioned_stocks": [], "sentiment": "neutral", "key_quotes": []}
    except Exception as e:
        print(f"Transcript analysis error: {e}")
        return None
