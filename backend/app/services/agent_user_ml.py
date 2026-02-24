"""
User Behavior ML Model for TrendVest AI Agent.

REAL machine learning (scikit-learn) that learns from user interaction patterns
and predicts whether a topic/ticker will see a price increase.

Architecture:
  1. FEATURE EXTRACTION: For each topic, extract behavioral features from
     the user_interactions table (click velocity, intent depth, timing, etc.)
  2. LABEL GENERATION: Check what actually happened to the price 7 days later
  3. TRAINING: Logistic Regression (small data) → Gradient Boosting (>200 samples)
  4. PREDICTION: Given current behavior patterns, predict P(price_up_7d)
  5. RETRAINING: Weekly retrain on new data

Features extracted per topic per week:
  - click_velocity_24h:    interactions in last 24h
  - click_acceleration:    24h count / 7d daily average (spike detection)
  - high_intent_ratio:     % of high-intent actions (watchlist, stock_click, chat)
  - unique_sessions_24h:   distinct session IDs in 24h (breadth of interest)
  - peak_hour:             hour of day with most activity (0-23)
  - weekend_activity:      % of interactions on weekends
  - return_session_ratio:  % of sessions with >1 interaction (conviction)
  - momentum_score:        from momentum_scores table
  - momentum_direction:    encoded as 1=rising, 0=stable, -1=falling
  - avg_session_depth:     avg interactions per session on this topic

Target:
  - 1 if the topic's top ticker rose ≥2% in the next 7 days
  - 0 otherwise

Model selection:
  - <50 samples:   No prediction (insufficient data)
  - 50-200:        LogisticRegression (robust with small data)
  - >200:          GradientBoostingClassifier (captures nonlinear patterns)

Storage:
  - Model saved to DB as pickled bytes (agent_ml_models table)
  - Features and predictions logged for audit

HONEST NOTE:
  This IS real ML, but it's limited by data volume. With <200 samples,
  don't expect miracles. The real power comes after months of user data.
  Treat early predictions as supplementary, not primary signals.
"""

from __future__ import annotations

import io
import json
import logging
import pickle
from datetime import datetime, timezone, timedelta
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Feature names in order — must match extraction and training
FEATURE_NAMES = [
    "click_velocity_24h",
    "click_acceleration",
    "high_intent_ratio",
    "unique_sessions_24h",
    "peak_hour",
    "weekend_ratio",
    "return_session_ratio",
    "momentum_score",
    "momentum_direction",
    "avg_session_depth",
]

# Minimum samples needed for each model type
MIN_SAMPLES_LOGISTIC = 50
MIN_SAMPLES_BOOSTING = 200

MODEL_KEY = "user_behavior_v1"


