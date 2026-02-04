import os
import json
from datetime import datetime
import re
import spacy_transformers  # noqa: F401 ensures spaCy HF components are registered
import spacy
from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_analyzer.nlp_engine import TransformersNlpEngine, NerModelConfiguration
from presidio_analyzer.pattern import Pattern
from presidio_analyzer.pattern_recognizer import PatternRecognizer
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

# INITIAL SETUP AND CONFIGURATION
# By default, read from LLM_output.txt in the project root.
INPUT_FILE = "LLM_output.txt"
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Medical degree blacklist – tokens which should never be treated as PERSON names
MEDICAL_DEGREE_BLACKLIST = {
    "MD", "MS", "DNB", "DMLT", "MNAMS", "MBBS", "DM", "MCH",
    # Additional common medical degree abbreviations
    "BDS", "BAMS", "BHMS", "BPT"
}

# Drug whitelist (kept for optional use)
DRUG_NAME_WHITELIST = {
    "AMOXICILLIN", "LEVOSALBUTAMOL", "SALBUTAMOL", "AZITHROMYCIN",
    "CEFTRIAXONE", "DOLO", "PARACETAMOL", "IBUPROFEN",
    "CEFADROXIL", "CETIRIZINE", "MONTELUKAST"
}

# LABEL NORMALIZATION MAP
BLACKLISTED_TYPES = {"US_DRIVER_LICENSE", "US_SSN", "US_PASSPORT", "US_BANK_NUMBER", "URL", "MISC"}
LABEL_NORMALIZATION = {
    "PER": "PERSON", "PERSON": "PERSON", "PATIENT": "PERSON", "STAFF": "PERSON",
    "LOC": "LOCATION", "LOCATION": "LOCATION", "GPE": "LOCATION",
    "HOSP": "LOCATION", "HOSPITAL": "LOCATION",
    "ORG": "ORGANIZATION", "ORGANIZATION": "ORGANIZATION",
    "EMAIL": "EMAIL_ADDRESS", "PHONE": "PHONE_NUMBER",
    "DATE": "DATE_TIME", "TIME": "DATE_TIME",
    "POSTAL_CODE": "POSTAL_CODE", "ZIP": "POSTAL_CODE", "PIN": "POSTAL_CODE",
    "ADDRESS_NUMBER": "ADDRESS_NUMBER", "ADDRESS": "ADDRESS_NUMBER",
    "AGE": "AGE",
    "GENDER": "GENDER", "SEX": "GENDER",
}

PHONE_LIKE_TYPES = {"PHONE_NUMBER", "US_BANK_NUMBER", "US_DRIVER_LICENSE"}
ADDRESS_KEYWORDS = {
    "LAB", "PATHLAB", "PATHLABS", "REFERENCE", "HOSPITAL", "CLINIC",
    "CENTRAL", "NRL", "LPL", "BLOCK", "SECTOR", "AVENUE", "ROAD",
    "DELHI", "AHMEDABAD", "KUNJ"
}

# MODEL INITIALIZATION
print("[1/2] Initializing StanfordAIMI Transformer...")
mapping = {
    "PER": "PERSON", "PERSON": "PERSON",
    "LOC": "LOCATION", "LOCATION": "LOCATION", "GPE": "LOCATION",
    "ORG": "ORGANIZATION", "ORGANIZATION": "ORGANIZATION",
    "AGE": "AGE", "ID": "ID", "EMAIL": "EMAIL_ADDRESS",
    "DATE": "DATE_TIME", "TIME": "DATE_TIME",
    "PHONE": "PHONE_NUMBER",
    "PATIENT": "PERSON", "STAFF": "PERSON", "HCW": "PERSON",
    "HOSP": "LOCATION", "HOSPITAL": "LOCATION",
    "FACILITY": "LOCATION", "PATORG": "ORGANIZATION", "VENDOR": "ORGANIZATION"
}

ner_config = NerModelConfiguration(
    model_to_presidio_entity_mapping=mapping,
    alignment_mode="expand",
    aggregation_strategy="max",
    labels_to_ignore=["O"]
)

transformers_config = [
    {
        "lang_code": "en",
        "model_name": {
            "spacy": "en_core_web_sm",
            "transformers": "StanfordAIMI/stanford-deidentifier-base",
        }
    }
]

transformers_nlp = TransformersNlpEngine(
    models=transformers_config,
    ner_model_configuration=ner_config
)
stanford_analyzer = AnalyzerEngine(nlp_engine=transformers_nlp, supported_languages=["en"])


