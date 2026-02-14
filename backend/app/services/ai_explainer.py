"""
AI Explainer service for TrendVest.
Uses Claude to answer financial questions in Hebrew or English.
"""
import os
from datetime import datetime, timezone, date
from collections import defaultdict
from typing import Optional

try:
    import anthropic
except ImportError:
    anthropic = None

SYSTEM_PROMPT_HE = """אתה העוזר הדיגיטלי של TrendVest — פלטפורמה ישראלית למעקב מגמות בשוק ההון.

התפקיד שלך:
- להסביר מושגים פיננסיים בעברית פשוטה וברורה
- לעזור למתחילים להבין את שוק ההון
- להסביר למה נושאים מסוימים טרנדיים כרגע
- לענות על שאלות על מניות, סקטורים ומגמות

כללים קריטיים:
- לעולם לא לתת ייעוץ השקעות או תחזיות מחירים
- לעולם לא לומר "קנה" או "מכור" לגבי אף מניה
- תמיד להוסיף disclaimer כשמדברים על מניות ספציפיות
- לענות רק בעברית
- לשמור על תשובות קצרות — עד 200 מילים
- להשתמש בשפה פשוטה, להימנע מז'רגון מקצועי
- אם שואלים לייעוץ — להפנות לתוכן חינוכי

פורמט תשובה:
- תשובות קצרות וברורות
- פסקאות קצרות
- דוגמאות מהחיים כשרלוונטי
"""

SYSTEM_PROMPT_EN = """You are the digital assistant of TrendVest — a trend-tracking stock discovery platform.

Your role:
- Explain financial concepts in simple, clear English
- Help beginners understand the stock market
- Explain why certain topics are trending right now
- Answer questions about stocks, sectors, and trends

Critical rules:
- NEVER give investment advice or price predictions
- NEVER say "buy" or "sell" for any stock
- Always add a disclaimer when discussing specific stocks
- Keep answers short — under 200 words
- Use simple language, avoid professional jargon
- If asked for advice — redirect to educational content

Response format:
- Short, clear answers
- Short paragraphs
- Real-life examples when relevant
"""

SUGGESTED_QUESTIONS_HE = [
    "מה זה ETF?",
    "מה זה שווי שוק?",
    "איך שוק המניות עובד?",
    "מה זה דיבידנד?",
    "מה זה מדד S&P 500?",
    "מה ההבדל בין מניה לאגרת חוב?",
]

SUGGESTED_QUESTIONS_EN = [
    "What is an ETF?",
    "What is market cap?",
    "How does the stock market work?",
    "What is a dividend?",
    "What is the S&P 500 index?",
    "What's the difference between a stock and a bond?",
]

SUGGESTED_QUESTIONS_TOPIC_HE = [
    "למה {topic} טרנדי עכשיו?",
    "אילו חברות קשורות ל{topic}?",
    "מה הסיכונים בסקטור {topic}?",
    "האם {topic} מגמה ארוכת טווח?",
]

SUGGESTED_QUESTIONS_TOPIC_EN = [
    "Why is {topic} trending right now?",
    "Which companies are related to {topic}?",
    "What are the risks in the {topic} sector?",
    "Is {topic} a long-term trend?",
]

# Fallback responses when no API key
FALLBACK_HE = (
    "שירות ה-AI לא פעיל כרגע (חסר API key).\n\n"
    "בינתיים, הנה כמה טיפים:\n"
    "- עקוב אחרי הטרנדים בדשבורד\n"
    "- בדוק מניות בסקרינר\n"
    "- קרא חדשות בפיד החדשות\n\n"
    "השירות יהיה זמין ברגע שיוגדר API key."
)

FALLBACK_EN = (
    "AI service is currently unavailable (API key not configured).\n\n"
    "In the meantime, here are some tips:\n"
    "- Follow the trends on the dashboard\n"
    "- Check stocks in the screener\n"
    "- Read news in the news feed\n\n"
    "The service will be available once an API key is configured."
)


