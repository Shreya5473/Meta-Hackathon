"""NLP pipeline: classification, sentiment, severity, clustering, entity extraction.

Uses:
- zero-shot NLI (DistilRoBERTa) for multi-category classification
- VADER for fast sentiment
- sentence-transformers + HDBSCAN for event clustering
- spaCy for entity extraction with expanded categories
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import numpy as np

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Expanded classification labels ────────────────────────────────────────────
# Maps to the event categories used by the signal generator

CLASSIFICATION_LABELS = [
    "military escalation",
    "sanctions",
    "trade restrictions",
    "energy supply disruption",
    "cyber attack",
    "political instability",
    "economic policy change",
    "diplomatic breakdown",
    "territorial dispute",
    "nuclear threat",
    "normal",
]

# Simplified 3-class labels for fast classification fallback
CLASSIFICATION_LABELS_SIMPLE = ["normal", "tension", "escalation"]

# Geo-region keywords (expanded)
_GEO_KEYWORDS: dict[str, list[str]] = {
    "middle_east": [
        "israel", "iran", "saudi", "gaza", "lebanon", "syria", "iraq", "yemen",
        "houthi", "hezbollah", "hamas", "hormuz", "qatar", "uae", "dubai",
        "bahrain", "oman", "jordan", "suez",
    ],
    "europe": [
        "russia", "ukraine", "nato", "eu", "european", "poland", "germany",
        "france", "uk", "britain", "kremlin", "moscow", "crimea", "baltics",
        "finland", "sweden", "norway", "denmark", "netherlands", "belgium",
        "spain", "italy", "greece", "turkey", "balkans",
    ],
    "asia_pacific": [
        "china", "taiwan", "korea", "japan", "india", "pakistan", "xi jinping",
        "beijing", "south china sea", "asean", "australia", "new zealand",
        "philippines", "vietnam", "indonesia", "malaysia", "singapore",
        "kashmir", "tibet", "hong kong", "pyongyang",
    ],
    "americas": [
        "us", "usa", "america", "brazil", "mexico", "venezuela", "colombia",
        "argentina", "canada", "pentagon", "white house", "congress",
        "fed", "federal reserve", "cuba", "chile", "peru",
    ],
    "africa": [
        "africa", "nigeria", "ethiopia", "congo", "sahel", "sudan",
        "libya", "egypt", "south africa", "kenya", "somalia",
        "mozambique", "niger", "mali", "boko haram", "al-shabaab",
    ],
}

# ── Commodity keywords for exposure detection ─────────────────────────────────
_COMMODITY_KEYWORDS: dict[str, list[str]] = {
    "crude_oil": ["oil", "crude", "brent", "wti", "opec", "petroleum", "barrel"],
    "natural_gas": ["natural gas", "gas", "lng", "pipeline", "nord stream"],
    "gold": ["gold", "bullion", "precious metal", "safe haven"],
    "wheat": ["wheat", "grain", "cereal", "food supply"],
    "copper": ["copper", "base metal"],
    "uranium": ["uranium", "nuclear fuel"],
    "semiconductors": ["semiconductor", "chip", "microchip", "foundry", "tsmc"],
    "rare_earths": ["rare earth", "lithium", "cobalt", "critical mineral"],
}

# ── Sector keywords ──────────────────────────────────────────────────────────
_SECTOR_KEYWORDS: dict[str, list[str]] = {
    "energy": ["oil", "gas", "energy", "solar", "wind", "nuclear", "pipeline", "refinery"],
    "defense": ["military", "defense", "weapon", "missile", "drone", "army", "navy", "air force"],
    "technology": ["tech", "semiconductor", "ai", "cyber", "software", "hardware", "cloud"],
    "financials": ["bank", "financial", "credit", "debt", "bond", "treasury", "forex"],
    "healthcare": ["pharma", "health", "vaccine", "pandemic", "medical"],
    "transportation": ["airline", "shipping", "logistics", "port", "freight"],
    "agriculture": ["wheat", "corn", "soybean", "crop", "harvest", "famine", "food"],
}


@dataclass
class NLPResult:
    classification: str
    classification_detail: str  # expanded category
    sentiment_score: float
    severity_score: float
    entities: list[str]
    geo_risk_vector: dict[str, float]
    commodity_exposure: list[str]
    sector_exposure: list[str]
    embedding: list[float]


class NLPPipeline:
    """Lazy-loaded NLP pipeline to avoid startup cost when not needed."""

    def __init__(self) -> None:
        self._classifier: Any = None
        self._sentiment: Any = None
        self._embedder: Any = None
        self._nlp: Any = None

    def _get_classifier(self) -> Any:
        if self._classifier is None:
            from transformers import pipeline
            settings = get_settings()
            logger.info("loading_nli_classifier", model=settings.nlp_model_name)
            self._classifier = pipeline(
                "zero-shot-classification",
                model=settings.nlp_model_name,
                device=-1,  # CPU; swap to 0 for GPU
            )
        return self._classifier

    def _get_sentiment(self) -> Any:
        if self._sentiment is None:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
            self._sentiment = SentimentIntensityAnalyzer()
        return self._sentiment

    def _get_embedder(self) -> Any:
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer
            settings = get_settings()
            logger.info("loading_sentence_transformer", model=settings.sentence_transformer_model)
            self._embedder = SentenceTransformer(settings.sentence_transformer_model)
        return self._embedder

    def _get_spacy(self) -> Any:
        if self._nlp is None:
            import spacy
            settings = get_settings()
            self._nlp = spacy.load(settings.spacy_model)
        return self._nlp

    def classify(self, text: str) -> tuple[str, float]:
        """Returns (label, confidence_score) using simple 3-class labels."""
        clf = self._get_classifier()
        result = clf(text, CLASSIFICATION_LABELS_SIMPLE, multi_label=False)
        label = result["labels"][0]
        score = float(result["scores"][0])
        return label, score

    def classify_detailed(self, text: str) -> tuple[str, float]:
        """Returns (detailed_label, confidence_score) using expanded categories."""
        clf = self._get_classifier()
        result = clf(text, CLASSIFICATION_LABELS, multi_label=False)
        label: str = result["labels"][0]
        score = float(result["scores"][0])
        # Normalize label to underscore format
        return label.replace(" ", "_"), score

    def sentiment(self, text: str) -> float:
        """VADER compound score: -1 to 1."""
        analyzer = self._get_sentiment()
        return float(analyzer.polarity_scores(text)["compound"])

    def severity(self, classification: str, sentiment: float, confidence: float) -> float:
        """Heuristic severity: high escalation + negative sentiment → high severity."""
        class_weight = {
            "normal": 0.0,
            "tension": 0.4,
            "escalation": 0.85,
            "military_escalation": 0.90,
            "sanctions": 0.65,
            "trade_restrictions": 0.55,
            "energy_supply_disruption": 0.75,
            "cyber_attack": 0.70,
            "political_instability": 0.50,
            "economic_policy_change": 0.40,
            "diplomatic_breakdown": 0.60,
            "territorial_dispute": 0.80,
            "nuclear_threat": 0.95,
        }.get(classification, 0.2)
        sentiment_factor = max(0.0, -sentiment)  # negative sentiment → higher severity
        raw = 0.5 * class_weight + 0.3 * sentiment_factor + 0.2 * confidence
        return float(min(1.0, max(0.0, raw)))

    def extract_entities(self, text: str) -> list[str]:
        nlp = self._get_spacy()
        doc = nlp(text[:512])  # cap for speed
        return list(
            {
                ent.text
                for ent in doc.ents
                if ent.label_ in {"GPE", "ORG", "PERSON", "NORP", "FAC", "LOC", "EVENT"}
            }
        )

    def geo_risk_vector(self, text: str, entities: list[str]) -> dict[str, float]:
        """Map text to regional risk weights based on keyword presence."""
        lower = (text + " " + " ".join(entities)).lower()
        vector: dict[str, float] = {}
        for region, keywords in _GEO_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in lower)
            if matches > 0:
                vector[region] = min(1.0, matches * 0.20)
        return vector or {"global": 1.0}

    def commodity_exposure(self, text: str, entities: list[str]) -> list[str]:
        """Detect commodity exposures from text."""
        lower = (text + " " + " ".join(entities)).lower()
        exposed = []
        for commodity, keywords in _COMMODITY_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                exposed.append(commodity)
        return exposed

    def sector_exposure(self, text: str, entities: list[str]) -> list[str]:
        """Detect sector exposures from text."""
        lower = (text + " " + " ".join(entities)).lower()
        exposed = []
        for sector, keywords in _SECTOR_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                exposed.append(sector)
        return exposed

    def embed(self, text: str) -> list[float]:
        embedder = self._get_embedder()
        return embedder.encode(text[:512], normalize_embeddings=True).tolist()

    def process(self, title: str, body: str | None = None) -> NLPResult:
        text = title if not body else f"{title}. {body[:256]}"
        label, confidence = self.classify(text)
        detail_label, _ = self.classify_detailed(text)
        sent = self.sentiment(text)
        sev = self.severity(detail_label or label, sent, confidence)
        entities = self.extract_entities(text)
        geo = self.geo_risk_vector(text, entities)
        commodities = self.commodity_exposure(text, entities)
        sectors = self.sector_exposure(text, entities)
        emb = self.embed(text)
        return NLPResult(
            classification=label,
            classification_detail=detail_label,
            sentiment_score=sent,
            severity_score=sev,
            entities=entities,
            geo_risk_vector=geo,
            commodity_exposure=commodities,
            sector_exposure=sectors,
            embedding=emb,
        )


class EventClusterer:
    """HDBSCAN clustering of event embeddings."""

    def __init__(self, min_cluster_size: int = 3) -> None:
        self.min_cluster_size = min_cluster_size
        self._model: Any = None

    def _get_model(self) -> Any:
        if self._model is None:
            import hdbscan
            self._model = hdbscan.HDBSCAN(
                min_cluster_size=self.min_cluster_size,
                metric="euclidean",
                prediction_data=True,
            )
        return self._model

    def cluster(self, embeddings: list[list[float]]) -> list[int]:
        """Return cluster label array (−1 = noise/unclustered)."""
        if len(embeddings) < self.min_cluster_size:
            return [-1] * len(embeddings)
        arr = np.array(embeddings, dtype=np.float32)
        model = self._get_model()
        labels: list[int] = model.fit_predict(arr).tolist()
        return labels


# Module-level singletons (lazy-loaded)
_nlp_pipeline: NLPPipeline | None = None
_clusterer: EventClusterer | None = None


def get_nlp_pipeline() -> NLPPipeline:
    global _nlp_pipeline  # noqa: PLW0603
    if _nlp_pipeline is None:
        _nlp_pipeline = NLPPipeline()
    return _nlp_pipeline


def get_clusterer() -> EventClusterer:
    global _clusterer  # noqa: PLW0603
    if _clusterer is None:
        _clusterer = EventClusterer()
    return _clusterer
