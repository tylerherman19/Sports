"""
Model Performance Metrics — tracks log loss, Brier score, AUC, calibration.
"""

import logging
from typing import Dict, Any, List, Tuple

import numpy as np
from sklearn.metrics import log_loss, brier_score_loss, roc_auc_score
from sklearn.calibration import calibration_curve

logger = logging.getLogger(__name__)


def compute_all_metrics(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> Dict[str, Any]:
    """
    Compute log loss, Brier score, AUC, and calibration curve data.

    Returns
    -------
    dict:
        log_loss        — scalar
        brier_score     — scalar
        auc             — scalar
        calib_pred      — array of mean predicted probabilities per bucket
        calib_actual    — array of actual win rates per bucket
        bucket_stats    — list of dicts for confidence bucket table
    """
    ll = log_loss(y_true, y_prob)
    bs = brier_score_loss(y_true, y_prob)
    auc = roc_auc_score(y_true, y_prob)

    # Calibration curve
    frac_pos, mean_pred = calibration_curve(y_true, y_prob, n_bins=n_bins, strategy="quantile")

    # Confidence bucket analysis: 50–60, 60–70, 70–80, 80+%
    buckets = compute_bucket_stats(y_true, y_prob)

    return {
        "log_loss":     float(ll),
        "brier_score":  float(bs),
        "auc":          float(auc),
        "calib_pred":   mean_pred.tolist(),
        "calib_actual": frac_pos.tolist(),
        "bucket_stats": buckets,
    }


def compute_bucket_stats(
    y_true: np.ndarray,
    y_prob: np.ndarray,
) -> List[Dict[str, Any]]:
    """
    Break predictions into confidence buckets and compute accuracy per bucket.
    Uses max(p, 1-p) as the confidence measure so that 60% means the model
    said one team had at least 60% chance.
    """
    confidence = np.maximum(y_prob, 1.0 - y_prob)
    correct = (y_prob >= 0.5).astype(int) == y_true

    buckets = []
    boundaries = [(0.50, 0.60), (0.60, 0.70), (0.70, 0.80), (0.80, 1.01)]
    labels = ["50–60%", "60–70%", "70–80%", "80%+"]

    for (low, high), label in zip(boundaries, labels):
        mask = (confidence >= low) & (confidence < high)
        count = mask.sum()
        accuracy = float(correct[mask].mean()) if count > 0 else None
        avg_conf = float(confidence[mask].mean()) if count > 0 else None
        buckets.append({
            "bucket":    label,
            "count":     int(count),
            "accuracy":  accuracy,
            "avg_confidence": avg_conf,
        })

    return buckets


def ensemble_metrics_from_bundles(
    logistic_bundle: Dict,
    xgb_bundle: Dict,
) -> Dict[str, Dict[str, Any]]:
    """
    Compute metrics for both models on the same test set.
    Uses the logistic model's test set as the shared evaluation set.
    """
    X_test = logistic_bundle["X_test"]
    y_test = logistic_bundle["y_test"]

    log_probs = logistic_bundle["model"].predict_proba(X_test)[:, 1]
    xgb_probs = xgb_bundle["model"].predict_proba(X_test)[:, 1]

    return {
        "logistic": compute_all_metrics(y_test, log_probs),
        "xgboost":  compute_all_metrics(y_test, xgb_probs),
        "ensemble": compute_all_metrics(y_test, (log_probs * 0.55 + xgb_probs * 0.45)),
    }
