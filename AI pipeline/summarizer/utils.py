"""
utils.py

Utility functions for the summarization pipeline.
"""

from __future__ import annotations
import json
import re




def combine_chunks(chunks: list[str]) -> str:
    """
    Combine semantic chunks into a single document string.

    Parameters
    ----------
    chunks : list[str]
        List of semantic chunk texts.

    Returns
    -------
    str
        Combined document text.
    """

    if not chunks:
        raise ValueError("No chunks provided.")

    cleaned_chunks = [
        chunk.strip()
        for chunk in chunks
        if chunk and chunk.strip()
    ]

    if not cleaned_chunks:
        raise ValueError("No valid chunk text found.")

    return "\n\n".join(cleaned_chunks)


def deduplicate_action_items(action_items: list[dict]) -> list[dict]:
    """
    Remove exact duplicate actionable items.

    Action items are considered duplicates if they have the same
    task, deadline, reason and page.

    Parameters
    ----------
    action_items : list[dict]
        Extracted actionable items.

    Returns
    -------
    list[dict]
        Deduplicated actionable items.
    """

    seen = set()
    unique_action_items = []

    for item in action_items:
        key = (
            item.get("task"),
            item.get("deadline"),
            item.get("reason"),
            item.get("page"),
        )

        if key not in seen:
            seen.add(key)
            unique_action_items.append(item)

    return unique_action_items

def parse_json_string(text: str) -> dict | list:
    """
    Safely parse JSON from a response string, cleaning up markdown code blocks
    and extraneous text if present.
    """
    text = text.strip()
    
    # 1. Try direct loading first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
        
    # 2. Extract content within markdown code block ```json ... ``` or ``` ... ```
    code_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 3. Find the first '{' or '[' and matching closing symbol
    start_brace = text.find('{')
    start_bracket = text.find('[')
    
    start_idx = -1
    end_idx = -1
    
    if start_brace != -1 and (start_bracket == -1 or start_brace < start_bracket):
        start_idx = start_brace
        end_idx = text.rfind('}')
    elif start_bracket != -1:
        start_idx = start_bracket
        end_idx = text.rfind(']')
        
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        try:
            return json.loads(text[start_idx:end_idx + 1])
        except json.JSONDecodeError:
            pass
            
    # Raise the original/standard exception
    return json.loads(text)
