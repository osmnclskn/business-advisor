import re
from datetime import datetime, timezone
from lingua import Language, LanguageDetectorBuilder


_language_detector = LanguageDetectorBuilder.from_languages(
    Language.ENGLISH,
    Language.TURKISH,
).build()


def detect_language(text: str) -> str:
    try:
        detected = _language_detector.detect_language_of(text)
        if detected == Language.TURKISH:
            return "Turkish"
    except Exception as e:
        pass
    return "English"


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


if __name__ == "__main__":
    print("=== detect_language tests ===\n")

    test_cases = [
        # (input, expected, description)
        ("Satışlarım düşüyor, yardım et", "Turkish", "Turkish with special chars"),
        ("Müşteri şikayetleri çok arttı", "Turkish", "Turkish business problem"),
        ("Satis dusuk, yardim et", "Turkish", "Turkish WITHOUT special chars (mobile keyboard)"),
        ("Rakiplerimiz ne yapiyor bilmiyorum", "Turkish", "Turkish no special chars, longer"),
        ("My sales are dropping", "English", "Plain English"),
        ("What are the trends in AI sector?", "English", "English business question"),
        ("Can you give me a pizza recipe?", "English", "English non-business"),
        ("Hello", "English", "Short English greeting"),
        ("Merhaba", "Turkish", "Short Turkish greeting"),
        ("Help me with müşteri problems", "Turkish", "Mixed - Turkish char present"),
        ("E-ticaret sektöründe lider kim?", "Turkish", "Turkish with ö and ü"),
        ("warehouse operations delayed", "English", "English operational"),
        ("", "English", "Empty string fallback"),
        ("123 456", "English", "Numbers only fallback"),
    ]

    passed = 0
    failed = 0

    for text, expected, description in test_cases:
        result = detect_language(text)
        status = "✓" if result == expected else "✗"
        if result == expected:
            passed += 1
        else:
            failed += 1
        print(f"  {status} {description}")
        print(f"    Input:    \"{text}\"")
        print(f"    Expected: {expected} | Got: {result}")
        if result != expected:
            print(f"    *** FAILED ***")
        print()

    print(f"Results: {passed}/{passed + failed} passed", end="")
    if failed:
        print(f" ({failed} FAILED)")
    else:
        print(" — all good!")