class AIExplainer:
    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self._client = None
        self._daily_usage: dict[str, dict] = defaultdict(lambda: {"date": date.today(), "count": 0})
        self.free_daily_limit = 3
        self._cache: dict[str, str] = {}

    @property
    def client(self):
        if self._client is None:
            if not anthropic:
                return None
            if not self.api_key:
                return None
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def check_rate_limit(self, user_id: str) -> tuple[bool, int]:
        usage = self._daily_usage[user_id]
        if usage["date"] != date.today():
            usage["date"] = date.today()
            usage["count"] = 0
        remaining = max(0, self.free_daily_limit - usage["count"])
        return remaining > 0, remaining

    def record_usage(self, user_id: str):
        usage = self._daily_usage[user_id]
        if usage["date"] != date.today():
            usage["date"] = date.today()
            usage["count"] = 0
        usage["count"] += 1

    async def ask(self, question: str, context: str | None = None,
                  user_id: str = "anonymous", language: str = "he") -> dict:
        allowed, remaining = self.check_rate_limit(user_id)
        if not allowed:
            msg = ("הגעת למגבלת השאלות היומית (3 שאלות ביום בחינם)."
                   if language == "he"
                   else "You've reached the daily question limit (3 questions/day free).")
            return {
                "answer": msg,
                "suggested_questions": [],
                "questions_remaining": 0,
            }

        # Select language-specific content
        system_prompt = SYSTEM_PROMPT_HE if language == "he" else SYSTEM_PROMPT_EN
        general_suggestions = SUGGESTED_QUESTIONS_HE if language == "he" else SUGGESTED_QUESTIONS_EN
        topic_suggestions = SUGGESTED_QUESTIONS_TOPIC_HE if language == "he" else SUGGESTED_QUESTIONS_TOPIC_EN

        # Graceful fallback when no API key
        if self.client is None:
            self.record_usage(user_id)
            _, remaining_after = self.check_rate_limit(user_id)
            fallback = FALLBACK_HE if language == "he" else FALLBACK_EN
            return {
                "answer": fallback,
                "suggested_questions": general_suggestions[:3],
                "questions_remaining": remaining_after,
            }

        # Build messages
        messages = []
        if context:
            ctx_msg = (f"הקשר: המשתמש צופה כרגע בנושא: {context}"
                       if language == "he"
                       else f"Context: The user is currently viewing the topic: {context}")
            ack_msg = ("הבנתי, אענה בהקשר של הנושא הזה."
                       if language == "he"
                       else "Got it, I'll answer in the context of this topic.")
            messages.append({"role": "user", "content": ctx_msg})
            messages.append({"role": "assistant", "content": ack_msg})

        messages.append({"role": "user", "content": question})

        try:
            response = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=500,
                system=system_prompt,
                messages=messages,
            )
            answer = response.content[0].text
        except Exception as e:
            print(f"Claude API error: {e}")
            answer = (
                "מצטער, נתקלתי בבעיה טכנית. נסה שוב בעוד כמה שניות."
                if language == "he"
                else "Sorry, I encountered a technical issue. Please try again in a few seconds."
            )

        self.record_usage(user_id)
        _, remaining_after = self.check_rate_limit(user_id)

        if context:
            suggestions = [q.format(topic=context) for q in topic_suggestions[:3]]
        else:
            import random
            suggestions = random.sample(general_suggestions, min(3, len(general_suggestions)))

        return {
            "answer": answer,
            "suggested_questions": suggestions,
            "questions_remaining": remaining_after,
        }

    async def translate_text(self, text: str, target_language: str, ticker: str) -> str:
        """Translate text (e.g. company summary) to target language."""
        if target_language != "he":
            return text
        cache_key = f"translate:{ticker}:{target_language}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        if self.client is None:
            return text
        try:
            response = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=800,
                system="You are a professional translator. Translate the given company description to Hebrew. Output ONLY the translation, nothing else.",
                messages=[{"role": "user", "content": text}],
            )
            translated = response.content[0].text
            self._cache[cache_key] = translated
            return translated
        except Exception as e:
            print(f"Translation error: {e}")
            return text

    async def explain_term(self, term: str, language: str = "he") -> str:
        """Return a 1-2 sentence definition of a financial term."""
        cache_key = f"term:{term.lower()}:{language}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        if self.client is None:
            return term
        lang_instruction = "Answer in Hebrew." if language == "he" else "Answer in English."
        try:
            response = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                system=f"You are a financial education assistant. {lang_instruction} Give a concise 1-2 sentence definition. No disclaimers needed.",
                messages=[{"role": "user", "content": f"Define: {term}"}],
            )
            explanation = response.content[0].text
            self._cache[cache_key] = explanation
            return explanation
        except Exception as e:
            print(f"Explain term error: {e}")
            return term

    async def explain_section(self, ticker: str, section: str, data: dict, language: str = "he") -> str:
        """Return a contextual AI summary of a stock's financial section with actual numbers."""
        cache_key = f"section:{ticker}:{section}:{language}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        if self.client is None:
            fallback = "AI service unavailable." if language == "en" else "שירות ה-AI לא זמין כרגע."
            return fallback
        lang_instruction = "Answer in Hebrew." if language == "he" else "Answer in English."
        data_str = "\n".join(f"- {k}: {v}" for k, v in data.items() if v is not None)
        try:
            response = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=400,
                system=(
                    f"You are a financial education assistant. {lang_instruction} "
                    "Summarize the data in 2-3 sentences for a beginner investor. "
                    "Do NOT give investment advice. Educational only."
                ),
                messages=[{"role": "user", "content": f"Explain {ticker}'s {section} data:\n{data_str}"}],
            )
            explanation = response.content[0].text
            self._cache[cache_key] = explanation
            return explanation
        except Exception as e:
            print(f"Explain section error: {e}")
            fallback = "Could not generate explanation." if language == "en" else "לא ניתן ליצור הסבר."
            return fallback

    async def generate_officer_bio(self, name: str, title: str, company: str, language: str = "en") -> str:
        """Generate a 1-2 sentence professional bio for a company officer."""
        cache_key = f"bio:{name}:{company}:{language}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        if self.client is None:
            return ""
        lang_instruction = "Answer in Hebrew." if language == "he" else "Answer in English."
        try:
            response = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=150,
                system=(
                    f"You are a professional bio writer. {lang_instruction} "
                    "Write a concise 1-2 sentence professional summary. "
                    "Focus on their role and what they oversee. No speculation."
                ),
                messages=[{"role": "user", "content": f"Write a short bio for {name}, {title} at {company}."}],
            )
            bio = response.content[0].text
            self._cache[cache_key] = bio
            return bio
        except Exception as e:
            print(f"Officer bio error: {e}")
            return ""