# HELPER FUNCTIONS
def normalize_label(label: str) -> str:
    return LABEL_NORMALIZATION.get(label.upper(), label.upper())


def presidio_to_dict(results, text):
    return [
        {
            "entity_type": normalize_label(r.entity_type),
            "text": text[r.start:r.end],
            "score": float(r.score),
            "start": r.start,
            "end": r.end,
        }
        for r in results
    ]


def overlap_fraction(a_start, a_end, b_start, b_end):
    inter = max(0, min(a_end, b_end) - max(a_start, b_start))
    denom = max(1, (max(a_end, b_end) - min(a_start, b_start)))
    return inter / denom


# ---------- Custom Pattern Detection Functions ----------
def detect_postal_codes(text: str) -> list:
    """
    Detect Indian postal codes (6-digit codes).
    Returns list of dicts with entity_type, text, start, end, score.
    """
    results = []
    # Indian postal code pattern: 6 digits, often preceded by dash, em dash, or space
    # First try to match with dash/em dash, then standalone 6 digits
    # Pattern 1: dash/em dash followed by 6 digits
    pattern1 = re.compile(r'[–\-]\s*\d{6}\b')
    for match in pattern1.finditer(text):
        start, end = match.span()
        matched_text = match.group()
        digits_only = re.sub(r'\D', '', matched_text)
        
        if len(digits_only) == 6:
            context_after = text[end:min(len(text), end+5)]
            # Accept if followed by comma, period, space, or end
            if context_after.startswith((',', '.', ' ', '\n', '')):
                results.append({
                    "entity_type": "POSTAL_CODE",
                    "text": digits_only,
                    "start": start,
                    "end": end,
                    "score": 0.85
                })
    
    # Pattern 2: Standalone 6 digits (with optional space) after location context
    pattern2 = re.compile(r'\b\d{3}\s*\d{3}\b')
    for match in pattern2.finditer(text):
        start, end = match.span()
        matched_text = match.group()
        digits_only = re.sub(r'\s', '', matched_text)
        
        # Skip if already captured by pattern1
        if any(r["start"] <= start < r["end"] for r in results):
            continue
        
        # Check context
        context_before = text[max(0, start-30):start]
        context_after = text[end:min(len(text), end+10)]
        
        # Reject if part of longer number sequence
        if re.search(r'\d{7,}', context_before + digits_only + context_after):
            continue
        
        # Accept if after location keywords or dash/em dash
        is_postal_context = (
            any(kw in context_before.lower() for kw in ['road', 'street', 'hyderabad', 'location', 
                                                         'delhi', 'mumbai', 'bangalore', 'chennai', 'guntur',
                                                         '–', '-']) or
            context_after.startswith((',', '.', ' ', '\n', ''))
        )
        
        if is_postal_context:
            results.append({
                "entity_type": "POSTAL_CODE",
                "text": digits_only,
                "start": start,
                "end": end,
                "score": 0.85
            })
    
    return results


def detect_address_numbers(text: str) -> list:
    """
    Detect address numbers like #15-11-154, #123, etc.
    Returns list of dicts with entity_type, text, start, end, score.
    """
    results = []
    # Pattern: # followed by numbers with optional dashes/slashes
    # Examples: #15-11-154, #123, #12/34
    hash_pattern = re.compile(r'#\s*\d+(?:[-/]\d+)*')
    for match in hash_pattern.finditer(text):
        start, end = match.span()
        matched_text = match.group()
        
        # Check context - should be near address-related words
        context_before = text[max(0, start-30):start].lower()
        context_after = text[end:min(len(text), end+30)].lower()
        
        # Accept if near location/address keywords
        address_keywords = ['beside', 'near', 'road', 'street', 'address', 'location', 
                           'hospital', 'clinic', 'market', 'super']
        if (any(kw in context_before for kw in address_keywords) or
            any(kw in context_after for kw in address_keywords)):
            results.append({
                "entity_type": "ADDRESS_NUMBER",
                "text": matched_text,
                "start": start,
                "end": end,
                "score": 0.80
            })
    # Pattern without '#' (e.g., 15-11-154) when near address keywords
    dash_pattern = re.compile(r'\b\d{1,4}(?:[-/]\d+){1,}\b')
    for match in dash_pattern.finditer(text):
        start, end = match.span()
        matched_text = match.group()
        context_before = text[max(0, start-30):start].lower()
        context_after = text[end:min(len(text), end+30)].lower()
        address_keywords = ['beside', 'near', 'road', 'street', 'address', 'location',
                           'hospital', 'clinic', 'market', 'super']
        if (any(kw in context_before for kw in address_keywords) or
            any(kw in context_after for kw in address_keywords)):
            results.append({
                "entity_type": "ADDRESS_NUMBER",
                "text": matched_text,
                "start": start,
                "end": end,
                "score": 0.80
            })
    return results

