import json
from pathlib import Path

from models import Document, Page, Table
from semantic import SemanticBuilder


def load_document(json_path: str) -> Document:
    with open(json_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    pages = []

    for page in raw:
        tables = [
            Table(
                rows=t.get("rows", []),
                caption="",
                page_number=page["page_number"],
            )
            for t in page.get("tables", [])
        ]

        pages.append(
            Page(
                page_number=page["page_number"],
                text=page["text"],
                tables=tables,
            )
        )

    return Document(
        document_id="test_doc",
        document_name=Path(json_path).stem,
        pages=pages,
    )


doc = load_document(r"E:\PatraRekha\ingestion\KMRL.json")      # <-- your OCR JSON

builder = SemanticBuilder()

sections = builder.build(doc)

print(f"\nFound {len(sections)} sections\n")

for section in sections:
    print("=" * 60)
    print(f"Title      : {section.title}")
    print(f"Level      : {section.level}")
    print(f"Pages      : {section.page_start}-{section.page_end}")
    print(f"Paragraphs : {len(section.blocks)}")
    print(f"Tables     : {len(section.tables)}")

    print("\nPreview:\n")

    print("\n".join(section.blocks[:3]))

    print()