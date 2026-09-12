from workflows.compare import (
    FALLBACK_FACT_SECTION,
    _observed_sections_from_coverages,
    _plan_sections,
)
from workflows.llm import stream_text
from workflows.retrieval import ChunkRecord, DocumentCoverage
from workflows.state import WorkflowState


def make_state():
    return WorkflowState(
        user_id="user-1",
        owner_email="user@example.com",
        effective_email="user@example.com",
        query="Compare the two documents",
        conversation_id="conversation-1",
        selected_documents=["Document A", "Document B"],
        doc_pairs=[
            ("Document A", "doc-a"),
            ("Document B", "doc-b"),
        ],
    )


def test_observed_sections_ignore_generic_full_document_metadata():
    coverages = {
        "doc-a": DocumentCoverage(
            records=[],
            sections=["Full Document", "Overview", "2 Termination"],
        ),
        "doc-b": DocumentCoverage(
            records=[],
            sections=["Full Document", "3 Payment Terms"],
        ),
    }

    assert _observed_sections_from_coverages(coverages) == [
        "2 Termination",
        "3 Payment Terms",
    ]


def test_observed_sections_fall_back_to_headings_in_chunk_text():
    coverages = {
        "doc-a": DocumentCoverage(
            records=[
                ChunkRecord(
                    text=(
                        "# Scope of Work\n"
                        "The vendor must provide services.\n\n"
                        "1.2 Payment Terms\n"
                        "Payment is due in 30 days."
                    )
                )
            ],
            sections=["Full Document"],
        )
    }

    assert _observed_sections_from_coverages(coverages) == [
        "Scope of Work",
        "1.2 Payment Terms",
    ]


def test_plan_sections_preserves_observed_pdf_sections():
    sections = _plan_sections(
        make_state(),
        ["Scope of Work", "Payment Terms", "Termination"],
    )

    assert [section["name"] for section in sections] == [
        "Scope of Work",
        "Payment Terms",
        "Termination",
    ]
    assert "Overview" not in [section["name"] for section in sections]


def test_plan_sections_infers_topics_when_only_preview_exists():
    sections = _plan_sections(
        make_state(),
        [],
        preview_text=(
            "Habitat: Tigers live in forests.\n"
            "Diet: Tigers eat deer.\n\n"
            "Habitat: Lions live in savannas.\n"
            "Diet: Lions eat zebra."
        ),
    )

    section_names = [section["name"] for section in sections]

    assert "Habitat" in section_names
    assert "Diet" in section_names
    assert FALLBACK_FACT_SECTION not in section_names


def test_plan_sections_uses_fact_fallback_when_no_topics_are_clear():
    sections = _plan_sections(
        make_state(),
        [],
        preview_text="Tigers are striped cats.\n\nLions live in prides.",
    )

    assert sections == [
        {
            "name": FALLBACK_FACT_SECTION,
            "focus": (
                "Compare concrete facts, attributes, quantities, dates, "
                "entities, and other stated details from the documents."
            ),
            "sub_queries": [
                "facts attributes quantities dates entities details",
            ],
            "use_coverage": True,
        }
    ]


def test_stream_text_preserves_word_boundaries_between_chunks():
    chunks = list(stream_text("The comparison found differences.", chunk_size=12))

    assert "".join(chunks) == "The comparison found differences. "
