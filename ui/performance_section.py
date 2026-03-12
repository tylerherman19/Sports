"""
Section 5 — Model Performance
Live log loss, Brier score, AUC, calibration curve, confidence bucket table.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, Any

from models.metrics import ensemble_metrics_from_bundles


def render_performance_section(
    logistic_bundle: Dict,
    xgb_bundle: Dict,
):
    st.markdown("## Model Performance")
    st.markdown(
        "Evaluated on a held-out 15% test split of FiveThirtyEight historical data "
        "(games since 1990). All metrics update live when model parameters change."
    )

    # Compute metrics
    with st.spinner("Computing metrics…"):
        try:
            metrics = ensemble_metrics_from_bundles(logistic_bundle, xgb_bundle)
        except Exception as e:
            st.error(f"Error computing metrics: {e}")
            return

    models_display = {
        "Logistic Regression": metrics["logistic"],
        "XGBoost":             metrics["xgboost"],
        "Ensemble Blend":      metrics["ensemble"],
    }

    # ── Metric cards ──────────────────────────────────────────────────────────
    for model_name, m in models_display.items():
        st.markdown(f"### {model_name}")
        c1, c2, c3 = st.columns(3)
        _metric_card(c1, "Log Loss", f"{m['log_loss']:.4f}",
                     "↓ lower is better | perfect = 0")
        _metric_card(c2, "Brier Score", f"{m['brier_score']:.4f}",
                     "↓ lower is better | perfect = 0")
        _metric_card(c3, "AUC", f"{m['auc']:.4f}",
                     "↑ higher is better | perfect = 1.0")

        # Calibration curve
        _render_calibration_curve(model_name, m)

        # Confidence bucket table
        _render_bucket_table(m["bucket_stats"])

        st.markdown("---")

    # ── Feature importance ─────────────────────────────────────────────────────
    st.markdown("### XGBoost Feature Importance")
    fi = xgb_bundle.get("feature_importance", {})
    if fi:
        _render_feature_importance(fi)
    else:
        st.caption("Feature importance not available.")


def _metric_card(col, label: str, value: str, note: str = ""):
    with col:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-value">{value}</div>'
            f'<div class="metric-label">{label}</div>'
            + (f'<div style="font-size:0.7rem;color:#484f58;margin-top:4px">{note}</div>' if note else "")
            + '</div>',
            unsafe_allow_html=True
        )


def _render_calibration_curve(model_name: str, metrics: Dict):
    pred = metrics.get("calib_pred", [])
    actual = metrics.get("calib_actual", [])
    if not pred or not actual:
        return

    fig = go.Figure()

    # Perfect calibration line
    fig.add_trace(go.Scatter(
        x=[0, 1], y=[0, 1],
        mode="lines",
        line=dict(color="#30363d", dash="dash", width=1),
        name="Perfect calibration",
    ))

    # Model calibration
    fig.add_trace(go.Scatter(
        x=pred, y=actual,
        mode="lines+markers",
        line=dict(color="#58a6ff", width=2),
        marker=dict(size=8, color="#58a6ff"),
        name=model_name,
        hovertemplate="Predicted: %{x:.0%}<br>Actual: %{y:.0%}<extra></extra>",
    ))

    fig.update_layout(
        plot_bgcolor="#161b22",
        paper_bgcolor="#0d1117",
        font_color="#e6edf3",
        xaxis=dict(title="Predicted Probability", tickformat=".0%", range=[0, 1]),
        yaxis=dict(title="Actual Win Rate", tickformat=".0%", range=[0, 1]),
        legend=dict(orientation="h", y=1.05),
        margin=dict(l=0, r=0, t=20, b=0),
        height=300,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_bucket_table(bucket_stats: list):
    st.markdown("**Confidence Bucket Accuracy**")

    headers = ["Confidence", "Games", "Model Accuracy", "Avg Confidence"]
    rows_html = ""
    for b in bucket_stats:
        acc = f"{b['accuracy']:.1%}" if b['accuracy'] is not None else "—"
        avg_conf = f"{b['avg_confidence']:.1%}" if b['avg_confidence'] is not None else "—"

        # Color accuracy cell
        if b["accuracy"] is not None:
            # Good: accuracy close to or above avg confidence
            avg_c = b.get("avg_confidence") or 0
            diff = b["accuracy"] - avg_c
            acc_color = "#3fb950" if diff > -0.02 else ("#f85149" if diff < -0.05 else "#e6edf3")
        else:
            acc_color = "#8b949e"

        rows_html += f"""
        <tr>
          <td><b>{b['bucket']}</b></td>
          <td style="color:#8b949e">{b['count']:,}</td>
          <td style="color:{acc_color};font-weight:600">{acc}</td>
          <td style="color:#8b949e">{avg_conf}</td>
        </tr>"""

    st.markdown(f"""
<table style="width:100%;border-collapse:collapse;font-size:0.85rem;color:#e6edf3">
  <thead>
    <tr>
      {"".join(f'<th style="background:#161b22;color:#8b949e;padding:6px 10px;text-align:left;border-bottom:1px solid #30363d;font-size:0.75rem;text-transform:uppercase">{h}</th>' for h in headers)}
    </tr>
  </thead>
  <tbody>
    {rows_html}
  </tbody>
</table>""", unsafe_allow_html=True)


def _render_feature_importance(fi: Dict):
    sorted_fi = sorted(fi.items(), key=lambda x: x[1], reverse=True)
    labels = [k for k, _ in sorted_fi]
    values = [v for _, v in sorted_fi]

    fig = go.Figure(go.Bar(
        x=values,
        y=labels,
        orientation="h",
        marker_color="#58a6ff",
        hovertemplate="%{y}: %{x:.4f}<extra></extra>",
    ))
    fig.update_layout(
        plot_bgcolor="#161b22",
        paper_bgcolor="#0d1117",
        font_color="#e6edf3",
        xaxis_title="Importance",
        margin=dict(l=0, r=0, t=10, b=0),
        height=300,
    )
    st.plotly_chart(fig, use_container_width=True)
