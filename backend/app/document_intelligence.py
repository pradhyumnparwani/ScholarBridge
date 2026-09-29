from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.models import Application, ApplicationDocument, BeneficiaryProfile, ScholarshipScheme, StudentProfile


def _number(value: str) -> float:
    return float(value.replace(",", "").replace("₹", "").strip())


def analyze_document(
    document_type: str,
    filename: str,
    content: bytes,
    profile: StudentProfile | None,
    application: Application,
    scheme: ScholarshipScheme,
) -> dict[str, Any]:
    """Offline, deterministic extraction used when no OCR provider is configured.

    The uploaded bytes are treated as text when possible; filenames also support
    predictable demo fixtures such as income_450000.pdf or wrong_name.pdf.
    """
    text = content.decode("utf-8", errors="ignore")
    source = f"{filename} {text}".lower()
    extracted: dict[str, Any] = {"document_type": document_type, "source": "offline-demo-extractor"}
    checks: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []

    expected_types = {
        "income_certificate": ("income", "income_certificate"),
        "marksheet": ("marksheet", "marks", "score"),
        "caste_certificate": ("caste", "tribal", "scheduled tribe"),
        "admission_proof": ("admission", "enrollment", "enrolment"),
    }
    type_terms = expected_types.get(document_type, (document_type,))
    if not any(term in source for term in type_terms):
        issues.append({"type": "Document type unclear", "reason": f"The uploaded file does not clearly identify itself as a {document_type.replace('_', ' ')}.", "action": f"Upload a readable {document_type.replace('_', ' ')} with its document heading visible."})

    applicant = application.beneficiary_profile or application.student_profile
    name = application.beneficiary_profile.full_name if application.beneficiary_profile else application.user.full_name if application.user else ""
    if "wrong_name" in source or "mismatch_name" in source:
        extracted["name"] = "Unmatched Applicant"
    else:
        extracted["name"] = name
    checks.append({"field": "name", "expected": name, "actual": extracted["name"], "passed": extracted["name"].casefold() == name.casefold()})
    if extracted["name"].casefold() != name.casefold():
        issues.append({"type": "Name mismatch", "reason": f"Document name '{extracted['name']}' does not match application profile '{name}'.", "action": "Upload a document issued to the applicant."})

    if document_type == "income_certificate":
        matches = re.findall(r"(?:income|rs\.?|₹)\s*[:=]?\s*([0-9][0-9,]{2,})", source, re.IGNORECASE)
        if matches:
            income = _number(matches[-1])
        else:
            income = profile.income if profile else None
        extracted["annual_income"] = income
        limit = next((float(rule.value) for rule in scheme.eligibility_rules if rule.field == "income" and rule.operator == "lte"), None)
        passed = income is not None and (limit is None or income <= limit)
        checks.append({"field": "annual_income", "expected": limit, "actual": income, "passed": passed})
        if income is None:
            issues.append({"type": "Missing information", "reason": "Required income field could not be verified.", "action": "Upload an income certificate with a readable annual income."})
        elif limit is not None and income > limit:
            issues.append({"type": "Eligibility mismatch", "reason": f"Extracted income Rs. {income:,.0f} exceeds the scheme limit of Rs. {limit:,.0f}.", "action": "Upload a current certificate within the scheme limit or review another scheme."})
    elif document_type == "marksheet":
        matches = re.findall(r"(?:percentage|marks|score)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)", source, re.IGNORECASE)
        percentage = float(matches[-1]) if matches else (profile.percentage if profile else None)
        extracted["percentage"] = percentage
        minimum = next((float(rule.value) for rule in scheme.eligibility_rules if rule.field == "percentage" and rule.operator == "gte"), None)
        passed = percentage is not None and (minimum is None or percentage >= minimum)
        checks.append({"field": "percentage", "expected": minimum, "actual": percentage, "passed": passed})
        if percentage is None:
            issues.append({"type": "Missing information", "reason": "Academic percentage could not be verified.", "action": "Upload a clear marksheet showing the final percentage or score."})
        elif minimum is not None and percentage < minimum:
            issues.append({"type": "Eligibility mismatch", "reason": f"Extracted score {percentage:g}% is below the required {minimum:g}%.", "action": "Upload the latest valid marksheet or review another scheme."})
    elif document_type == "caste_certificate":
        extracted["category"] = "ST" if any(term in source for term in ("st", "tribal", "scheduled tribe", "caste")) else (profile.category if profile else None)
        expected = next((rule.value for rule in scheme.eligibility_rules if rule.field == "category"), None)
        passed = extracted["category"] is not None and (expected is None or str(extracted["category"]).casefold() == str(expected).casefold())
        checks.append({"field": "category", "expected": expected, "actual": extracted["category"], "passed": passed})
        if extracted["category"] is None:
            issues.append({"type": "Missing information", "reason": "Required category could not be verified.", "action": "Upload a readable category certificate showing ST classification."})
        elif not passed:
            issues.append({"type": "Category mismatch", "reason": f"Document category '{extracted['category']}' does not match required category '{expected}'.", "action": "Upload the correct ST category certificate."})
    else:
        extracted["document_present"] = True
        checks.append({"field": "document_present", "expected": True, "actual": True, "passed": True})

    if issues:
        status = "Flagged for Review" if any(item["type"] == "Document type unclear" for item in issues) else "Mismatch Detected" if any(item["type"] in ("Name mismatch", "Eligibility mismatch", "Category mismatch") for item in issues) else "Missing Information"
    else:
        status = "AI Verified"
    return {"status": status, "extracted": extracted, "checks": checks, "issues": issues}


def serialize_analysis(result: dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=True)
