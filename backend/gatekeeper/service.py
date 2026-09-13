"""Webhook-facing intake gatekeeper service.

``evaluate_intake(document_record, content)`` is the single entry point used
by the document-processing worker for EVERY ingestion source (Gmail poller,
manual upload, Supabase trigger webhook, ...).  It:

1. Resolves the workspace (user_id -> owner_email -> 'default').
2. Loads the policy.  No enabled policy + no manual override  ->  ALLOW
   immediately with zero classifier cost (existing behavior unchanged).
3. Applies any manual override stored on the audit trail.
4. Extracts text cheaply (reusing the existing converter/pdfplumber tools).
5. Classifies (deterministic -> optional gated LLM).
6. Runs the pure policy engine.
7. Records an audit / quarantine row (REVIEW and BLOCK always; ALLOW only
   when a policy is active).

Every failure path is fail-open: ALLOW, exactly like today.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Mapping

from db.intake_policies import (
    DEFAULT_WORKSPACE,
    get_policy_for_workspace,
)
from db.intake_decisions import (
    get_override_for_file,
    record_decision,
)


MAX_EXTRACT_BYTES = int(
    os.getenv(
        "INTAKE_GATEKEEPER_MAX_EXTRACT_BYTES",
        10 * 1024 * 1024,
    )
)


def resolve_workspace_id(document_record: Mapping) -> str:
    user_id = str(document_record.get("user_id") or "").strip()
    if user_id:
        return user_id

    owner_email = str(
        document_record.get("owner_email") or ""
    ).strip().lower()
    if owner_email:
        return owner_email

    return DEFAULT_WORKSPACE


def _load_policy(workspace_id: str) -> dict | None:
    try:
        return get_policy_for_workspace(workspace_id)
    except Exception as exc:
        print(
            f"Intake gatekeeper: policy lookup failed for "
            f"{workspace_id}: {exc}"
        )
        return None


def extract_text(
    filename: str,
    content: bytes,
) -> str:
    """Extract lightweight text for classification.

    Reuses the existing document_preprocessing conversion utilities.
    PDFs are read with pdfplumber; other formats are converted to a temp
    PDF first via the project's own converter.  Returns "" on any failure.
    """

    if not content:
        return ""

    if len(content) > MAX_EXTRACT_BYTES:
        return ""

    extension = Path(filename or "").suffix.lower()

    pdf_path = None
    temp_dir = None

    try:

        from document_preprocessing.converter import (
            convert_to_pdf,
            is_supported_document,
        )

        if not is_supported_document(filename):
            return ""

        temp_dir = tempfile.TemporaryDirectory(
            prefix="patrarekha-intake-"
        )
        root = Path(temp_dir.name)

        original_path = root / Path(filename or "document").name
        original_path.write_bytes(content)

        if extension == ".pdf":
            pdf_path = original_path
        else:
            pdf_path = root / f"{original_path.stem}.pdf"
            convert_to_pdf(original_path, pdf_path)

        return _extract_pdf_text(pdf_path)

    except Exception as exc:
        print(
            f"Intake gatekeeper: text extraction failed for "
            f"{filename}: {exc}"
        )
        return ""

    finally:
        if temp_dir is not None:
            temp_dir.cleanup()


def _extract_pdf_text(pdf_path: Path) -> str:
    import pdfplumber

    parts: list[str] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            parts.append(text)

    return "\n".join(parts).strip()


def _classifier_document(document_record: Mapping) -> dict:
    return {
        "file_id": document_record.get("file_id"),
        "filename": document_record.get("filename"),
        "file_type": document_record.get("file_type"),
        "provenance": {
            "sender": document_record.get("source_sender"),
            "subject": document_record.get("source_subject"),
            "email_intent": document_record.get("email_intent"),
        },
    }


def evaluate_intake(
    document_record: Mapping | None,
    content: bytes | None = None,
) -> dict:
    """Evaluate one document against its workspace intake policy.

    Returns a decision dict:
        {decision, category, confidence, signals, reason, policy_version,
         classifier, overridden, workspace_id}
    Never raises: failures fall back to ALLOW to preserve existing behavior.
    """

    empty = {
        "decision": "ALLOW",
        "category": "other",
        "confidence": 0.0,
        "signals": [],
        "reason": "No intake policy configured; existing behavior preserved",
        "policy_version": None,
        "classifier": "deterministic",
        "overridden": False,
        "workspace_id": None,
    }

    if not document_record:
        return empty

    workspace_id = resolve_workspace_id(document_record)

    file_id = document_record.get("file_id")

    override = None
    try:
        override_row = get_override_for_file(str(file_id))
        if override_row:
            override = override_row.get("decision")
    except Exception:
        override = None

    # ------------------------------------------------------------------
    # Disabled / absent policy with no manual override: preserve current
    # behavior exactly, no classification cost, no audit noise.
    # ------------------------------------------------------------------
    policy = _load_policy(workspace_id)

    active = bool(policy and policy.get("enabled"))

    if not active and not override:
        return {
            **empty,
            "workspace_id": workspace_id,
            "overridden": False,
        }

    # ------------------------------------------------------------------
    # Active policy (or override): classify + decide.
    # ------------------------------------------------------------------
    from gatekeeper.engine import (
        evaluate_classification,
        DECISION_ALLOW,
    )
    from gatekeeper.classifier import classify as classify_document

    classifier_input = _classifier_document(document_record)

    text = ""
    try:
        if content or classifier_input.get("filename"):
            text = extract_text(
                str(classifier_input.get("filename") or ""),
                content or b"",
            )
    except Exception as exc:
        print(f"Intake gatekeeper: extraction error {exc}")

    try:
        from gatekeeper.llm import llm_enabled

        classification = classify_document(
            classifier_input,
            text=text,
            llm_enabled=llm_enabled(),
        )
    except Exception as exc:
        print(f"Intake gatekeeper: classification error {exc}")
        return {
            **empty,
            "workspace_id": workspace_id,
            "reason": f"Classification failed; allowed by default: {exc}",
        }

    result = evaluate_classification(
        classification,
        classifier_input,
        policy,
        text=text,
        override=override,
    )

    # ------------------------------------------------------------------
    # Audit / quarantine record.
    # ------------------------------------------------------------------
    try:
        should_record = result.decision != DECISION_ALLOW or active
        if should_record:
            record_decision(
                workspace_id=workspace_id,
                decision=result.decision,
                category=result.category,
                confidence=result.confidence,
                signals=result.signals,
                reason=result.reason,
                policy_version=result.policy_version,
                classifier=result.classifier,
                file_id=str(file_id) if file_id else None,
                source_email_id=document_record.get("source_email_id"),
            )
    except Exception as exc:
        print(f"Intake gatekeeper: audit record failed: {exc}")

    return {
        "decision": result.decision,
        "category": result.category,
        "confidence": result.confidence,
        "signals": result.signals,
        "reason": result.reason,
        "policy_version": result.policy_version,
        "classifier": result.classifier,
        "overridden": result.overridden,
        "workspace_id": workspace_id,
    }


def as_public_dict(result) -> dict:
    """Convert an EvaluationResult/decision dict into the public shape."""
    if hasattr(result, "to_dict"):
        return result.to_dict()
    return dict(result)