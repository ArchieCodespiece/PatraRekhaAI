"""Document Intake Gatekeeper.

Policy-based ALLOW / REVIEW / BLOCK routing for every incoming document,
inserted before the existing chunking / embedding / storage / RAG pipeline.

Public interface (source-agnostic, reusable):

    from gatekeeper import evaluate, classify

    decision = evaluate(document, workspace_policy, text=extracted_text)
    # decision.decision in {"ALLOW", "REVIEW", "BLOCK"}

The webhook worker uses the higher-level service entry point
``gatekeeper.service.evaluate_intake`` which resolves policies, applies
manual overrides and records the audit trail.
"""

from __future__ import annotations

from typing import Mapping

from gatekeeper.categories import (
    DEFAULT_CATEGORIES,
    CATEGORY_LABELS,
)
from gatekeeper.classifier import (
    ClassificationResult,
    classify,
)
from gatekeeper.engine import (
    DECISION_ALLOW,
    DECISION_REVIEW,
    DECISION_BLOCK,
    EvaluationResult,
    evaluate_classification,
)

__all__ = [
    "DECISION_ALLOW",
    "DECISION_REVIEW",
    "DECISION_BLOCK",
    "ClassificationResult",
    "EvaluationResult",
    "DEFAULT_CATEGORIES",
    "CATEGORY_LABELS",
    "classify",
    "evaluate",
    "evaluate_classification",
]


def evaluate(
    document: Mapping,
    workspace_policy: Mapping | None,
    text: str | None = None,
    llm_enabled: bool = False,
    override: str | None = None,
) -> EvaluationResult:
    """
    Pure decision entry point.

    ``document``            dict with ``filename`` / ``name`` and optional
                            ``provenance`` {sender, subject, email_intent}.
    ``workspace_policy``    normalized policy dict from
                            ``db.intake_policies`` (or a hand-built dict),
                            or None.  A disabled/absent policy yields ALLOW.
    ``text``                optional already-extracted document text.
    ``override``            optional manual ALLOW/BLOCK resolution.

    Returns an ``EvaluationResult`` (decision, category, confidence,
    signals, reason, policy_version).
    """

    classification = classify(
        document,
        text=text,
        llm_enabled=llm_enabled,
    )

    return evaluate_classification(
        classification,
        document,
        workspace_policy,
        text=text,
        override=override,
    )