def detect_age_values(text: str) -> list:
    """Detect age values in all common formats: 'Age 62', 'Age: 62', 'Age/Sex: 62', 'Age / Sex: 23 YRS / M', etc."""
    results = []
    # Comprehensive pattern handling all formats:
    # - "Age 62", "Age: 62", "Age:62"
    # - "Age/Sex: 62", "Age / Sex: 62", "Age/Sex:62"
    # - "Age / Sex: 23 YRS / M", "Age: 62 years", "Age 62/Male"
    # Pattern: Age (optional /Sex with optional spaces) optional colon optional spaces number (optional suffix)
    pattern = re.compile(r'\bAge\s*(?:\/\s*Sex)?\s*:?\s*(\d{1,3})\s*(?:YRS|years?|Y|M|Male|Female|\/[MF])?', re.IGNORECASE)
    for match in pattern.finditer(text):
        age_num = int(match.group(1))
        if 0 <= age_num <= 120:  # Reasonable age range
            # Find the actual number position (not the full match)
            age_start = match.start(1)  # Position of the number group
            age_end = match.end(1)      # End position of the number group
            results.append({
                "entity_type": "AGE",
                "text": match.group(1),  # Store just the age number "62"
                "start": age_start,       # Redact only the number, not the label
                "end": age_end,           # Redact only the number, not the label
                "score": 0.90
            })
    return results


def detect_gender_sex(text: str) -> list:
    """Detect gender/sex identifiers in common medical formats."""
    results = []
    # Common patterns:
    # - "Age / Sex: 23 Years / Male"
    # - "Age/Sex: 62/Male"
    # - "Sex: Male", "Sex: Female"
    # - "Gender: M", "Gender: F"
    # - "M", "F", "Male", "Female" (when near Age or Sex context)
    
    # Pattern 1: Explicit "Sex:" or "Gender:" labels
    pattern1 = re.compile(
        r'\b(?:Sex|Gender)\s*:?\s*(Male|Female|M|F|MALE|FEMALE)\b',
        re.IGNORECASE
    )
    for match in pattern1.finditer(text):
        gender_text = match.group(1)
        start, end = match.span(1)  # Only redact the gender value, not the label
        results.append({
            "entity_type": "GENDER",
            "text": gender_text,
            "start": start,
            "end": end,
            "score": 0.90
        })
    
    # Pattern 2: Gender in "Age / Sex: XX Years / Male" format
    pattern2 = re.compile(
        r'\bAge\s*(?:\/\s*Sex)?\s*:?\s*\d{1,3}\s*(?:Years?|YRS)?\s*\/\s*(Male|Female|M|F|MALE|FEMALE)\b',
        re.IGNORECASE
    )
    for match in pattern2.finditer(text):
        gender_text = match.group(1)
        # Find the position of the gender text within the match
        match_start = match.start()
        gender_start = match.start(1)
        gender_end = match.end(1)
        results.append({
            "entity_type": "GENDER",
            "text": gender_text,
            "start": gender_start,
            "end": gender_end,
            "score": 0.90
        })
    
    # Pattern 3: Standalone "Male" or "Female" after age patterns (e.g., "Age 23 Male")
    pattern3 = re.compile(
        r'\bAge\s*:?\s*\d{1,3}\s+(Male|Female|M|F)\b',
        re.IGNORECASE
    )
    for match in pattern3.finditer(text):
        gender_text = match.group(1)
        gender_start = match.start(1)
        gender_end = match.end(1)
        # Check if not already captured by pattern2
        already_captured = any(
            r["start"] <= gender_start < r["end"] for r in results
        )
        if not already_captured:
            results.append({
                "entity_type": "GENDER",
                "text": gender_text,
                "start": gender_start,
                "end": gender_end,
                "score": 0.85
            })
    
    # Pattern 4: "/ M" or "/ F" format (short form)
    pattern4 = re.compile(
        r'\b\/\s*(M|F)\b(?!\w)',
        re.IGNORECASE
    )
    for match in pattern4.finditer(text):
        # Check context - should be near age or patient info
        context_start = max(0, match.start() - 50)
        context_text = text[context_start:match.end()]
        if re.search(r'\bAge|Sex|Patient|/\s*\d{1,3}\s*Years?\b', context_text, re.IGNORECASE):
            gender_text = match.group(1)
            gender_start = match.start(1)  # Start after the "/ "
            gender_end = match.end(1)
            # Check if not already captured
            already_captured = any(
                r["start"] <= gender_start < r["end"] for r in results
            )
            if not already_captured:
                results.append({
                    "entity_type": "GENDER",
                    "text": gender_text,
                    "start": gender_start,
                    "end": gender_end,
                    "score": 0.80
                })
    
    return results


