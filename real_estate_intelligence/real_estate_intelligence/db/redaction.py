"""PII redaction and sanitization utilities for GujRERA intelligence data.

Scans and scrubs sensitive Personally Identifiable Information (PII):
- Indian Permanent Account Numbers (PAN)
- 12-digit national IDs (Aadhaar)
- Personal email addresses
- Bank account numbers
while strictly preserving statutory GujRERA project registration identifiers
(PR/GJ/...) and Council of Architecture (CoA) license numbers.
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Regex patterns for sensitive entity detection
EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# PAN: 5 letters, 4 digits, 1 letter, optional service tax / GSTIN suffix
PAN_REGEX = re.compile(r"\b[A-Za-z]{5}\d{4}[A-Za-z](?:ST\d{3})?\b")
# 12-digit National ID (Aadhaar): 12 digits, optional space or hyphen separator
AADHAAR_REGEX = re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b")
# Bank account in free text
TEXT_BANK_ACCOUNT_REGEX = re.compile(r"(?i)\b(?:a/c(?:\s*no)?|account(?:\s*no)?\.?)\s*[:#-]?\s*(\d{4,18})\b")

# Whitelist patterns for statutory identifiers
COA_PATTERN = re.compile(r"\bCA/\d{2,4}/\d+\b|\bCA/\d+/\d+\b", re.IGNORECASE)
RERA_PATTERN = re.compile(r"\bPR/GJ/[A-Za-z0-9/_-]+\b", re.IGNORECASE)

# Sensitive key markers
SENSITIVE_KEY_NAMES: Set[str] = {
    "license_or_reg_no",
    "name",
    "email",
    "address",
    "account_no",
    "account_number",
    "bank_account",
    "account_number_masked",
    "snippet",
    "detail",
    "remarks",
    "shared_anchors",
    "shared_licenses",
    "shared_banks",
}

ACCOUNT_KEY_NAMES: Set[str] = {
    "account_no",
    "account_number",
    "bank_account",
    "account_number_masked",
    "raw_account_no",
}


def is_whitelisted(text: str) -> bool:
    """Return True if the text represents a statutory RERA registration or CoA license."""
    s = text.strip()
    if s.upper().startswith("PR/GJ/"):
        return True
    if COA_PATTERN.fullmatch(s):
        return True
    return False


def mask_bank_account(val: Any) -> str:
    """Mask bank account to ****XXXX retaining last 4 digits."""
    val_str = str(val).strip()
    if not val_str:
        return "****"
    # If already masked like ****1234
    if re.match(r"^\*+[0-9A-Za-z]+$", val_str):
        return val_str
    digits = re.sub(r"\D", "", val_str)
    if len(digits) >= 4:
        return f"****{digits[-4:]}"
    elif len(digits) > 0:
        return f"****{digits}"
    return "****"


def _scrub_text(text: str) -> str:
    """Scrub PAN, Aadhaar, Email, and bank accounts from text while preserving whitelisted tokens."""
    if not text:
        return text

    if is_whitelisted(text):
        return text

    # Extract whitelisted spans to avoid accidental redaction
    placeholders: List[Tuple[str, str]] = []
    
    def repl_whitelist(match: re.Match) -> str:
        token = match.group(0)
        idx = len(placeholders)
        placeholder = f"__WL_STATUTORY_{idx}__"
        placeholders.append((placeholder, token))
        return placeholder

    scrubbed = RERA_PATTERN.sub(repl_whitelist, text)
    scrubbed = COA_PATTERN.sub(repl_whitelist, scrubbed)

    # 1. Emails
    scrubbed = EMAIL_REGEX.sub("[REDACTED-EMAIL]", scrubbed)

    # 2. PAN
    scrubbed = PAN_REGEX.sub("[REDACTED-PAN]", scrubbed)

    # 3. 12-digit National ID (Aadhaar)
    scrubbed = AADHAAR_REGEX.sub("[REDACTED-ID]", scrubbed)

    # 4. Bank account references in text
    def repl_acct(match: re.Match) -> str:
        raw_num = match.group(1)
        masked = mask_bank_account(raw_num)
        return match.group(0).replace(raw_num, masked)

    scrubbed = TEXT_BANK_ACCOUNT_REGEX.sub(repl_acct, scrubbed)

    # Restore whitelisted tokens
    for placeholder, original in placeholders:
        scrubbed = scrubbed.replace(placeholder, original)

    return scrubbed


def redact_value(key: str, value: Any) -> Any:
    """Redact sensitive PII from a single key-value pair.
    
    Args:
        key: Column or attribute name.
        value: The value to redact.
    """
    if value is None:
        return None

    key_lower = str(key).lower().strip() if key else ""

    # Check bank account keys
    if key_lower in ACCOUNT_KEY_NAMES or ("account" in key_lower and ("no" in key_lower or "num" in key_lower or "mask" in key_lower)):
        return mask_bank_account(value)

    # If value is numeric and not an account key, return as is
    if isinstance(value, (int, float, bool)):
        return value

    val_str = str(value)

    # Check if key is sensitive or if key is empty/unspecified
    is_sensitive = (
        not key_lower
        or key_lower in SENSITIVE_KEY_NAMES
        or any(k in key_lower for k in ("license", "reg_no", "email", "address", "snippet", "detail", "remarks"))
        or key_lower.endswith("name")
    )

    if not is_sensitive:
        return value

    return _scrub_text(val_str)


def redact_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Redact all sensitive fields in a dictionary record."""
    if not isinstance(record, dict):
        return record
    out: Dict[str, Any] = {}
    for k, v in record.items():
        if isinstance(v, dict):
            out[k] = redact_record(v)
        elif isinstance(v, list):
            out[k] = [redact_record(item) if isinstance(item, dict) else redact_value(k, item) for item in v]
        else:
            out[k] = redact_value(k, v)
    return out


def redact_payload(obj: Any) -> Any:
    """Recursively scrub sensitive keys and text across arbitrary dict/list structures."""
    if isinstance(obj, dict):
        out_dict: Dict[str, Any] = {}
        for k, v in obj.items():
            if isinstance(v, (dict, list, tuple)):
                out_dict[k] = redact_payload(v)
            else:
                out_dict[k] = redact_value(k, v)
        return out_dict
    elif isinstance(obj, list):
        return [redact_payload(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(redact_payload(item) for item in obj)
    elif isinstance(obj, str):
        return redact_value("", obj)
    return obj
