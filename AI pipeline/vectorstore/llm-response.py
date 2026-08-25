"""Utility for generating a chat answer from retrieved Pinecone context."""

from __future__ import annotations

import os
import re

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

RESPONSE_MODE_INSTRUCTIONS = {
    "action_list": (
        "FORMAT: Use a Markdown bulleted list. "
        "Bold the key action. "
        "Include deadlines or responsible parties when available."
    ),
    "deadline_table": (
        "FORMAT: Use a Markdown table. "
        "Columns: | Deadline | Action | Responsible Party | Document |. "
        "Sort rows chronologically by deadline."
    ),
    "comparison_table": (
        "FORMAT: Use a Markdown table. "
        "Compare the documents side-by-side with clear column headers."
    ),
    "extraction_table": (
        "FORMAT: Use a Markdown table. "
        "Extract the requested structured information into columns."
    ),
    "summary": (
        "FORMAT: Use a short overview paragraph, "
        "followed by key points as a bulleted list. "
        "Use Markdown headings."
    ),
    "timeline": (
        "FORMAT: Use a Markdown table or chronological bullet list. "
        "Order events from earliest to latest."
    ),
    "general": (
        "FORMAT: Use clear Markdown with headings and bullets where helpful. "
        "Do not use one large paragraph for multiple independent items."
    ),
}


def classify_query(question: str) -> str:
    q = question.lower()

    if re.search(
        r"\b(action\s*items?|things?\s*to\s*do|required\s*actions?|what\s*should\s*(i|we)\s*do)\b",
        q,
    ):
        return "action_list"

    if re.search(
        r"\b(deadlines?|due\s*dates?|important\s*dates?|timelines?|when\s*(is|are)|by\s*when)\b",
        q,
    ):
        return "deadline_table"

    if re.search(
        r"\b(compare|comparison|difference|versus|vs\.?)\b",
        q,
    ):
        return "comparison_table"

    if re.search(
        r"\b(summarize|summary|summarise|key\s*points?|overview|tl;dr)\b",
        q,
    ):
        return "summary"

    if re.search(
        r"\b(extract|list\s*(all|the)?\s*(names|dates|amounts|numbers|emails|addresses))\b",
        q,
    ):
        return "extraction_table"

    if re.search(
        r"\b(timeline|chronolog|sequence\s*of\s*events|order\s*of)\b",
        q,
    ):
        return "timeline"

    return "general"


def generate_response(question: str, context: str) -> str:
    """
    Generate a final answer using the Groq model with retrieved vector context.

    Parameters
    ----------
    question : str
        User question.
    context : str
        Context text gathered from filtered Pinecone retrieval.
    """

    question = question.strip()
    context = context.strip()

    if not question:
        raise ValueError("Question cannot be empty.")

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is missing from the environment.")

    client = Groq(api_key=api_key)

    if not context:
        context = "No relevant context was found for the selected documents."

    mode = classify_query(question)
    format_instruction = RESPONSE_MODE_INSTRUCTIONS[mode]

    system_prompt = (
        "You are a document QA assistant. Answer using only the provided "
        "selected-document context. Do not use outside knowledge. "
        "When the documents mention multiple documents, cite the document "
        "names provided in the context. "
        "Return your answer in Markdown. "
        "Never expose internal identifiers such as UUIDs, database IDs, "
        "chunk IDs, or Pinecone IDs. Use the human-readable document name only. "
        "Do not manually generate source metadata; source references are handled "
        "by the application. "
        "Answer the user's question directly without prefacing with "
        "'Based on the provided context' unless absolutely necessary.\n\n"
        f"{format_instruction}"
    )

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": (
                f"Question: {question}\n\n"
                f"Context:\n{context}"
            ),
        },
    ]

    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=messages,
            temperature=0.2,
            max_completion_tokens=1024,
            top_p=1,
            stream=False,
        )

        return completion.choices[0].message.content or ""
    except Exception:
        return (
            "I couldn't reach the external LLM service right now, "
            "so I'm falling back to the retrieved document context. "
            f"Relevant context: {context[:600]}"
        )


        return completion.choices[0].message.content or ""
    except Exception:
        return (
            "I couldn’t reach the external LLM service right now, "
            "so I’m falling back to the retrieved document context. "
            f"Relevant context: {context[:600]}"
        )