def detect_abbreviated_doctor_names(text: str, detected_persons: list) -> list:
    """Detect abbreviated doctor names like 'Dr. K. Ragava' when full name was detected."""
    results = []
    # Extract last names from detected persons (likely doctors if they have titles)
    last_names = set()
    for person in detected_persons:
        name = person.get("text", "")
        # Extract last name (last word after spaces/dots)
        parts = re.split(r'[.\s]+', name.strip())
        if len(parts) >= 2:
            last_name = parts[-1]
            if len(last_name) > 2:  # Valid last name
                last_names.add(last_name)
    
    if not last_names:
        return results
    
    # Pattern: Dr. [Initial(s)] LastName
    for last_name in last_names:
        pattern = re.compile(rf'\bDr\.\s+[A-Z]\.\s+{re.escape(last_name)}\b', re.IGNORECASE)
        for match in pattern.finditer(text):
            # Check if this exact span wasn't already detected
            start, end = match.span()
            already_detected = any(
                p.get("start", 0) <= start < p.get("end", 0) 
                for p in detected_persons
            )
            if not already_detected:
                results.append({
                    "entity_type": "PERSON",
                    "text": match.group(0),
                    "start": start,
                    "end": end,
                    "score": 0.85
                })
    return results


# ---------- Phone helpers ----------
def normalize_phone_digits(text: str) -> str:
    """Return only digits from text."""
    return re.sub(r"\D", "", text or "")


