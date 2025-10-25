import re
import logging
from typing import Dict, List, Optional
from datetime import datetime

# Fallback local date parser if external utility is unavailable
try:
    from app.utils.date_parser import parse_date
except Exception:
    def parse_date(text: str) -> Optional[str]:
        if not text:
            return None
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d/%m/%y", "%d %B %Y", "%d %b %Y"):
            try:
                return datetime.strptime(text.strip(), fmt).strftime("%Y-%m-%d")
            except Exception:
                continue
        return None

logger = logging.getLogger(__name__)

# Configuration for optional LLM-based fallback extraction
try:
    from app.config import get_settings
    USE_LLM_EXTRACTION = get_settings().USE_LLM_EXTRACTION
except Exception:
    USE_LLM_EXTRACTION = False


def parse_claim(ocr_text: str) -> Dict:
    """
    Parse OCR text from a claim document into structured data fields.
    """
    text = _pre_clean(ocr_text)

    parsed = {
        "patient": _extract_patient_info(text),
        "diagnoses": _extract_diagnoses(text),
        "medications": _extract_medications(text),
        "procedures": _extract_procedures(text),
        "admission": _extract_admission(text),
        "total_amount": _extract_total_amount(text),
    }

    parsed = _validate_parsed(parsed)

    # Lightweight structured logging for debugging and validation
    try:
        pname = parsed.get("patient", {}).get("name", "") or "<no-name>"
        logger.info(
            "parse_claim: patient=%s | diagnoses=%d | meds=%d | procedures=%d",
            pname,
            len(parsed.get("diagnoses") or []),
            len(parsed.get("medications") or []),
            len(parsed.get("procedures") or []),
        )
    except Exception:
        pass

    # Optional fallback if all primary extraction returned empty
    if USE_LLM_EXTRACTION and not any(bool(v) for v in parsed.values()):
        try:
            parsed = _extract_with_llm(text)
        except Exception as e:
            logger.exception("Mock LLM extraction failed: %s", e)

    return parsed


def _pre_clean(text: str) -> str:
    """
    Remove boilerplate headers and reduce noise before extraction.
    """
    text = text or ""
    noise = ["POWERED BY SMART APPLICATIONS", "PREPARED BY", "PARTNER NAME", "NET VALUE"]
    for n in noise:
        text = re.sub(re.escape(n) + ".*", "", text, flags=re.I)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def _validate_parsed(parsed: Dict) -> Dict:
    """
    Prune common false positives from diagnoses and medication lists.
    """
    parsed["diagnoses"] = [
        d for d in parsed["diagnoses"]
        if len(d) > 2 and not d.isdigit()
    ]
    parsed["medications"] = [
        m for m in parsed["medications"]
        if m.get("name") and not m["name"].isdigit()
    ]
    return parsed


def _extract_patient_info(text: str) -> Dict:
    """
    Extract patient name and age fields, reducing noise from invoice labels.
    """
    name = ""
    age = None

    # Name search priority: Patient → Member → Generic label
    name_patterns = [
        r"Patient\s*Name[:\-\s]*([A-Z][A-Za-z' -]{2,}(?:\s+[A-Z][A-Za-z' -]{2,})?)",
        r"Member\s*Name[:\-\s]*([A-Z][A-Za-z' -]{2,}(?:\s+[A-Z][A-Za-z' -]{2,})?)",
        r"\bName[:\-\s]*([A-Z][A-Za-z' -]{2,})"
    ]

    for p in name_patterns:
        m = re.search(p, text, flags=re.I)
        if m:
            candidate = m.group(1).strip()
            # Avoid capturing invoice headers
            if not re.search(r"(invoice|scheme|insurer|value)", candidate, re.I):
                candidate = re.sub(r"\b(Patient|Member)\s*Name\b", "", candidate, flags=re.I).strip(" :-")
                name = candidate
                break

    # Simple age detection
    age_patterns = [r"Age[:\s]*([0-9]{1,3})", r"(\d{1,3})\s+years?\b"]
    for p in age_patterns:
        m = re.search(p, text, flags=re.I)
        if m:
            try:
                age = int(m.group(1))
                break
            except Exception:
                pass

    return {"name": name or "", "age": age}


