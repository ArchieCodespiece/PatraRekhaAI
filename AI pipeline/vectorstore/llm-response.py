"""Utility for generating a chat answer from retrieved Pinecone context."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()


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

    messages = [
        {
            "role": "system",
            "content": (
                "You are a document QA assistant. Answer using only the provided "
                "selected-document context. Do not use outside knowledge. If the "
                "documents, mention each document separately and cite the document "
                "names from the context."
            ),
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
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=0.2,
            max_completion_tokens=1024,
            top_p=1,
            stream=False,
        )

        return completion.choices[0].message.content or ""
    except Exception:
        return (
            "I couldn’t reach the external LLM service right now, "
            "so I’m falling back to the retrieved document context. "
            f"Relevant context: {context[:600]}"
        )