def is_valid_phone_number(text: str) -> bool:
    """
    Accepts common Indian mobile and landline formats while rejecting date-like,
    vitals, MRD codes, times, decimals etc.
    """
    if not text or not text.strip():
        return False
    raw = text.strip()

    # digits only
    digits = normalize_phone_digits(raw)

    # reasonable length for phone numbers in the domain (landline+std could be up to 12)
    if not (7 <= len(digits) <= 12):
        return False

    # Reject date-like patterns (e.g., 24/04/12-0901)
    if re.search(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", raw):
        return False
    
    # Normalize spaces/dashes for pattern matching (replace multiple spaces/dashes with single separator)
    normalized = re.sub(r"[- ]+", " ", raw).strip()
    
    # Mobile regex (Indian) - handles formats like "91 3333 2737", "+91 3333 2737", "3333 2737"
    # Pattern: optional country code (+91 or 91), then 6-9 followed by 9 more digits
    mobile_pattern = re.compile(r"(\+91[- ]?|91[- ]?)?[6-9]\d{2,3}[- ]?\d{6,7}$")
    # Landline with STD - handles formats like "0863 - 222 72 77", "0863-2227277", "040-23456789"
    # Pattern: optional 0, then 2-4 digit STD code, separator, then 6-8 digit local number
    landline_pattern = re.compile(r"^0?\d{2,4}[- ]?\d{2,3}[- ]?\d{4,5}$")
    # Short local landline (e.g., 3336255, 3333 2737) - 6-8 digits
    short_landline_pattern = re.compile(r"^\d{6,8}$")

    if mobile_pattern.search(normalized) or landline_pattern.search(normalized) or short_landline_pattern.fullmatch(normalized):
        return True

    # Fallback: if digits are 10 and start with valid mobile starting digit, accept
    if len(digits) == 10 and digits[0] in "6789":
        return True

    # Accept some 11+ digit numbers if they include leading 0 or country code and last 10 start with mobile digit
    if len(digits) in (11, 12) and digits[-10] in "6789":
        return True
    
    # Accept landline patterns: STD code (2-4 digits) + local number (6-8 digits) = 8-12 total digits
    # Check if it looks like a valid STD + local combination
    if 8 <= len(digits) <= 12:
        # For 8-10 digits: could be STD (2-4) + local (6-8)
        # For 11-12 digits: could be 0 + STD (2-4) + local (6-8) or country code + mobile
        # If it doesn't match mobile pattern above, check if it's a valid landline structure
        if len(digits) >= 8:
            # Check if first 2-4 digits could be STD code (typically starts with 0 for landlines)
            if digits[0] == '0' and 3 <= len(digits) <= 12:
                return True
            # Or if it's 8-10 digits total, likely STD + local
            if 8 <= len(digits) <= 10:
                return True

    return False


def normalize_key_for_count(e: dict) -> str:
    """
    Create a canonical key for counting occurrences across models.
    For phone numbers and phone-like types, use normalized last-10-digits (if available).
    For PERSON entities, remove common prefixes (Dr., Mr., Mrs., etc.) and trailing punctuation.
    Otherwise return lowercased stripped text.
    """
    if not e or "entity_type" not in e or "text" not in e:
        return ""
    etype = e["entity_type"]
    txt = e["text"]
    if etype in PHONE_LIKE_TYPES:
        digits = normalize_phone_digits(txt)
        if not digits:
            return ""
        # Prefer last-10 digits for matching (remove country code)
        if len(digits) > 10:
            return digits[-10:]
        return digits
    # For PERSON entities, normalize by removing prefixes and trailing punctuation
    if etype == "PERSON":
        # Remove common prefixes (case-insensitive)
        txt = re.sub(r'^(dr\.?|mr\.?|mrs\.?|ms\.?|miss\.?|prof\.?|professor|shri)\s+', '', txt, flags=re.IGNORECASE)
        # Remove common suffixes/honorifics
        txt = re.sub(r'\b(sir|jr\.?|sr\.?|ii|iii|iv)\b\.?$', '', txt, flags=re.IGNORECASE)
        # Replace dots in initials and remove trailing punctuation
        txt = re.sub(r'\.\s*', ' ', txt)
        txt = re.sub(r'[.,;:!?]+$', '', txt)
        txt = ' '.join(txt.split())
        return txt.lower().strip()
    return txt.lower().strip()


def looks_like_address(text: str) -> bool:
    """Heuristic check for address-like org/location spans."""
    if not text:
        return False
    cleaned = text.strip()
    if not cleaned:
        return False
    if cleaned.isupper() and len(cleaned) <= 3:
        return False
    upper = cleaned.upper()
    if any(keyword in upper for keyword in ADDRESS_KEYWORDS):
        return True
    if re.search(r"\b(BLOCK|SECTOR)\b", upper):
        return True
    if re.search(r"\b\d{6}\b", cleaned):
        return True
    if re.search(r"\b\d{2,}\b", cleaned) and any(ch.isalpha() for ch in cleaned):
        return True
    if any(ch.isdigit() for ch in cleaned) and "-" in cleaned:
        return True
    return False


# ---------- Medication-context heuristics (prevent medication being labeled PERSON) ----------
DOSAGE_PATTERN = re.compile(r'\b\d+\s*(?:mg|mcg|g|gm|ml|mL|IU|Units)\b', flags=re.IGNORECASE)
ROUTE_WORDS = {"IV", "IM", "PO", "SC", "TD", "OD", "BD", "SOS", "PRN", "TD", "SACHET", "INJ", "TAB", "CAP"}

def is_medicine_context(span_text: str, full_text: str, start: int, end: int) -> bool:
    """
    Heuristic: if the PERSON-labeled span is in close proximity to dosage tokens or route words,
    treat it as likely medication and return True (so it will be excluded from PERSON redaction).
    """
    if not span_text:
        return False
    # search within +/- 30 chars
    window = full_text[max(0, start - 30): min(len(full_text), end + 30)]
    if DOSAGE_PATTERN.search(window):
        return True
    if any(re.search(rf'\b{re.escape(route)}\b', window, flags=re.IGNORECASE) for route in ROUTE_WORDS):
        return True
    # sometimes the dosage appears immediately after span (e.g., "Tabi Thyronorm 15 mcg")
    if DOSAGE_PATTERN.search(span_text):
        return True
    return False


# ---------- Utility sanitizers ----------
def sanitize_entity(e: dict) -> dict:
    """Return a copy with helper keys removed and normalized types/scores."""
    e = dict(e)  # shallow copy
    for k in ("_labels", "_score_sum", "_score_count"):
        if k in e:
            del e[k]
    # Normalize entity_type and score
    e["entity_type"] = normalize_label(e.get("entity_type", ""))
    e["score"] = float(e.get("score", 0.0))
    # Ensure text is string
    e["text"] = str(e.get("text", ""))
    return e


def normalized_span_key(e: dict):
    """Return a dedupe key for spans (type, normalized text, start, end)."""
    return (e.get("entity_type"), normalize_key_for_count(e), e.get("start"), e.get("end"))


def to_recognizer_results(entities):
    return [RecognizerResult(e["entity_type"], e["start"], e["end"], e["score"]) for e in entities]


# MAIN PIPELINE EXECUTION
def main():
    print("[2/2] Running de-identification pipeline...")

    # Read input
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        text = f.read().strip()

    # --- Document / page metadata (single-page for now) ---
    # These can be overridden via environment variables when you later
    # extend to multi-page processing.
    doc_name = os.getenv("DOC_NAME", os.path.basename(INPUT_FILE))
    doc_id = os.getenv("DOC_ID", os.path.splitext(doc_name)[0])
    # For now, assume one page; caller can override PAGE_NUMBER when needed.
    page_number = int(os.getenv("PAGE_NUMBER", "1"))

    # --- Run Stanford model ---
    stanford_results = presidio_to_dict(stanford_analyzer.analyze(text, language="en"), text)

    # --- Run custom pattern detectors ---
    print("Running custom pattern detectors (postal codes, address numbers, age, gender/sex, abbreviated doctors)...")
    postal_code_results = detect_postal_codes(text)
    address_number_results = detect_address_numbers(text)
    age_results = detect_age_values(text)
    gender_sex_results = detect_gender_sex(text)
    # Get detected persons for abbreviated doctor name detection (Stanford only)
    all_persons = [
        e
        for e in stanford_results
        if normalize_label(e.get("entity_type", "")) == "PERSON"
    ]
    abbreviated_doctor_results = detect_abbreviated_doctor_names(text, all_persons)
    
    # Merge custom detections into Stanford results
    custom_results = postal_code_results + address_number_results + age_results + gender_sex_results + abbreviated_doctor_results
    for custom_entity in custom_results:
        # Normalize the entity
        custom_entity["entity_type"] = normalize_label(custom_entity.get("entity_type", ""))
        stanford_results.append(custom_entity.copy())

    # Save Stanford model output
    json.dump(stanford_results, open(os.path.join(OUTPUT_DIR, "stanford_output.json"), "w", encoding="utf-8"), indent=2)

    # --- Ensemble ---
    core_types = {
        "PERSON",
        "LOCATION",
        "ORGANIZATION",
        "DATE_TIME",
        "PHONE_NUMBER",
        "ID",
        "POSTAL_CODE",
        "ADDRESS_NUMBER",
    }
    ensembled = []

    # 1) Add non-core entity types from Stanford (no ensemble voting needed)
    for entity in stanford_results:
        etype = entity.get("entity_type")
        if etype in core_types:
            continue
        # Skip blacklisted types
        if etype in BLACKLISTED_TYPES:
            continue
        ensembled.append(sanitize_entity(entity))

    # 2) PERSON entities from Stanford only (with basic domain filters)
    existing_person_spans = set()

    def add_person_from_model(model_results, min_score: float = 0.0):
        for ent in model_results:
            raw_type = ent.get("entity_type", "")
            etype = normalize_label(raw_type)
            if etype != "PERSON":
                continue
            # Apply per-model score threshold (e.g., >= 0.5 for Stanford PERSON)
            if ent.get("score", 0.0) < min_score:
                continue
            entity = sanitize_entity(ent)
            span_text = entity.get("text", "")
            txt_upper = span_text.strip().upper()

            # Drop medical degrees (MD, MS, etc.)
            clean_txt = re.sub(r"[^\w]", "", txt_upper)
            if clean_txt in MEDICAL_DEGREE_BLACKLIST:
                continue

            # Drop drug names from whitelist
            if re.sub(r"[^\w\s]", "", span_text).strip().upper() in DRUG_NAME_WHITELIST:
                continue

            # Drop short all‑caps tokens (e.g., MD, CT)
            if txt_upper.isupper() and len(txt_upper) <= 4:
                continue

            # Drop PERSON spans that look like medications
            if is_medicine_context(span_text, text, entity.get("start", 0), entity.get("end", 0)):
                continue

            start, end = entity.get("start", 0), entity.get("end", 0)
            if any(overlap_fraction(start, end, ps, pe) > 0.5 for ps, pe in existing_person_spans):
                continue

            existing_person_spans.add((start, end))
            ensembled.append(entity)

    # PERSON from Stanford only (with score threshold >= 0.5)
    add_person_from_model(stanford_results, min_score=0.5)

    # 3) ID, PHONE_NUMBER, DATE_TIME, LOCATION, and ORGANIZATION entities from Stanford only
    existing_org_spans = set()

    facility_keywords = [
        "hospital", "clinic", "center", "centre", "diagnostic",
        "laboratory", "lab", "medical", "healthcare", "health",
        "market"
    ]
    existing_id_spans = set()
    existing_phone_spans = set()
    existing_datetime_spans = set()
    existing_location_spans = set()
    
    # Collect all phone number candidates first (including low-confidence ones)
    phone_candidates = []
    for ent in stanford_results:
        etype = normalize_label(ent.get("entity_type", ""))
        if etype == "PHONE_NUMBER":
            entity = sanitize_entity(ent)
            phone_candidates.append(entity)
    
    # Sort phone candidates: prefer longer spans, then higher scores
    # This ensures we prioritize complete phone numbers over partial ones
    phone_candidates.sort(key=lambda e: (
        -(e.get("end", 0) - e.get("start", 0)),  # Longer spans first (negative for descending)
        -e.get("score", 0.0)  # Higher scores first
    ))
    
    # Process phone numbers: prefer longer/more complete ones, use pattern validation for low-confidence
    for entity in phone_candidates:
        score = entity.get("score", 0.0)
        phone_text = entity.get("text", "").strip()
        
        # Accept if score >= 0.7 OR if it's a valid phone number pattern (even with low confidence)
        is_valid_pattern = is_valid_phone_number(phone_text)
        
        if score < 0.7 and not is_valid_pattern:
            continue
        
        span = (entity.get("start", 0), entity.get("end", 0))
        
        # Check for overlap with existing phone spans
        # If overlapping, prefer the longer/more complete one (already sorted)
        has_overlap = False
        for ps, pe in existing_phone_spans:
            if overlap_fraction(span[0], span[1], ps, pe) > 0.5:
                has_overlap = True
                break
        
        if not has_overlap:
            existing_phone_spans.add(span)
            ensembled.append(entity)
    
    # Process other entity types
    for ent in stanford_results:
        etype = normalize_label(ent.get("entity_type", ""))

        # IDs: Stanford only, threshold 0.75
        if etype == "ID":
            if ent.get("score", 0.0) < 0.75:
                continue
            entity = sanitize_entity(ent)
            span = (entity.get("start", 0), entity.get("end", 0))
            if any(overlap_fraction(span[0], span[1], ps, pe) > 0.5 for ps, pe in existing_id_spans):
                continue
            existing_id_spans.add(span)
            ensembled.append(entity)

        # DATE_TIME: Stanford only, threshold 0.7
        elif etype == "DATE_TIME":
            if ent.get("score", 0.0) < 0.7:
                continue
            entity = sanitize_entity(ent)
            span = (entity.get("start", 0), entity.get("end", 0))
            if any(overlap_fraction(span[0], span[1], ps, pe) > 0.5 for ps, pe in existing_datetime_spans):
                continue
            existing_datetime_spans.add(span)
            ensembled.append(entity)

        # LOCATION: Stanford only
        elif etype == "LOCATION":
            score = ent.get("score", 0.0)
            if score < 0.75:
                continue
            entity = sanitize_entity(ent)
            # Prefer address / facility-like or high-confidence locations
            text_lower = entity.get("text", "").lower()
            is_facility = any(kw in text_lower for kw in facility_keywords)
            if not (is_facility or looks_like_address(entity.get("text", "")) or score >= 0.75):
                continue
            span = (entity.get("start", 0), entity.get("end", 0))
            if any(overlap_fraction(span[0], span[1], ps, pe) > 0.5 for ps, pe in existing_location_spans):
                continue
            existing_location_spans.add(span)
            ensembled.append(entity)

        # ORGANIZATION: Stanford only
        elif etype == "ORGANIZATION":
            score = ent.get("score", 0.0)
            if score < 0.65:
                continue
            entity = sanitize_entity(ent)
            text_lower = entity.get("text", "").lower()
            is_facility = any(kw in text_lower for kw in facility_keywords)
            # Relaxed: accept any ORGANIZATION with score >= 0.7, even without facility/address heuristics
            if not (score >= 0.7 or is_facility or looks_like_address(entity.get("text", ""))):
                continue
            span = (entity.get("start", 0), entity.get("end", 0))
            if any(overlap_fraction(span[0], span[1], ps, pe) > 0.5 for ps, pe in existing_org_spans):
                continue
            existing_org_spans.add(span)
            ensembled.append(entity)

    # 5) POSTAL_CODE and ADDRESS_NUMBER from Stanford only
    existing_postal_spans = set()
    existing_address_spans = set()

    for ent in stanford_results:
        etype = normalize_label(ent.get("entity_type", ""))
        if etype not in {"POSTAL_CODE", "ADDRESS_NUMBER"}:
            continue
        entity = sanitize_entity(ent)
        # Optional mild score filter
        if entity.get("score", 0.0) < 0.6:
            continue
        span = (entity.get("start", 0), entity.get("end", 0))
        if etype == "POSTAL_CODE":
            if any(overlap_fraction(span[0], span[1], ps, pe) > 0.5 for ps, pe in existing_postal_spans):
                continue
            existing_postal_spans.add(span)
        else:  # ADDRESS_NUMBER
            if any(overlap_fraction(span[0], span[1], ps, pe) > 0.5 for ps, pe in existing_address_spans):
                continue
            existing_address_spans.add(span)
        ensembled.append(entity)

    # Extend DATE_TIME entities to include time portion (e.g., "20-Feb-2023 at 13:33")
    for entity in ensembled:
        if entity.get("entity_type") != "DATE_TIME":
            continue
        end_pos = entity.get("end", 0)
        if end_pos < len(text):
            remaining = text[end_pos:end_pos + 40]  # Look ahead 40 chars
            time_match = re.search(
                r'^\s*(?:at|@)?\s*\d{1,2}:\d{2}(?::\d{2})?(?:\s*(?:AM|PM|am|pm|hrs?|hr))?',
                remaining
            )
            if time_match:
                # Extend the entity to include the time portion
                entity["end"] = end_pos + time_match.end()
                entity["text"] = text[entity.get("start", 0):entity["end"]]

    # Deduplicate ensembled list (by normalized span key)
    deduped = []
    seen_keys = set()
    for e in ensembled:
        k = normalized_span_key(e)
        if k in seen_keys or k == (None, "", None, None):
            continue
        seen_keys.add(k)
        deduped.append(e)
    ensembled = deduped

    # Save final ensembled entities
    json.dump(ensembled, open(os.path.join(OUTPUT_DIR, "ensemble_entities.json"), "w", encoding="utf-8"), indent=2)

    # --- Redact using presidio anonymizer ---
    anonymizer = AnonymizerEngine()
    rec_results = to_recognizer_results(ensembled)
    dynamic_operators = {
        result.entity_type: OperatorConfig(
            operator_name="replace",
            params={"new_value": result.entity_type}
        )
        for result in rec_results
    }
    if "DEFAULT" not in dynamic_operators:
        dynamic_operators["DEFAULT"] = OperatorConfig(
            operator_name="replace",
            params={"new_value": "ENTITY"}
        )

    anonymized = anonymizer.anonymize(
        text=text,
        analyzer_results=rec_results,
        operators=dynamic_operators
    )

    # --- Save outputs ---
    # Ensure output folder exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_text_path = os.path.join(OUTPUT_DIR, "anonymized_output.txt")
    meta_data_path = os.path.join(OUTPUT_DIR, "ensemble_metadata.json")

    # Write anonymized text, fallback to input if empty
    anonymized_text = anonymized.text if anonymized.text else text
    with open(output_text_path, "w", encoding="utf-8") as f:
        f.write(anonymized_text)

    # Build simple page-wise, document-scoped metadata for re-identification.
    # For now we treat the whole input as a single page (page_1_*).
    entities_by_type = {}
    type_counters = {}
    for e in ensembled:
        etype = e.get("entity_type", "UNKNOWN")
        type_counters.setdefault(etype, 0)
        type_counters[etype] += 1
        entity_id = f"page_{page_number}_{etype}_{type_counters[etype]}"
        enriched = dict(e)
        enriched["entity_id"] = entity_id
        entities_by_type.setdefault(etype, []).append(enriched)

    metadata = {
        "input_file": INPUT_FILE,
        "doc_name": doc_name,
        "doc_id": doc_id,
        "page_number": page_number,
        "timestamp": datetime.now().isoformat(),
        "models": ["StanfordAIMI/stanford-deidentifier-base"],
        "total_entities_redacted": len(ensembled),
        # Flat entity list kept for backwards compatibility.
        "entities": ensembled,
        # Page-wise, document-scoped view for (future) multi-page re-identification.
        "pages": {
            str(page_number): {
                "entities_by_type": entities_by_type
            }
        }
    }

    json.dump(metadata, open(meta_data_path, "w", encoding="utf-8"), indent=2)

    print("\nPROCESS COMPLETE")
    print(f"-> Stanford model output saved in {OUTPUT_DIR}/stanford_output.json")
    print(f"-> Final entities in {OUTPUT_DIR}/ensemble_entities.json")
    print(f"-> Anonymized text: {OUTPUT_DIR}/anonymized_output.txt")
    print(f"-> Metadata: {OUTPUT_DIR}/ensemble_metadata.json")


# main function execution
if __name__ == "__main__":
    main()
