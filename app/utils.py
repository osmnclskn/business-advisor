import re
from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clean_llm_json_response(response: str) -> str:
    cleaned = response.strip()
    code_block_match = re.search(
        r'```(?:\s*json\s*|\s*JSON\s*|\s*)?\n?([\s\S]*?)\n?```',
        cleaned
    )
    if code_block_match:
        return code_block_match.group(1).strip()
    first_brace = cleaned.find('{')
    first_bracket = cleaned.find('[')
    if first_brace == -1 and first_bracket == -1:
        return cleaned
    
    if first_bracket != -1 and (first_brace == -1 or first_bracket < first_brace):
        json_array_match = re.search(r'(\[[\s\S]*\])', cleaned)
        if json_array_match:
            return json_array_match.group(1).strip()
    
    if first_brace != -1:
        json_object_match = re.search(r'(\{[\s\S]*\})', cleaned)
        if json_object_match:
            return json_object_match.group(1).strip()
    
    return cleaned
