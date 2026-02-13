"""
AI Explainer service for TrendVest.
Uses Claude Haiku to answer financial questions in simple Hebrew.
"""
import os
from datetime import datetime, timezone, date
from collections import defaultdict
from typing import Optional

try:
    import anthropic
except ImportError:
    anthropic = None
    print("⚠️  anthropic not installed. Run: pip install anthropic")


SYSTEM_PROMPT = """אתה העוזר הדיגיטלי של TrendVest — פלטפורמה ישראלית למעקב מגמות בשוק ההון.

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
- שימוש באימוג'ים ממוקד (לא יותר מדי)
- פסקאות קצרות
- דוגמאות מהחיים כשרלוונטי
"""

SUGGESTED_QUESTIONS_GENERAL = [
    "מה זה ETF?",
    "מה זה שווי שוק?",
    "איך שוק המניות עובד?",
    "מה זה דיבידנד?",
    "מה זה מדד S&P 500?",
    "מה ההבדל בין מניה לאגרת חוב?",
]

SUGGESTED_QUESTIONS_TOPIC = [
    "למה {topic} טרנדי עכשיו?",
    "אילו חברות קשורות ל{topic}?",
    "מה הסיכונים בסקטור {topic}?",
    "האם {topic} מגמה ארוכת טווח?",
]


class AIExplainer:
    """Handles AI-powered financial explanations in Hebrew."""

    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self._client = None
        self._daily_usage: dict[str, dict] = defaultdict(lambda: {"date": date.today(), "count": 0})
        self.free_daily_limit = 3

    @property
    def client(self):
        """Lazy init Anthropic client."""
        if self._client is None:
            if not anthropic:
                raise RuntimeError("anthropic package not installed")
            if not self.api_key:
                raise RuntimeError("ANTHROPIC_API_KEY not set")
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def check_rate_limit(self, user_id: str) -> tuple[bool, int]:
        """
        Check if user has remaining questions.

        Returns:
            (allowed: bool, remaining: int)
        """
        usage = self._daily_usage[user_id]
        if usage["date"] != date.today():
            usage["date"] = date.today()
            usage["count"] = 0

        remaining = max(0, self.free_daily_limit - usage["count"])
        return remaining > 0, remaining

    def record_usage(self, user_id: str):
        """Record that a user asked a question."""
        usage = self._daily_usage[user_id]
        if usage["date"] != date.today():
            usage["date"] = date.today()
            usage["count"] = 0
        usage["count"] += 1

    async def ask(self, question: str, context: str | None = None,
                  user_id: str = "anonymous") -> dict:
        """
        Ask the AI explainer a question.

        Args:
            question: User's question in Hebrew
            context: Optional topic slug for context
            user_id: User identifier for rate limiting

        Returns:
            Dict with 'answer', 'suggested_questions', 'questions_remaining'
        """
        # Check rate limit
        allowed, remaining = self.check_rate_limit(user_id)
        if not allowed:
            return {
                "answer": "הגעת למגבלת השאלות היומית (3 שאלות ביום בחינם). שדרג ל-Pro לשאלות ללא הגבלה! 🔒",
                "suggested_questions": [],
                "questions_remaining": 0,
            }

        # Build messages
        messages = []
        if context:
            messages.append({
                "role": "user",
                "content": f"הקשר: המשתמש צופה כרגע בנושא: {context}"
            })
            messages.append({
                "role": "assistant",
                "content": "הבנתי, אענה בהקשר של הנושא הזה."
            })

        messages.append({"role": "user", "content": question})

        try:
            response = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=500,
                system=SYSTEM_PROMPT,
                messages=messages,
            )
            answer = response.content[0].text

        except Exception as e:
            print(f"❌ Claude API error: {e}")
            answer = (
                "מצטער, נתקלתי בבעיה טכנית. 😔\n"
                "נסה שוב בעוד כמה שניות, או שאל שאלה אחרת."
            )

        # Record usage
        self.record_usage(user_id)
        _, remaining_after = self.check_rate_limit(user_id)

        # Generate suggested questions
        if context:
            suggestions = [q.format(topic=context) for q in SUGGESTED_QUESTIONS_TOPIC[:3]]
        else:
            import random
            suggestions = random.sample(SUGGESTED_QUESTIONS_GENERAL, min(3, len(SUGGESTED_QUESTIONS_GENERAL)))

        return {
            "answer": answer,
            "suggested_questions": suggestions,
            "questions_remaining": remaining_after,
        }
