"""
XGBoost Classifier — System 9
Trains on the same features as logistic regression (plus additional derived ones).
Captures non-linear relationships that logistic regression misses.
"""

import logging

import numpy as np
import streamlit as st
from sklearn.metrics import log_loss, brier_score_loss, roc_auc_score
from sklearn.model_selection import train_test_split, cross_val_score
from xgboost import XGBClassifier

from models.features import build_training_features, FEATURE_NAMES

logger = logging.getLogger(__name__)


@st.cache_resource(show_spinner="Training XGBoost model…")
def train_xgboost_model(df, time_decay_lambda: float = 0.05):
    """
    Train XGBoost on 538 historical data.
    Cached for the session.

    Returns dict with model + evaluation metrics.
    """
    X, y, w = build_training_features(df, time_decay_lambda=time_decay_lambda)

    X_train, X_test, y_train, y_test, w_train, w_test = train_test_split(
        X, y, w, test_size=0.15, random_state=42, shuffle=True
    )

    # Hyperparameters tuned via cross-validation intuition
    # (full CV grid search omitted to keep startup fast — values are solid defaults)
    model = XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        gamma=0.1,
        reg_lambda=1.0,
        reg_alpha=0.1,
        use_label_encoder=False,
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
        verbosity=0,
    )

    model.fit(
        X_train, y_train,
        sample_weight=w_train,
        eval_set=[(X_test, y_test)],
        verbose=False,
    )

    probs = model.predict_proba(X_test)[:, 1]
    ll = log_loss(y_test, probs)
    bs = brier_score_loss(y_test, probs)
    auc = roc_auc_score(y_test, probs)

    logger.info(
        "XGBoost model trained. Log-loss=%.4f  Brier=%.4f  AUC=%.4f",
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
        "feature_importance": dict(zip(FEATURE_NAMES, model.feature_importances_)),
    }


def predict_xgboost(model_bundle: dict, feature_vector: np.ndarray) -> float:
    """Return XGBoost win probability for team1 given a feature vector."""
    fv = np.array(feature_vector).reshape(1, -1)
    return float(model_bundle["model"].predict_proba(fv)[0, 1])
