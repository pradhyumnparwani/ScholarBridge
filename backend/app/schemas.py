from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: str = "student"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class StudentProfileCreate(BaseModel):
    category: str = "ST"
    income: float = 0
    age: int = 0
    education_level: str = "UG"
    course: str = "B.Tech"
    percentage: float = 0
    phone: str | None = None
    state: str | None = None
    district: str | None = None


class BeneficiaryProfileCreate(BaseModel):
    full_name: str
    age: int = 0
    category: str = "ST"
    income: float = 0
    education_level: str = "UG"
    course: str = "B.Tech"
    percentage: float = 0
    institution: str | None = None
    state: str | None = None
    district: str | None = None
    relationship_to_applicant: str | None = None


class ScholarshipBase(BaseModel):
    name: str
    level: str
    benefit: str
    description: str | None = None
    deadline: date


class EligibilityRuleValue(BaseModel):
    field: str
    operator: str
    value: str
    description: str


class ScholarshipCreate(ScholarshipBase):
    rules: list[EligibilityRuleValue] = []
    required_documents: list[str] = []


class ScholarshipOut(ScholarshipBase):
    id: int
    slug: str
    is_active: bool


class ApplicationCreate(BaseModel):
    scheme_id: int
    student_profile_id: int | None = None
    beneficiary_profile_id: int | None = None
    applicant_type: str = "self"
    relationship_to_applicant: str | None = None

class ApplicationApplicantUpdate(BaseModel):
    student_profile_id: int | None = None
    beneficiary_profile_id: int | None = None
    applicant_type: str = "self"
    relationship_to_applicant: str | None = None


class OfficerDocumentReview(BaseModel):
    status: str
    notes: str | None = None


class OfficerDeficiencyCreate(BaseModel):
    document_id: int | None = None
    field: str
    deficiency_type: str
    reason: str
    explanation: str
    required_action: str
    severity: str = "Medium"


class OfficerDecision(BaseModel):
    status: str
    comment: str | None = None


class ApplicationDocumentCreate(BaseModel):
    document_type: str
    filename: str
    file_path: str
    extracted_text: str | None = None
    classification: str | None = None


class EligibilityEvaluation(BaseModel):
    eligible: bool
    checks: list[dict]
    summary: str


class NotificationOut(BaseModel):
    id: int
    title: str
    message: str
    is_read: bool
    created_at: datetime


class DeficiencyOut(BaseModel):
    id: int
    title: str
    description: str
    severity: str
    created_at: datetime


class ApplicationOut(BaseModel):
    id: int
    status: str
    scheme_id: int
    user_id: int
    eligibility_result: str | None = None
    summary: str | None = None
    created_at: datetime
