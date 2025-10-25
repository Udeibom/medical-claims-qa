import logging
import difflib
from typing import Dict

logger = logging.getLogger(__name__)

try:
    from app.config import get_settings
    USE_LLM_QA = get_settings().USE_LLM_QA
except Exception:
    USE_LLM_QA = False


def answer_question(parsed_doc: Dict, question: str) -> str:
    """
    Rule-based question answering engine for parsed claim JSON data.
    """
    if not parsed_doc or not isinstance(parsed_doc, dict):
        return "No document data available."

    q = (question or "").lower().strip()

    # Patient / Member Name
    if any(tok in q for tok in ("name", "patient", "member", "who")):
        patient = parsed_doc.get("patient", {})
        name = (patient.get("name") or "").strip()
        if name:
            name = name.replace("Member Name", "").strip(" :-")
            return f"The patient's name is {name}."
        return "No patient name was found in the document."

    # Total Amount / Payable
    if any(tok in q for tok in ("total", "amount", "payable", "grand total", "net value")):
        total = parsed_doc.get("total_amount")
        return total if total else "Total amount not found in document."

    # Medication Queries
    meds = parsed_doc.get("medications") or []
    if meds and any(tok in q for tok in ("drug", "medicine", "medication", "dose", "mg", "tablet", "capsule")):
        med_names = [m.get("name", "") for m in meds if m.get("name")]
        med_name_lower = [n.lower() for n in med_names]

        # Attempt fuzzy match
        found_med = None
        for i, name in enumerate(med_name_lower):
            if name and (name in q or difflib.SequenceMatcher(None, name, q).ratio() > 0.6):
                found_med = meds[i]
                break

        if found_med:
            if "how many" in q or "quantity" in q:
                return found_med.get("quantity") or "Quantity not specified."
            if "dosage" in q or "mg" in q or "ml" in q:
                return found_med.get("dosage") or "Dosage not specified."
            return f"{found_med.get('name')} ({found_med.get('dosage') or 'no dosage info'})"

        med_list = ", ".join(med_names)
        return f"Medications mentioned: {med_list}" if med_list else "No medications found in document."

    # Diagnosis Queries
    if any(tok in q for tok in ("diagnos", "condition", "disease")):
        dx = parsed_doc.get("diagnoses") or []
        return ", ".join(dx) if dx else "No diagnosis found in document."

    # Procedures / Tests
    if any(tok in q for tok in ("procedure", "treatment", "test", "investigation", "scan")):
        procs = parsed_doc.get("procedures") or []
        return ", ".join(procs) if procs else "No procedures found in document."

    # Admission Queries
    if any(tok in q for tok in ("admit", "admission", "discharge", "inpatient", "hospitalized")):
        adm = parsed_doc.get("admission") or {}
        if adm.get("was_admitted"):
            return (
                f"Patient was admitted on {adm.get('admission_date') or 'unknown'} "
                f"and discharged on {adm.get('discharge_date') or 'unknown'}."
            )
        return "Patient was not admitted."

    # Fallback LLM-like response
    if USE_LLM_QA:
        return _generate_answer_from_llm(parsed_doc, question)

    return "I could not find an answer in the document."


def _generate_answer_from_llm(parsed_doc: Dict, question: str) -> str:
    """
    Context-based fallback that synthesizes a natural language answer from document data.
    No external model call is performed.
    """
    logger.info("Using mock LLM QA fallback.")

    context = []

    patient_name = parsed_doc.get("patient", {}).get("name")
    if patient_name:
        context.append(f"the patient was {patient_name}")

    diagnoses = parsed_doc.get("diagnoses")
    if diagnoses:
        context.append(f"diagnosed with {', '.join(diagnoses)}")

    procedures = parsed_doc.get("procedures")
    if procedures:
        context.append(f"procedures done: {', '.join(procedures)}")

    total = parsed_doc.get("total_amount")
    if total:
        context.append(f"total amount was {total}")

    if not context:
        return "Based on available data, no relevant information could be inferred."

    return "Based on the document, " + "; ".join(context) + "."
