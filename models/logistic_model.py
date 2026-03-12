"""
Logistic Regression Model — System 1
Trains on FiveThirtyEight historical data with isotonic regression calibration.
"""

import logging
from typing import Tuple

import numpy as np
import streamlit as st
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import log_loss, brier_score_loss, roc_auc_score

from models.features import build_training_features, FEATURE_NAMES

logger = logging.getLogger(__name__)


@st.cache_resource(show_spinner="Training logistic regression model…")
def train_logistic_model(df, time_decay_lambda: float = 0.05):
    """
    Train and calibrate a logistic regression model on 538 historical data.
    Cached for the session — never retrains when sliders change.

    Returns
    -------
    model : CalibratedClassifierCV (wrapped LogisticRegression + isotonic calibration)
    X_test : np.ndarray
    y_test : np.ndarray
    feature_names : list[str]
    """
    X, y, w = build_training_features(df, time_decay_lambda=time_decay_lambda)

    X_train, X_test, y_train, y_test, w_train, w_test = train_test_split(
        X, y, w, test_size=0.15, random_state=42, shuffle=True
    )

    # Base logistic regression (C=1 default, no max_iter issue with lbfgs)
    base = LogisticRegression(
        C=1.0,
        max_iter=1000,
        solver="lbfgs",
        random_state=42,
    )

    # Wrap with isotonic calibration (cv=3 for speed)
    model = CalibratedClassifierCV(base, cv=3, method="isotonic")
    model.fit(X_train, y_train, sample_weight=w_train)

    # Evaluate on test set
    probs = model.predict_proba(X_test)[:, 1]
    ll = log_loss(y_test, probs)
    bs = brier_score_loss(y_test, probs)
    auc = roc_auc_score(y_test, probs)

    logger.info(
        "Logistic model trained. Log-loss=%.4f  Brier=%.4f  AUC=%.4f",
        ll, bs, auc
    )

    return {
        "model":         model,
        "X_test":        X_test,
        "y_test":        y_test,
        "log_loss":      ll,
        "brier_score":   bs,
        "auc":           auc,
        "feature_names": FEATURE_NAMES,
        "n_train":       len(X_train),
        "n_test":        len(X_test),
    }


def predict_logistic(model_bundle: dict, feature_vector: np.ndarray) -> float:
    """Return calibrated win probability for team1 given a feature vector."""
    fv = np.array(feature_vector).reshape(1, -1)
    return float(model_bundle["model"].predict_proba(fv)[0, 1])


def get_calibration_data(model_bundle: dict, n_bins: int = 10) -> Tuple[np.ndarray, np.ndarray]:
    """Return (mean_predicted_prob, fraction_of_positives) for calibration curve."""
    probs = model_bundle["model"].predict_proba(model_bundle["X_test"])[:, 1]
    fraction_pos, mean_pred = calibration_curve(
        model_bundle["y_test"], probs, n_bins=n_bins, strategy="quantile"
    )
    return mean_pred, fraction_pos