def _extract_diagnoses(text: str) -> List[str]:
    """
    Identify short diagnosis lines between the diagnosis header and the next section.
    """
    diagnoses = []
    block = re.search(
        r"(?:Diagnosis\s*Details?|Diagnoses?)[:\s\n]*(.*?)"
        r"(?:(?:Total|Medications?|TREATMENT|Procedure|PREPARED BY|POWERED BY|$))",
        text, flags=re.I | re.S)
    if block:
        section = block.group(1)
        for ln in section.splitlines():
            ln = ln.strip(" .:\t")
            if not ln:
                continue
            if re.search(r"\b(ICD|code|amount|invoice|partner)\b", ln, re.I):
                continue
            if len(ln.split()) <= 6 and re.search(r"[A-Za-z]", ln):
                diagnoses.append(ln)
    return diagnoses


def _extract_medications(text: str) -> List[Dict]:
    """
    Identify drug lines by presence of dose units, then extract name, dosage, and quantity.
    """
    meds = []
    drug_lines = []

    for ln in text.splitlines():
        if re.search(r"\b(mg|ml|caps?|tab|tablet|syrup|cream)\b", ln, re.I):
            drug_lines.append(ln.strip())

    for ln in drug_lines:
        m = re.match(
            r"(?P<code>\d{4,}\s+)?(?P<name>[A-Za-z0-9'()/\s-]{3,40})\s+"
            r"(?P<dose>\d{1,4}\s*(?:mg|ml|mcg|g|%)?)\s+"
            r"(?P<qty>\d{1,3})?",
            ln)
        if m:
            meds.append({
                "name": m.group("name").strip(),
                "dosage": m.group("dose").strip(),
                "quantity": (m.group("qty") or "").strip()
            })

    return meds


def _extract_procedures(text: str) -> List[str]:
    """
    Extract procedure or treatment descriptions from tabular sections.
    """
    procs = []
    block = re.search(r"(TREATMENTS?|Procedures?)(.*?)(?:Diagnosis|Total|$)",
                      text, flags=re.I | re.S)
    if block:
        section = block.group(2)
        for ln in section.splitlines():
            ln = ln.strip()
            if re.search(r"Date|Description|Qty|Amount|Balance", ln, re.I):
                continue
            if re.search(r"[A-Za-z]{3,}", ln):
                clean = re.sub(r"^\d{4}-\d{2}-\d{2}[-:\s\d]*", "", ln)
                procs.append(clean.strip())
    return procs


def _extract_admission(text: str) -> Dict:
    """
    Determine admission status and extract any available admission or discharge dates.
    """
    was_admitted = bool(re.search(r"\badmission|admitted\b", text, re.I))
    admission_date = None
    discharge_date = None

    m1 = re.search(r"Admission Date[:\s\-]*([^\n,]+)", text, re.I)
    if m1:
        admission_date = parse_date(m1.group(1).strip())

    m2 = re.search(r"Discharge Date[:\s\-]*([^\n,]+)", text, re.I)
    if m2:
        discharge_date = parse_date(m2.group(1).strip())

    return {"was_admitted": was_admitted, "admission_date": admission_date, "discharge_date": discharge_date}


def _extract_total_amount(text: str) -> str:
    """
    Extract final total payable or settlement value, normalizing formatting.
    """
    patterns = [
        r"Total\s+Settlement[:\s]*([\d,]+\.\d{2})",
        r"Net\s+Value[:\s]*([\d,]+\.\d{2})",
        r"Total\s+Amount[:\s]*([\d,]+\.\d{2})"
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            return m.group(1).replace(",", "")
    return ""


def _extract_with_llm(text: str) -> Dict:
    """
    Lightweight pattern-based fallback that fills major fields when primary
    regex extraction fails. No external model call.
    """
    name = re.search(r"(?:Patient|Member)[:\s\-]+([A-Za-z ,.'-]{3,})", text, re.I)
    diagnosis = re.search(r"diagnos(?:is|es)?[:\-]?\s*([A-Za-z ,]+)", text, re.I)
    total = re.search(r"(₦|N|NGN)\s*[\d,]+(?:\.\d{2})?", text)
    procs = re.findall(r"(?:MRI|CT|X[-\s]?Ray|Scan|Test|Procedure|Treatment)[A-Za-z0-9\s]*", text, re.I)

    return {
        "patient": {"name": name.group(1).strip() if name else "Unknown", "age": None},
        "diagnoses": [diagnosis.group(1).strip()] if diagnosis else [],
        "medications": [],
        "procedures": list(set([p.strip() for p in procs if p.strip()])),
        "admission": {"was_admitted": "admit" in text.lower(), "admission_date": None, "discharge_date": None},
        "total_amount": total.group(0).strip() if total else "",
    }
