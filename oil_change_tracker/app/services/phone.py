import re

def normalize_phone(raw: str) -> str:
    if not raw:
        return ""
    digits = re.sub(r"\D+", "", raw)
    # Keep last 10 if longer (US)
    if len(digits) > 10:
        digits = digits[-10:]
    if len(digits) == 10:
        return f"({digits[0:3]}) {digits[3:6]}-{digits[6:10]}"
    return digits
