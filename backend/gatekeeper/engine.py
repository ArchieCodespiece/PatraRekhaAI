"""Pure decision engine for the document intake gatekeeper.

Given a classification result and a workspace policy, produce the final
ALLOW / REVIEW / BLOCK decision.  This module has NO database or network
dependencies so it can be unit-tested with constructed policies.

Decision ordering:

1. No policy / disabled policy  ->  ALLOW (current ingestion behavior)
2. Manual override             ->  override decision (ALLOW/BLOCK)
3. Matching sender rule        ->  rule action
4. Matching keyword rule       ->  rule action
5. Blocked category            ->  BLOCK
6. Review category             ->  REVIEW
7. Allowed category            ->  ALLOW
8. Confidence below threshold  ->  REVIEW (ambiguous)
9. Unlisted category           ->  policy default_decision

Sensitive markers never decide on their own: they only appear as signals.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Mapping


DECISION_ALLOW = "ALLOW"
DECISION_REVIEW = "REVIEW"
DECISION_BLOCK = "BLOCK"


@dataclass(frozen=True)
class EvaluationResult:
    decision: str = DECISION_ALLOW
    category: str = "other"
    confidence: float = 0.0
    signals: list[dict] = field(default_factory=list)
    reason: str = "No intake policy configured; existing behavior preserved"
    policy_version: int | None = None
    classifier: str = "deterministic"
    overridden: bool = False

    @property
    def allowed(self) -> bool:
        return self.decision == DECISION_ALLOW

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "category": self.category,
            "confidence": self.confidence,
            "signals": self.signals,
            "reason": self.reason,
            "policy_version": self.policy_version,
            "classifier": self.classifier,
            "overridden": self.overridden,
        }


def evaluate_classification(
    classification,
    document: Mapping,
    policy: Mapping | None,
    text: str | None = None,
    override: str | None = None,
) -> EvaluationResult:
    """Pure decision from a classification result + policy."""

    category = getattr(classification, "category", None) or "other"
    confidence = getattr(classification, "confidence", 0.0) or 0.0
    signals = list(getattr(classification, "signals", None) or [])
    classifier = getattr(classification, "method", None) or "deterministic"

    # ------------------------------------------------------------------
    # 1. Manual override wins over everything.
    # ------------------------------------------------------------------
    if override in {DECISION_ALLOW, DECISION_BLOCK}:
        return EvaluationResult(
            decision=override,
            category=category,
            confidence=confidence,
            signals=signals,
            reason=f"Manual override ({override})",
            policy_version=policy.get("policy_version") if policy else None,
            classifier=classifier,
            overridden=True,
        )

    # ------------------------------------------------------------------
    # 2. No policy / disabled policy  ->  preserve current behavior.
    # ------------------------------------------------------------------
    if not policy:
        return EvaluationResult(
            decision=DECISION_ALLOW,
            category=category,
            confidence=confidence,
            signals=signals,
            reason="No intake policy configured; existing behavior preserved",
            classifier=classifier,
        )

    if not bool(policy.get("enabled", False)):
        return EvaluationResult(
            decision=DECISION_ALLOW,
            category=category,
            confidence=confidence,
            signals=signals,
            reason=f"Intake policy '{policy.get('name')}' is disabled",
            policy_version=policy.get("policy_version"),
            classifier=classifier,
        )

    # ------------------------------------------------------------------
    # 3. Category lists.
    # ------------------------------------------------------------------

    sender = _sender_from(document)

    # ------------------------------------------------------------------
    # 4. Sender rules.
    # ------------------------------------------------------------------
    for rule in policy.get("sender_rules") or []:
        if not _sender_matches(sender, rule):
            continue
        action = _action_for(rule)
        return EvaluationResult(
            decision=action,
            category=category,
            confidence=confidence,
            signals=signals,
            reason=f"Sender rule '{rule.get('value')}' -> {action}",
            policy_version=policy.get("policy_version"),
            classifier=classifier,
        )

    if text:
        # ------------------------------------------------------------------
        # 5. Keyword rules (regex over subject + extracted text).
        # ------------------------------------------------------------------
        searchable = f"{str(document.get('source_subject') or '')}\n{text}"
        for rule in policy.get("keyword_rules") or []:
            if not _keyword_matches(searchable, rule):
                continue
            action = _action_for(rule)
            return EvaluationResult(
                decision=action,
                category=category,
                confidence=confidence,
                signals=signals,
                reason=f"Keyword rule '{rule.get('value')}' -> {action}",
                policy_version=policy.get("policy_version"),
                classifier=classifier,
            )

    # ------------------------------------------------------------------
    # 6-8. Category-based routing.
    # ------------------------------------------------------------------
    blocked = _as_set(policy.get("blocked_categories"))
    reviewed = _as_set(policy.get("review_categories"))
    allowed = _as_set(policy.get("allowed_categories"))

    if category in blocked:
        return EvaluationResult(
            decision=DECISION_BLOCK,
            category=category,
            confidence=confidence,
            signals=signals,
            reason=f"Category '{category}' is blocked by policy",
            policy_version=policy.get("policy_version"),
            classifier=classifier,
        )

    if category in reviewed:
        return EvaluationResult(
            decision=DECISION_REVIEW,
            category=category,
            confidence=confidence,
            signals=signals,
            reason=f"Category '{category}' requires review",
            policy_version=policy.get("policy_version"),
            classifier=classifier,
        )

    if category in allowed:
        return EvaluationResult(
            decision=DECISION_ALLOW,
            category=category,
            confidence=confidence,
            signals=signals,
            reason=f"Category '{category}' is allowed by policy",
            policy_version=policy.get("policy_version"),
            classifier=classifier,
        )

    # ------------------------------------------------------------------
    # 9. Confidence gate.
    # ------------------------------------------------------------------
    min_confidence = float(policy.get("min_confidence") or 0)
    if min_confidence > 0 and confidence < min_confidence:
        return EvaluationResult(
            decision=DECISION_REVIEW,
            category=category,
            confidence=confidence,
            signals=signals,
            reason=(
                f"Confidence {confidence:.2f} below policy threshold "
                f"{min_confidence:.2f}"
            ),
            policy_version=policy.get("policy_version"),
            classifier=classifier,
        )

    # ------------------------------------------------------------------
    # 10. Unlisted category -> policy default.
    # ------------------------------------------------------------------
    default = str(policy.get("default_decision") or DECISION_REVIEW).upper()
    if default not in {DECISION_ALLOW, DECISION_REVIEW, DECISION_BLOCK}:
        default = DECISION_REVIEW

    return EvaluationResult(
        decision=default,
        category=category,
        confidence=confidence,
        signals=signals,
        reason=(
            f"Category '{category}' not listed; "
            f"defaulted to {default}"
        ),
        policy_version=policy.get("policy_version"),
        classifier=classifier,
    )


# ============================================================================
# Rule matching helpers
# ============================================================================

def _as_set(value) -> set[str]:
    return {str(item).strip().lower() for item in (value or []) if item}


def _sender_from(document: Mapping) -> str:
    provenance = document.get("provenance") or {}
    sender = str(
        provenance.get("sender")
        or document.get("source_sender")
        or document.get("sender")
        or ""
    ).strip().lower()
    return sender


def _action_for(rule: Mapping) -> str:
    action = str(rule.get("action") or "").strip().lower()
    return DECISION_ALLOW if action == "allow" else DECISION_BLOCK


def _sender_matches(sender: str, rule: Mapping) -> bool:
    if not sender:
        return False

    match_type = str(rule.get("match") or "").strip().lower()
    value = str(rule.get("value") or "").strip().lower()

    if not value:
        return False

    if match_type == "email":
        return sender == value

    if match_type == "domain":
        domain = sender.split("@")[-1] if "@" in sender else sender
        normalized = value.lstrip("@.").lower()
        return (
            domain == normalized
            or domain.endswith(f".{normalized}")
        )

    # match_type == "regex" (default)
    try:
        return re.search(value, sender, re.IGNORECASE) is not None
    except re.error:
        return False


def _keyword_matches(searchable: str, rule: Mapping) -> bool:
    value = str(rule.get("value") or "").strip()
    if not value:
        return False

    try:
        return re.search(value, searchable, re.IGNORECASE) is not None
    except re.error:
        return False