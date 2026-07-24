"""
llm.py

Generic LLM wrapper for the summarization pipeline
using Groq.
"""

import os

from dotenv import load_dotenv
from groq import Groq

# -----------------------------------------------------------------------------
# Load Environment Variables
# -----------------------------------------------------------------------------

load_dotenv()

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

def generate(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    max_tokens: int = 1000,
) -> str:
    """
    Generate a response from the LLM.

    Parameters
    ----------
    system_prompt : str
        System instruction.

    user_prompt : str
        User/content prompt.

    temperature : float
        Sampling temperature.

    max_tokens : int
        Maximum number of output tokens.

    Returns
    -------
    str
        Generated response.
    """

    response = client.chat.completions.create(
        model=MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
    )

    return response.choices[0].message.content.strip()