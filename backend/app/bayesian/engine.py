"""Probability engine and Bayesian updating for DHQPM (Phase 9+).

Models uncertain hospital events using labelled historical or synthetic data
with Laplace smoothing, then applies naive-Bayes posterior updating when
new evidence arrives. All probabilities are documented and traceable."""
from typing import Dict, Any, Optional
from datetime import datetime


class BayesianEngine:
    """Naive-Bayes event probability engine for hospital queue dynamics."""

    def __init__(self, session_count: int = 0):
        # Priors with Laplace smoothing (add-1 / (N + 2))
        self._prior_delay: float = 1.0 / (session_count + 2) if session_count else 0.5
        self._prior_noshow: float = 1.0 / (session_count + 2) if session_count else 0.5
        self._prior_emergency: float = 1.0 / (session_count + 2) if session_count else 0.5

        # Likelihood counters (populated from training data)
        self._likelihoods: Dict[str, Dict[str, int]] = {
            "delay": {"total": session_count, "with_evidence": 0},
            "noshow": {"total": session_count, "with_evidence": 0},
            "emergency": {"total": session_count, "with_evidence": 0},
        }
        self._evidence_bins: Dict[str, int] = {
            "delay": 0,
            "noshow": 0,
            "emergency": 0,
        }

    # ---- Prior estimation from labelled data ----

    def set_prior_from_counts(
        self,
        *,
        count_delay: int,
        count_noshow: int,
        count_emergency: int,
        session_count: int,
    ) -> None:
        """Set event priors using Laplace-smoothed frequencies."""
        total = session_count + 2
        self._prior_delay = (count_delay + 1) / total
        self._prior_noshow = (count_noshow + 1) / total
        self._prior_emergency = (count_emergency + 1) / total

    # ---- Likelihood estimation ----

    def update_likelihood(
        self,
        *,
        event: Literal["delay", "noshow", "emergency"],
        evidence_present: bool = True,
    ) -> None:
        """Increment likelihood counters for an event given evidence."""
        key = event
        if evidence_present:
            self._likelihoods[key]["with_evidence"] += 1
        self._likelihoods[key]["total"] = (
            self._likelihoods[key]["total"] + 1
        )  # simplified; in production track bins

    # ---- Naive-Bayes posterior updating ----

    def posterior_delay_given_evidence(
        self,
        *,
        evidence_ratio: float = 1.0,  # P(evidence | delay) / P(evidence | ~delay) odds factor
    ) -> float:
        """Compute P(delay | evidence) using naive-Bayes odds form.

        Returns a float in [0, 1].
        """
        # Odds form: posterior_odds = prior_odds * LR
        prior_odds = self._prior_delay / (1 - self._prior_delay)
        # Likelihood ratio approximated from evidence_ratio parameter
        posterior_odds = prior_odds * evidence_ratio
        return posterior_odds / (1 + posterior_odds)

    def posterior_noshow_given_evidence(
        self,
        *,
        evidence_factor: float = 1.0,
    ) -> float:
        """Compute P(no_show | evidence) using naive-Bayes odds form."""
        prior_odds = self._prior_noshow / (1 - self._prior_noshow)
        posterior_odds = prior_odds * evidence_factor
        return posterior_odds / (1 + posterior_odds)

    def posterior_emergency_given_evidence(
        self,
        *,
        evidence_factor: float = 1.0,
    ) -> float:
        """Compute P(emergency | evidence) using naive-Bayes odds form."""
        prior_odds = self._prior_emergency / (1 - self._prior_emergency)
        posterior_odds = prior_odds * evidence_factor
        return posterior_odds / (1 + posterior_odds)

    # ---- Serialization for API / DB ----

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prior_delay": self._prior_delay,
            "prior_noshow": self._prior_noshow,
            "prior_emergency": self._prior_emergency,
            "likelihoods": self._likelihoods,
            "evidence_bins": self._evidence_bins,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BayesianEngine":
        engine = cls(session_count=0)
        engine._prior_delay = data.get("prior_delay", engine._prior_delay)
        engine._prior_noshow = data.get("prior_noshow", engine._prior_noshow)
        engine._prior_emergency = data.get("prior_emergency", engine._prior_emergency)
        engine._likelihoods = data.get("likelihoods", engine._likelihoods)
        engine._evidence_bins = data.get("evidence_bins", engine._evidence_bins)
        return engine