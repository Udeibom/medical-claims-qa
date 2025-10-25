from typing import List, Optional, Dict
from pydantic import BaseModel


# ---- Patient / Admission / Medication submodels ----
class Patient(BaseModel):
    name: Optional[str] = ""
    age: Optional[int] = None


class Medication(BaseModel):
    name: str
    dosage: Optional[str] = ""
    quantity: Optional[str] = ""


class Admission(BaseModel):
    was_admitted: bool = False
    admission_date: Optional[str] = None
    discharge_date: Optional[str] = None


# ---- Parsed Claim ----
class ParsedClaim(BaseModel):
    patient: Patient
    diagnoses: List[str]
    medications: List[Medication]
    procedures: List[str]
    admission: Admission
    total_amount: Optional[str] = ""


# ---- API models ----
class ExtractResponse(BaseModel):
    document_id: str
    parsed: ParsedClaim


class AskRequest(BaseModel):
    document_id: str
    question: str


class AskResponse(BaseModel):
    answer: str
