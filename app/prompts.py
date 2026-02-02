from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

PROMPTS_DIR = Path(__file__).parent / "prompts"


@lru_cache()
def load_prompt(prompt_name: str) -> dict[str, Any]:
    prompt_path = PROMPTS_DIR / f"{prompt_name}.yaml"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt_data = yaml.safe_load(f)
    required_fields = ["system", "user"]
    for field in required_fields:
        if field not in prompt_data:
            raise ValueError(
                f"Missing required field '{field}' in prompt file: {prompt_path}"
            )
    prompt_data.setdefault("temperature", 0.7)
    prompt_data.setdefault("max_tokens", 1500)
    return prompt_data


def format_prompt(prompt_data: dict[str, Any], **variables) -> dict[str, str]:
    return {
        "system": prompt_data["system"].format(**variables),
        "user": prompt_data["user"].format(**variables),
    }


def clear_prompt_cache():
    load_prompt.cache_clear()