class UserBehaviorML:
    """
    ML model that learns user behavior patterns and predicts price movements.

    Usage:
        ml = UserBehaviorML(pool, stock_service)
        await ml.load_model()

        # Predict for a topic
        prediction = await ml.predict("artificial_intelligence")

        # Retrain on new data
        stats = await ml.retrain()
    """

    def __init__(self, pool, stock_service):
        self.pool = pool
        self.stock_service = stock_service
        self.model = None
        self.model_type = None  # "logistic" or "boosting"
        self.scaler = None
        self.training_stats = None

    # ──────────────────────────────────────
    # FEATURE EXTRACTION
    # ──────────────────────────────────────

    async def extract_features(self, topic_slug: str, as_of: Optional[datetime] = None) -> Optional[dict]:
        """
        Extract behavioral features for a topic at a given point in time.

        Returns dict with feature values + metadata, or None if insufficient data.
        """
        if as_of is None:
            as_of = datetime.now(timezone.utc)

        day_ago = as_of - timedelta(hours=24)
        week_ago = as_of - timedelta(days=7)

        async with self.pool.acquire() as conn:
            # ── Interaction counts ──
            count_24h = await conn.fetchval("""
                SELECT COUNT(*) FROM user_interactions
                WHERE target_slug = $1 AND created_at >= $2 AND created_at <= $3
            """, topic_slug, day_ago, as_of) or 0

            count_7d = await conn.fetchval("""
                SELECT COUNT(*) FROM user_interactions
                WHERE target_slug = $1 AND created_at >= $2 AND created_at <= $3
            """, topic_slug, week_ago, as_of) or 0

            if count_7d < 3:
                return None  # Not enough data for this topic

            # ── High intent actions ──
            high_intent_24h = await conn.fetchval("""
                SELECT COUNT(*) FROM user_interactions
                WHERE target_slug = $1
                  AND created_at >= $2 AND created_at <= $3
                  AND interaction_type IN ('watchlist_add', 'stock_click', 'chat_ask')
            """, topic_slug, day_ago, as_of) or 0

            # ── Unique sessions in 24h ──
            unique_sessions = await conn.fetchval("""
                SELECT COUNT(DISTINCT session_id) FROM user_interactions
                WHERE target_slug = $1
                  AND created_at >= $2 AND created_at <= $3
                  AND session_id IS NOT NULL
            """, topic_slug, day_ago, as_of) or 0

            # ── Peak hour ──
            peak_hour_row = await conn.fetchrow("""
                SELECT EXTRACT(HOUR FROM created_at)::int AS hr, COUNT(*) AS cnt
                FROM user_interactions
                WHERE target_slug = $1 AND created_at >= $2 AND created_at <= $3
                GROUP BY hr ORDER BY cnt DESC LIMIT 1
            """, topic_slug, week_ago, as_of)
            peak_hour = peak_hour_row["hr"] if peak_hour_row else 12

            # ── Weekend ratio ──
            weekend_count = await conn.fetchval("""
                SELECT COUNT(*) FROM user_interactions
                WHERE target_slug = $1
                  AND created_at >= $2 AND created_at <= $3
                  AND EXTRACT(DOW FROM created_at) IN (0, 6)
            """, topic_slug, week_ago, as_of) or 0

            # ── Return session ratio (sessions with >1 interaction) ──
            session_data = await conn.fetch("""
                SELECT session_id, COUNT(*) AS cnt
                FROM user_interactions
                WHERE target_slug = $1
                  AND created_at >= $2 AND created_at <= $3
                  AND session_id IS NOT NULL
                GROUP BY session_id
            """, topic_slug, week_ago, as_of)

            total_sessions = len(session_data) if session_data else 1
            return_sessions = sum(1 for s in session_data if s["cnt"] > 1) if session_data else 0
            avg_depth = np.mean([s["cnt"] for s in session_data]) if session_data else 0

            # ── Momentum data ──
            momentum_row = await conn.fetchrow("""
                SELECT m.score, m.direction
                FROM momentum_scores m
                JOIN topics t ON t.id = m.topic_id
                WHERE t.slug = $1
            """, topic_slug)

        # ── Calculate features ──
        daily_avg_7d = count_7d / 7 if count_7d > 0 else 0.1
        click_acceleration = count_24h / daily_avg_7d if daily_avg_7d > 0 else 0
        high_intent_ratio = high_intent_24h / max(count_24h, 1)
        weekend_ratio = weekend_count / max(count_7d, 1)
        return_ratio = return_sessions / max(total_sessions, 1)

        momentum_score = momentum_row["score"] if momentum_row else 100
        direction_map = {"rising": 1, "stable": 0, "falling": -1}
        momentum_dir = direction_map.get(momentum_row["direction"], 0) if momentum_row else 0

        features = {
            "click_velocity_24h": count_24h,
            "click_acceleration": round(click_acceleration, 3),
            "high_intent_ratio": round(high_intent_ratio, 3),
            "unique_sessions_24h": unique_sessions,
            "peak_hour": peak_hour,
            "weekend_ratio": round(weekend_ratio, 3),
            "return_session_ratio": round(return_ratio, 3),
            "momentum_score": momentum_score,
            "momentum_direction": momentum_dir,
            "avg_session_depth": round(float(avg_depth), 2),
        }

        return {
            "topic_slug": topic_slug,
            "features": features,
            "feature_vector": [features[name] for name in FEATURE_NAMES],
            "as_of": as_of.isoformat(),
        }

    # ──────────────────────────────────────
    # LABEL GENERATION
    # ──────────────────────────────────────

    async def _get_price_outcome(self, topic_slug: str, as_of: datetime, days_forward: int = 7) -> Optional[int]:
        """
        Check what happened to the top ticker's price after `as_of`.
        Returns 1 if rose ≥2%, 0 otherwise, None if no data.
        """
        async with self.pool.acquire() as conn:
            top_ticker = await conn.fetchval("""
                SELECT ts.ticker FROM topic_stocks ts
                JOIN topics t ON t.id = ts.topic_id
                WHERE t.slug = $1
                ORDER BY ts.priority ASC LIMIT 1
            """, topic_slug)

        if not top_ticker:
            return None

        try:
            import yfinance as yf
            stock = yf.Ticker(top_ticker)
            start_date = as_of.strftime("%Y-%m-%d")
            end_date = (as_of + timedelta(days=days_forward + 2)).strftime("%Y-%m-%d")
            hist = stock.history(start=start_date, end=end_date)

            if hist is None or len(hist) < 2:
                return None

            start_price = hist["Close"].iloc[0]
            # Get price closest to N days forward
            end_idx = min(days_forward, len(hist) - 1)
            end_price = hist["Close"].iloc[end_idx]

            change_pct = (end_price / start_price - 1) * 100
            return 1 if change_pct >= 2.0 else 0

        except Exception as e:
            logger.debug("Price outcome check failed for %s: %s", top_ticker, e)
            return None

    # ──────────────────────────────────────
    # TRAINING DATA COLLECTION
    # ──────────────────────────────────────

    async def _collect_training_data(self, weeks_back: int = 12) -> tuple[list, list]:
        """
        Collect training data by looking at past weekly snapshots.

        For each week going back N weeks:
          - Extract features as of that date
          - Check price outcome 7 days later
          - Build (X, y) dataset
        """
        X, y = [], []
        now = datetime.now(timezone.utc)

        async with self.pool.acquire() as conn:
            # Get all topic slugs that have interactions
            slugs = await conn.fetch("""
                SELECT DISTINCT target_slug FROM user_interactions
                WHERE created_at >= NOW() - INTERVAL '%s weeks'
                  AND target_slug IS NOT NULL
            """ % weeks_back)

        topic_slugs = [r["target_slug"] for r in slugs if r["target_slug"]]

        for week_offset in range(1, weeks_back + 1):
            snapshot_date = now - timedelta(weeks=week_offset)

            for slug in topic_slugs:
                try:
                    # Extract features as of that date
                    feat = await self.extract_features(slug, as_of=snapshot_date)
                    if not feat:
                        continue

                    # Get the actual price outcome
                    label = await self._get_price_outcome(slug, snapshot_date, days_forward=7)
                    if label is None:
                        continue

                    X.append(feat["feature_vector"])
                    y.append(label)

                except Exception as e:
                    logger.debug("Training data collection failed for %s week-%d: %s", slug, week_offset, e)
                    continue

        return X, y

    # ──────────────────────────────────────
    # MODEL TRAINING
    # ──────────────────────────────────────

    async def retrain(self, weeks_back: int = 12) -> dict:
        """
        Retrain the ML model on historical user behavior data.

        Returns training statistics.
        """
        logger.info("Starting user behavior ML retrain (looking back %d weeks)...", weeks_back)

        X_raw, y_raw = await self._collect_training_data(weeks_back)

        n_samples = len(X_raw)
        if n_samples < MIN_SAMPLES_LOGISTIC:
            return {
                "status": "insufficient_data",
                "samples": n_samples,
                "required": MIN_SAMPLES_LOGISTIC,
                "message": f"Need at least {MIN_SAMPLES_LOGISTIC} samples, have {n_samples}",
            }

        X = np.array(X_raw, dtype=float)
        y = np.array(y_raw, dtype=int)

        # Check class balance
        pos_count = int(y.sum())
        neg_count = n_samples - pos_count
        if pos_count < 5 or neg_count < 5:
            return {
                "status": "class_imbalance",
                "samples": n_samples,
                "positive": pos_count,
                "negative": neg_count,
                "message": "Need at least 5 positive and 5 negative examples",
            }

        from sklearn.preprocessing import StandardScaler
        from sklearn.model_selection import cross_val_score

        # Scale features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Select model based on data size
        if n_samples >= MIN_SAMPLES_BOOSTING:
            from sklearn.ensemble import GradientBoostingClassifier
            model = GradientBoostingClassifier(
                n_estimators=100,
                max_depth=3,
                learning_rate=0.1,
                min_samples_split=10,
                random_state=42,
            )
            model_type = "boosting"
        else:
            from sklearn.linear_model import LogisticRegression
            model = LogisticRegression(
                C=1.0,
                max_iter=1000,
                class_weight="balanced",
                random_state=42,
            )
            model_type = "logistic"

        # Cross-validate
        cv_folds = min(5, max(2, n_samples // 20))
        try:
            cv_scores = cross_val_score(model, X_scaled, y, cv=cv_folds, scoring="accuracy")
            cv_accuracy = float(cv_scores.mean())
            cv_std = float(cv_scores.std())
        except Exception:
            cv_accuracy = 0.0
            cv_std = 0.0

        # Train final model on all data
        model.fit(X_scaled, y)

        # Feature importance
        if hasattr(model, "feature_importances_"):
            importances = model.feature_importances_
        elif hasattr(model, "coef_"):
            importances = np.abs(model.coef_[0])
        else:
            importances = np.zeros(len(FEATURE_NAMES))

        feature_importance = {
            name: round(float(imp), 4)
            for name, imp in sorted(zip(FEATURE_NAMES, importances), key=lambda x: -x[1])
        }

        # Save model
        self.model = model
        self.scaler = scaler
        self.model_type = model_type

        stats = {
            "status": "trained",
            "model_type": model_type,
            "samples": n_samples,
            "positive_samples": pos_count,
            "negative_samples": neg_count,
            "cv_accuracy": round(cv_accuracy, 4),
            "cv_std": round(cv_std, 4),
            "feature_importance": feature_importance,
            "trained_at": datetime.now(timezone.utc).isoformat(),
        }
        self.training_stats = stats

        # Persist to DB
        await self._save_model_to_db(stats)

        logger.info(
            "ML model trained: type=%s samples=%d accuracy=%.1f%%",
            model_type, n_samples, cv_accuracy * 100,
        )

        return stats

    # ──────────────────────────────────────
    # PREDICTION
    # ──────────────────────────────────────

    async def predict(self, topic_slug: str) -> Optional[dict]:
        """
        Predict probability of price increase for a topic based on current user behavior.

        Returns:
          {
            "topic_slug": "ai_chips",
            "prediction": "bullish" | "bearish" | "neutral",
            "probability": 0.72,
            "confidence": 0.44,  # distance from 0.5
            "features": {...},
            "model_type": "logistic",
          }
        """
        if self.model is None:
            await self.load_model()

        if self.model is None:
            return None  # No trained model available

        feat = await self.extract_features(topic_slug)
        if not feat:
            return None

        try:
            X = np.array([feat["feature_vector"]], dtype=float)
            X_scaled = self.scaler.transform(X)

            proba = self.model.predict_proba(X_scaled)[0]
            # proba[1] = probability of price increase
            prob_up = float(proba[1]) if len(proba) > 1 else 0.5

            # Convert to signal
            confidence = abs(prob_up - 0.5) * 2  # 0 to 1
            if prob_up >= 0.6:
                prediction = "bullish"
            elif prob_up <= 0.4:
                prediction = "bearish"
            else:
                prediction = "neutral"

            return {
                "topic_slug": topic_slug,
                "prediction": prediction,
                "probability": round(prob_up, 4),
                "confidence": round(confidence, 4),
                "features": feat["features"],
                "model_type": self.model_type,
                "training_accuracy": self.training_stats.get("cv_accuracy") if self.training_stats else None,
            }

        except Exception as e:
            logger.warning("ML prediction failed for %s: %s", topic_slug, e)
            return None

    # ──────────────────────────────────────
    # MODEL PERSISTENCE
    # ──────────────────────────────────────

    async def _save_model_to_db(self, stats: dict):
        """Serialize model + scaler and save to DB."""
        try:
            model_bytes = pickle.dumps({
                "model": self.model,
                "scaler": self.scaler,
                "model_type": self.model_type,
                "stats": stats,
            })

            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO agent_ml_models (model_key, model_data, metadata, trained_at)
                    VALUES ($1, $2, $3, NOW())
                    ON CONFLICT (model_key) DO UPDATE SET
                        model_data = EXCLUDED.model_data,
                        metadata = EXCLUDED.metadata,
                        trained_at = NOW()
                """, MODEL_KEY, model_bytes, json.dumps(stats))

        except Exception as e:
            logger.warning("Failed to save ML model to DB: %s", e)

    async def load_model(self) -> bool:
        """Load model from DB if available."""
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT model_data, metadata FROM agent_ml_models WHERE model_key = $1",
                    MODEL_KEY,
                )

            if not row:
                return False

            data = pickle.loads(row["model_data"])
            self.model = data["model"]
            self.scaler = data["scaler"]
            self.model_type = data["model_type"]
            self.training_stats = data.get("stats")

            logger.info("Loaded ML model: %s", self.model_type)
            return True

        except Exception as e:
            logger.warning("Failed to load ML model: %s", e)
            return False

    async def get_model_info(self) -> dict:
        """Return info about the current model for the dashboard."""
        if self.model is None:
            await self.load_model()

        if self.model is None:
            return {
                "status": "not_trained",
                "message": "No ML model available yet. Need at least 50 data samples.",
            }

        return {
            "status": "ready",
            "model_type": self.model_type,
            "training_stats": self.training_stats,
        }
