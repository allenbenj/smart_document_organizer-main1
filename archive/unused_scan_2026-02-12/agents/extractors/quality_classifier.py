from typing import Any, Callable, Dict, List, Optional

import numpy as np  # noqa: E402
from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402


class QualityClassifier:
    """Lightweight classifier estimating extraction error probability."""

    def __init__(self) -> None:
        self.vectorizer = TfidfVectorizer(max_features=500)
        self.model = LogisticRegression(max_iter=200)
        self.is_trained = False

    def train(self, items: List[Dict[str, Any]], labels: List[int]) -> None:
        texts = [f"{i['item_type']} {i.get('text_context', '')}" for i in items]
        Xtext = self.vectorizer.fit_transform(texts)
        conf = np.array([[i.get("confidence", 0.0)] for i in items])
        X = np.hstack([Xtext.toarray(), conf])
        self.model.fit(X, labels)
        self.is_trained = True

    def predict_error_probability(self, item: Dict[str, Any]) -> float:
        if not self.is_trained:
            return 0.0
        text = [f"{item['item_type']} {item.get('text_context', '')}"]
        Xtext = self.vectorizer.transform(text)
        conf = np.array([[item.get("confidence", 0.0)]])
        X = np.hstack([Xtext.toarray(), conf])
        return float(self.model.predict_proba(X)[0][1])

    def evaluate(self, items: List[Dict[str, Any]], labels: List[int]) -> float:
        if not self.is_trained or not items:
            return 0.0
        texts = [f"{i['item_type']} {i.get('text_context', '')}" for i in items]
        Xtext = self.vectorizer.transform(texts)
        conf = np.array([[i.get("confidence", 0.0)] for i in items])
        X = np.hstack([Xtext.toarray(), conf])
        return float(self.model.score(X, labels))


class QualityModelMonitor:
    """Simple drift detector monitoring validation accuracy."""

    def __init__(
        self,
        classifier: QualityClassifier,
        threshold: float = 0.8,
        alert_cb: Optional[Callable[[float], None]] = None,
    ) -> None:
        self.classifier = classifier
        self.threshold = threshold
        self.alert_cb = alert_cb

    def check_drift(self, items: List[Dict[str, Any]], labels: List[int]) -> float:
        acc = self.classifier.evaluate(items, labels)
        if acc < self.threshold and self.alert_cb:
            self.alert_cb(acc)
        return acc


class PreprocessingErrorPredictor:
    """Predict likelihood of pre-processing errors from document features."""

    def __init__(self) -> None:
        self.vectorizer = TfidfVectorizer(max_features=200)
        self.model = LogisticRegression(max_iter=200)
        self.is_trained = False

    def train(self, docs: List[Dict[str, Any]], labels: List[int]) -> None:
        texts = [d.get("content_preview", "") for d in docs]
        Xtext = self.vectorizer.fit_transform(texts)
        sizes = np.array([[d.get("size", 0)] for d in docs])
        X = np.hstack([Xtext.toarray(), sizes])
        self.model.fit(X, labels)
        self.is_trained = True

    def predict_risk(self, doc: Dict[str, Any]) -> float:
        if not self.is_trained:
            return 0.0
        text = [doc.get("content_preview", "")]
        Xtext = self.vectorizer.transform(text)
        size = np.array([[doc.get("size", 0)]])
        X = np.hstack([Xtext.toarray(), size])
        return float(self.model.predict_proba(X)[0][1])
