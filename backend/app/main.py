from __future__ import annotations

from pathlib import Path
import json
import re
from datetime import datetime, date
from urllib.request import Request, urlopen

from fastapi import FastAPI, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text

from app.auth import get_current_user, require_role
from app.database import Base, SessionLocal, engine, get_db
from app.document_intelligence import analyze_document, serialize_analysis
from app.models import Application, ApplicationDocument, ApplicationStatusHistory, BeneficiaryProfile, Deficiency, EligibilityRule, Notification, RequiredDocument, ScholarshipScheme, StudentProfile, User
from app.schemas import (
    ApplicationCreate,
    ApplicationApplicantUpdate,
    BeneficiaryProfileCreate,
    ScholarshipCreate,
    StudentProfileCreate,
    Token,
    UserCreate,
    UserLogin,
    OfficerDecision,
    OfficerDeficiencyCreate,
    OfficerDocumentReview,
)
from app.seed import seed_database
from app.utils import create_access_token, hash_password, verify_password

Base.metadata.create_all(bind=engine)


def ensure_phase3_columns() -> None:
    additions = {
        "application_documents": {
            "extracted_data": "TEXT",
            "verification_summary": "TEXT",
        },
        "deficiencies": {
            "document_id": "INTEGER",
            "field": "VARCHAR(100)",
            "deficiency_type": "VARCHAR(100)",
            "reason": "TEXT",
            "required_action": "TEXT",
            "status": "VARCHAR(50) DEFAULT 'Open'",
        },
        "scholarship_schemes": {
            "source_name": "VARCHAR(255)",
            "source_url": "VARCHAR(500)",
            "academic_year": "VARCHAR(20)",
            "last_verified_at": "DATETIME",
            "source_status": "VARCHAR(50) DEFAULT 'official'",
        },
        "applications": {
            "beneficiary_profile_id": "INTEGER",
            "applicant_type": "VARCHAR(30) DEFAULT 'self'",
            "relationship_to_applicant": "VARCHAR(100)",
        },
    }
    with engine.begin() as connection:
        for table, columns in additions.items():
            existing = {column["name"] for column in inspect(engine).get_columns(table)}
            for column, definition in columns.items():
                if column not in existing:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))


ensure_phase3_columns()

NSP_URL = "https://scholarships.gov.in/All-Scholarships"

# Migrate the original fictional demo records to traceable official schemes.
def migrate_demo_schemes() -> None:
    with SessionLocal() as db:
        first = db.query(ScholarshipScheme).filter(ScholarshipScheme.slug == "tribal-higher-education-support-scheme").first()
        if first:
            first.name = "National Fellowship and Scholarship for Higher Education of ST Students - Scholarship"
            first.slug = "national-fellowship-and-scholarship-for-higher-education-of-st-students-scholarship"
            first.level = "Higher Education"
            first.benefit = "See official scheme details"
            first.description = "Official Ministry of Tribal Affairs / National Scholarship Portal scheme for higher education of ST students."
            first.deadline = date(2026, 10, 31)
            first.source_name = "National Scholarship Portal (NSP)"
            first.source_url = NSP_URL if "NSP_URL" in globals() else "https://scholarships.gov.in/All-Scholarships"
            first.academic_year = "2026-27"
            first.source_status = "official"
        second = db.query(ScholarshipScheme).filter(ScholarshipScheme.slug == "post-matric-scholarship-for-st-students").first()
        if second:
            second.name = "Post-Matric Scholarship Scheme for ST Students"
            second.slug = "post-matric-scholarship-scheme-for-st-students"
            second.level = "Post-Matric"
            second.benefit = "See official scheme details"
            second.description = "Official Ministry of Tribal Affairs centrally sponsored Post-Matric Scholarship scheme for ST students."
            second.deadline = date(2026, 10, 31)
            second.source_name = "Ministry of Tribal Affairs"
            second.source_url = "https://tribal.nic.in/ScholarshiP.aspx"
            second.academic_year = "2026-27"
            second.source_status = "official"
        db.commit()

migrate_demo_schemes()
MOTA_URL = "https://tribal.nic.in/ScholarshiP.aspx"

def fetch_nsp_schemes() -> list[dict]:
    """Read current public NSP scheme listings from the official page.

    The NSP page is a table/listing page. Parse each row independently so
    verification dates, FAQ text, and the next scheme cannot be swallowed
    into a scheme name.
    """
    request = Request(
        NSP_URL,
        headers={"User-Agent": "ScholarBridge/1.0 (official-source-sync)"},
    )

    with urlopen(request, timeout=12) as response:
        html = response.read().decode("utf-8", errors="ignore")

    def clean_html(value: str) -> str:
        value = re.sub(r"<script\b[^>]*>.*?</script>", " ", value, flags=re.I | re.S)
        value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
        value = re.sub(r"<br\s*/?>", " ", value, flags=re.I)
        value = re.sub(r"<[^>]+>", " ", value)
        value = re.sub(r"&nbsp;|&#160;", " ", value, flags=re.I)
        value = re.sub(r"&amp;", "&", value, flags=re.I)
        value = re.sub(r"&quot;", '"', value, flags=re.I)
        value = re.sub(r"&#39;|&apos;", "'", value, flags=re.I)
        value = re.sub(r"\s+", " ", value)
        return value.strip()

    def valid_name(value: str) -> bool:
        value = clean_html(value).strip(" -|:")
        lowered = value.casefold()

        if not (15 <= len(value) <= 300):
            return False

        blocked = (
            "student application open till",
            "defective application verification",
            "institute verification",
            "dno/sno/mno verification",
            "specifications faq",
            "login",
            "register",
            "academic year",
            "scheme name",
        )
        if any(marker in lowered for marker in blocked):
            return False

        return any(
            marker in lowered
            for marker in ("scholarship", "fellowship", "scheme")
        )

    rows = re.findall(
        r"<tr\b[^>]*>(.*?)</tr\s*>",
        html,
        flags=re.I | re.S,
    )

    results: list[dict] = []

    for row in rows:
        row_text = clean_html(row)
        if not row_text:
            continue

        deadline_match = re.search(
            r"Student\s+Application\s+Open\s+till\s*:?\s*(\d{2}-\d{2}-\d{4})",
            row_text,
            flags=re.I,
        )
        if not deadline_match:
            continue

        try:
            deadline = date.fromisoformat(
                "-".join(reversed(deadline_match.group(1).split("-")))
            )
        except ValueError:
            continue

        anchors = re.findall(
            r"<a\b[^>]*>(.*?)</a\s*>",
            row,
            flags=re.I | re.S,
        )
        candidates = [clean_html(item) for item in anchors]

        if not candidates:
            candidates = [
                clean_html(item)
                for item in re.findall(
                    r"<(?:td|th)\b[^>]*>(.*?)</(?:td|th)\s*>",
                    row,
                    flags=re.I | re.S,
                )
            ]

        name = next((item for item in candidates if valid_name(item)), None)

        if not name:
            for candidate in candidates:
                pieces = re.split(
                    r"(?=Student\s+Application\s+Open\s+till|"
                    r"Defective\s+Application\s+Verification|"
                    r"Institute\s+Verification|"
                    r"DNO/SNO/MNO\s+Verification|"
                    r"Specifications\s+FAQ)",
                    candidate,
                    flags=re.I,
                )
                for piece in pieces:
                    piece = clean_html(piece)
                    if valid_name(piece):
                        name = piece
                        break
                if name:
                    break

        if not name:
            continue

        name = re.sub(r"\s+", " ", name).strip(" -|:")
        results.append({"name": name, "deadline": deadline})

    unique: dict[str, dict] = {}
    for item in results:
        key = re.sub(r"[^a-z0-9]+", " ", item["name"].casefold()).strip()
        if key:
            unique[key] = item

    return list(unique.values())


def sync_official_scholarships(db: Session) -> dict:
    """Refresh official scheme metadata from NSP and keep source provenance visible."""
    now = datetime.utcnow()

    try:
        live = fetch_nsp_schemes()
    except Exception as exc:
        db.rollback()
        return {
            "ok": False,
            "source": NSP_URL,
            "error": str(exc),
            "updated": 0,
            "checked_at": now.isoformat(),
        }

    updated = 0
    existing = db.query(ScholarshipScheme).all()

    by_name = {
        re.sub(r"[^a-z0-9]+", " ", (scheme.name or "").casefold()).strip(): scheme
        for scheme in existing
    }
    by_slug = {scheme.slug: scheme for scheme in existing if scheme.slug}
    seen_slugs: set[str] = set()

    for item in live:
        name = re.sub(r"\s+", " ", item["name"]).strip()
        name_key = re.sub(r"[^a-z0-9]+", " ", name.casefold()).strip()

        if not name_key:
            continue

        scheme = by_name.get(name_key)

        slug_base = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")[:220]
        slug = slug_base or f"nsp-{updated + 1}"

        slug_owner = by_slug.get(slug)
        if scheme is None and slug_owner is not None:
            scheme = slug_owner

        if scheme is None:
            if slug in seen_slugs:
                continue

            scheme = ScholarshipScheme(
                name=name,
                slug=slug,
                level="See official scheme",
                benefit="See official scheme",
                description=(
                    "Current scheme listed by the National Scholarship Portal. "
                    "Eligibility and benefits should be verified against the "
                    "official scheme details before applying."
                ),
                deadline=item["deadline"],
                is_active=item["deadline"] >= date.today(),
            )
            db.add(scheme)
            by_name[name_key] = scheme
            by_slug[slug] = scheme
        else:
            if not scheme.slug:
                candidate = slug
                suffix = 2
                while candidate in by_slug:
                    candidate = f"{slug[: max(1, 220 - len(str(suffix)) - 1)]}-{suffix}"
                    suffix += 1
                scheme.slug = candidate
                by_slug[candidate] = scheme

            scheme.name = name
            scheme.deadline = item["deadline"]
            scheme.is_active = item["deadline"] >= date.today()

        seen_slugs.add(scheme.slug)

        scheme.source_name = "National Scholarship Portal (NSP)"
        scheme.source_url = NSP_URL
        scheme.academic_year = "2026-27"
        scheme.last_verified_at = now
        scheme.source_status = "official"
        updated += 1

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        return {
            "ok": False,
            "source": NSP_URL,
            "error": str(exc),
            "updated": 0,
            "checked_at": now.isoformat(),
        }

    return {
        "ok": True,
        "source": NSP_URL,
        "academic_year": "2026-27",
        "updated": updated,
        "checked_at": now.isoformat(),
    }


app = FastAPI(title="Scholar Bridge API", version="1.0.0")
UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
# Frontend origins allowed to call the API.
# Keep local development explicit and also allow Vercel deployments.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_origin_regex=r"https://([a-zA-Z0-9-]+\.)*vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    db = SessionLocal()
    try:
        seed_database(db)

        # Remove legacy demo applications from the old local prototype.
        # Real applications are created only when a signed-in user starts one.
        cleanup_legacy_demo_applications(db)

        # The official NSP sync is optional. A temporary network/DNS/SSL
        # problem must never prevent the local API from starting.
        try:
            sync_result = sync_official_scholarships(db)
            if not sync_result.get("ok"):
                db.rollback()
        except Exception:
            db.rollback()

        # Backfill is also best-effort so one malformed legacy record cannot
        # take the entire API offline during startup.
        try:
            backfill_document_intelligence(db)
        except Exception:
            db.rollback()
    finally:
        db.close()


def cleanup_legacy_demo_applications(db: Session) -> None:
    demo_user = db.query(User).filter(User.email == "student@scholarshipsetu.demo").first()
    if not demo_user:
        return
    applications = db.query(Application).filter(Application.user_id == demo_user.id).all()
    for application in applications:
        for document in list(application.documents):
            db.delete(document)
        for deficiency in list(application.deficiencies):
            db.delete(deficiency)
        for history in list(application.status_history):
            db.delete(history)
        db.delete(application)
    for notification in db.query(Notification).filter(Notification.user_id == demo_user.id).all():
        db.delete(notification)
    db.commit()


def add_notification(db: Session, user_id: int, title: str, message: str) -> None:
    db.add(Notification(user_id=user_id, title=title, message=message))


def backfill_document_intelligence(db: Session) -> None:
    for document in db.query(ApplicationDocument).filter(ApplicationDocument.extracted_data.is_(None)).all():
        application = db.query(Application).filter(Application.id == document.application_id).first()
        if not application or not application.scheme:
            continue
        result = analyze_document(document.document_type, document.filename, (document.extracted_text or "").encode(), application.beneficiary_profile or application.student_profile, application, application.scheme)
        document.extracted_data = serialize_analysis(result)
        document.verification_summary = "; ".join(item["reason"] for item in result["issues"]) or "Offline checks passed."
        if document.verification_status in (None, "Pending"):
            document.verification_status = result["status"]
        for issue in result["issues"]:
            if not db.query(Deficiency).filter(Deficiency.application_id == application.id, Deficiency.document_id == document.id, Deficiency.status == "Open").first():
                db.add(Deficiency(application_id=application.id, document_id=document.id, field=issue["type"], deficiency_type=issue["type"], title=f"{document.filename} — {issue['type']}", description=issue["reason"], reason=issue["reason"], required_action=issue["action"], severity="High"))
    for deficiency in db.query(Deficiency).filter(Deficiency.status == "Open").all():
        if deficiency.required_action:
            continue
        deficiency.field = deficiency.field or "income_certificate"
        deficiency.deficiency_type = deficiency.deficiency_type or "Missing Document"
        deficiency.reason = deficiency.reason or deficiency.description
        deficiency.required_action = "Upload the latest income certificate with the financial year declaration."
        application = deficiency.application
        if application and application.status == "Under Verification":
            application.status = "Deficiency Raised"
            db.add(ApplicationStatusHistory(application_id=application.id, status="Deficiency Raised", comment="A required document needs correction."))
    db.commit()


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "Scholar Bridge API"}


@app.post("/api/auth/register", response_model=Token)
def register_user(user_data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=user_data.email,
        full_name=user_data.full_name,
        password_hash=hash_password(user_data.password),
        role=user_data.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    access_token = create_access_token(user.id)
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/api/auth/login", response_model=Token)
def login_user(user_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_data.email).first()
    if not user or not verify_password(user_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token = create_access_token(user.id)
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/api/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
    }


@app.get("/api/students/profile")
def get_student_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        return {}
    return profile.__dict__


@app.post("/api/students/profile")
def create_student_profile(profile_data: StudentProfileCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if profile:
        for field, value in profile_data.model_dump().items():
            setattr(profile, field, value)
        db.commit()
        return profile

    profile = StudentProfile(user_id=current_user.id, **profile_data.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@app.post("/api/beneficiaries")
def create_beneficiary(profile_data: BeneficiaryProfileCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    beneficiary = BeneficiaryProfile(owner_user_id=current_user.id, **profile_data.model_dump())
    db.add(beneficiary)
    db.commit()
    db.refresh(beneficiary)
    return beneficiary_payload(beneficiary)


@app.get("/api/beneficiaries")
def list_beneficiaries(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [beneficiary_payload(item) for item in db.query(BeneficiaryProfile).filter(BeneficiaryProfile.owner_user_id == current_user.id).order_by(BeneficiaryProfile.id.desc()).all()]


def beneficiary_payload(beneficiary: BeneficiaryProfile) -> dict:
    return {"id": beneficiary.id, "full_name": beneficiary.full_name, "age": beneficiary.age, "category": beneficiary.category, "income": beneficiary.income, "education_level": beneficiary.education_level, "course": beneficiary.course, "percentage": beneficiary.percentage, "institution": beneficiary.institution, "state": beneficiary.state, "district": beneficiary.district, "relationship_to_applicant": beneficiary.relationship_to_applicant}


@app.get("/api/scholarships")
def list_scholarships(db: Session = Depends(get_db)):
    scholarships = db.query(ScholarshipScheme).all()
    return [
        {
            "id": scheme.id,
            "name": scheme.name,
            "slug": scheme.slug,
            "level": scheme.level,
            "benefit": scheme.benefit,
            "description": scheme.description,
            "deadline": scheme.deadline.isoformat(),
            "is_active": scheme.is_active,
            "source_name": scheme.source_name,
            "source_url": scheme.source_url,
            "academic_year": scheme.academic_year,
            "last_verified_at": scheme.last_verified_at.isoformat() if scheme.last_verified_at else None,
            "source_status": scheme.source_status,
        }
        for scheme in scholarships
    ]



@app.post("/api/scholarships/sync")
def sync_scholarships(current_user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    return sync_official_scholarships(db)

@app.get("/api/scholarships/{scheme_id}")
def get_scholarship(scheme_id: int, db: Session = Depends(get_db)):
    scheme = db.query(ScholarshipScheme).filter(ScholarshipScheme.id == scheme_id).first()
    if not scheme:
        raise HTTPException(status_code=404, detail="Scholarship not found")

    return {
        "id": scheme.id,
        "name": scheme.name,
        "slug": scheme.slug,
        "level": scheme.level,
        "benefit": scheme.benefit,
        "description": scheme.description,
        "deadline": scheme.deadline.isoformat(),
        "source_name": scheme.source_name,
        "source_url": scheme.source_url,
        "academic_year": scheme.academic_year,
        "last_verified_at": scheme.last_verified_at.isoformat() if scheme.last_verified_at else None,
        "source_status": scheme.source_status,
        "rules": [
            {"id": rule.id, "field": rule.field, "operator": rule.operator, "value": rule.value, "description": rule.description}
            for rule in scheme.eligibility_rules
        ],
        "required_documents": [
            {"id": doc.id, "document_type": doc.document_type, "label": doc.label, "required": doc.required}
            for doc in scheme.required_documents
        ],
    }


@app.post("/api/scholarships")
def create_scholarship(scheme: ScholarshipCreate, current_user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    slug = scheme.name.lower().replace(" ", "-")
    existing = db.query(ScholarshipScheme).filter(ScholarshipScheme.slug == slug).first()
    if existing:
        slug = f"{slug}-{existing.id}"

    new_scheme = ScholarshipScheme(
        name=scheme.name,
        slug=slug,
        level=scheme.level,
        benefit=scheme.benefit,
        description=scheme.description,
        deadline=scheme.deadline,
    )
    db.add(new_scheme)
    db.commit()
    db.refresh(new_scheme)

    for rule in scheme.rules:
        db.add(
            __import__("app.models", fromlist=["EligibilityRule"]).EligibilityRule(
                scheme_id=new_scheme.id,
                field=rule.field,
                operator=rule.operator,
                value=rule.value,
                description=rule.description,
            )
        )

    for doc in scheme.required_documents:
        db.add(
            __import__("app.models", fromlist=["RequiredDocument"]).RequiredDocument(
                scheme_id=new_scheme.id,
                document_type=doc,
                label=doc,
                required=True,
            )
        )

    db.commit()
    return {"id": new_scheme.id, "slug": new_scheme.slug, "name": new_scheme.name}


@app.post("/api/eligibility/check")
def evaluate_eligibility(scheme_id: int, beneficiary_id: int | None = None, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if beneficiary_id:
        profile = db.query(BeneficiaryProfile).filter(BeneficiaryProfile.id == beneficiary_id, BeneficiaryProfile.owner_user_id == current_user.id).first()
        if not profile:
            raise HTTPException(404, "Beneficiary profile not found")
    scheme = db.query(ScholarshipScheme).filter(ScholarshipScheme.id == scheme_id).first()
    if not profile:
        raise HTTPException(404, "Student profile not found")
    if not scheme:
        raise HTTPException(404, "Scholarship not found")

    checks = []
    eligible = True
    for rule in scheme.eligibility_rules:
        field_value = getattr(profile, rule.field, None)
        passed = False
        if rule.operator == "equals" and str(field_value).lower() == str(rule.value).lower():
            passed = True
        elif rule.operator in ("not equals", "not_equals") and str(field_value).lower() != str(rule.value).lower():
            passed = True
        elif rule.operator == "gte" and field_value is not None and float(field_value) >= float(rule.value):
            passed = True
        elif rule.operator in ("gt", "greater than") and field_value is not None and float(field_value) > float(rule.value):
            passed = True
        elif rule.operator == "lte" and field_value is not None and float(field_value) <= float(rule.value):
            passed = True
        elif rule.operator in ("lt", "less than") and field_value is not None and float(field_value) < float(rule.value):
            passed = True
        elif rule.operator == "in" and field_value is not None and str(field_value).lower() in [item.strip().lower() for item in str(rule.value).split(",")]:
            passed = True

        checks.append({
            "rule": rule.description,
            "passed": passed,
            "field": rule.field,
            "value": rule.value,
            "actual": field_value,
            "explanation": (
                f"Applicant value {field_value} satisfies the {rule.operator} requirement of {rule.value}."
                if passed
                else f"Applicant value {field_value if field_value is not None else 'not provided'} does not satisfy the {rule.operator} requirement of {rule.value}."
            ),
        })
        if not passed:
            eligible = False

    summary = "ELIGIBLE" if eligible else "NOT ELIGIBLE"
    return {
        "eligible": eligible,
        "checks": checks,
        "summary": summary,
    }


@app.get("/api/applications")
def list_applications(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role == "admin":
        applications = db.query(Application).all()
    else:
        applications = db.query(Application).filter(Application.user_id == current_user.id).all()
    return [
        {
            "id": app.id,
            "status": app.status,
            "scheme_id": app.scheme_id,
            "title": app.scheme.name if app.scheme else "",
            "summary": app.summary,
            "deficiencies": len([item for item in app.deficiencies if item.status == "Open"]),
            "documents_total": len(app.documents),
            "documents_verified": len([item for item in app.documents if item.verification_status in ("AI Verified", "Verified")]),
        }
        for app in applications
    ]


@app.post("/api/applications")
def create_application(application_data: ApplicationCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    scheme = db.query(ScholarshipScheme).filter(ScholarshipScheme.id == application_data.scheme_id).first()
    if not scheme:
        raise HTTPException(404, "Scholarship not found")

    beneficiary = None
    if application_data.applicant_type == "beneficiary":
        beneficiary = db.query(BeneficiaryProfile).filter(BeneficiaryProfile.id == application_data.beneficiary_profile_id, BeneficiaryProfile.owner_user_id == current_user.id).first()
        if not beneficiary:
            raise HTTPException(400, "Beneficiary profile is required")
    application = Application(
        user_id=current_user.id,
        scheme_id=scheme.id,
        student_profile_id=None if beneficiary else (application_data.student_profile_id or (current_user.student_profile.id if current_user.student_profile else None)),
        beneficiary_profile_id=beneficiary.id if beneficiary else None,
        applicant_type=application_data.applicant_type,
        relationship_to_applicant=application_data.relationship_to_applicant,
        status="Draft",
        summary="Application created.",
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    db.add(ApplicationStatusHistory(application_id=application.id, status="Draft", comment="Application started."))
    db.commit()
    return {"id": application.id, "status": application.status}


@app.get("/api/applications/{application_id}")
def get_application(application_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise HTTPException(404, "Application not found")
    if current_user.role != "admin" and application.user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed")

    return {
        "id": application.id,
        "status": application.status,
        "scheme_id": application.scheme_id,
        "title": application.scheme.name if application.scheme else "",
        "applicant_type": application.applicant_type,
        "relationship_to_applicant": application.relationship_to_applicant,
        "beneficiary": beneficiary_payload(application.beneficiary_profile) if application.beneficiary_profile else None,
        "summary": application.summary,
        "eligibility_result": application.eligibility_result,
        "documents": [
            {
                "id": document.id,
                "document_type": document.document_type,
                "filename": document.filename,
                "verification_status": document.verification_status,
                "verification_summary": document.verification_summary,
                "extracted_data": json.loads(document.extracted_data) if document.extracted_data else None,
                "created_at": document.created_at.isoformat(),
            }
            for document in application.documents
        ],
        "deficiencies": [
            {
                "id": item.id,
                "title": item.title,
                "description": item.description,
                "severity": item.severity,
                "field": item.field,
                "deficiency_type": item.deficiency_type,
                "reason": item.reason or item.description,
                "required_action": item.required_action,
                "status": item.status,
                "created_at": item.created_at.isoformat(),
            }
            for item in application.deficiencies
        ],
        "timeline": [
            {"id": item.id, "status": item.status, "comment": item.comment, "created_at": item.created_at.isoformat()}
            for item in sorted(application.status_history, key=lambda history: history.created_at)
        ],
    }


@app.patch("/api/applications/{application_id}/applicant")
def attach_beneficiary(
    application_id: int,
    payload: ApplicationApplicantUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise HTTPException(404, "Application not found")
    if current_user.role != "admin" and application.user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed")
    if application.status not in ("Draft", "Deficiency Raised", "Correction Submitted"):
        raise HTTPException(400, "The applicant can only be changed while the application is still being corrected or drafted.")

    beneficiary = db.query(BeneficiaryProfile).filter(
        BeneficiaryProfile.id == payload.beneficiary_profile_id,
        BeneficiaryProfile.owner_user_id == current_user.id,
    ).first()
    if not beneficiary:
        raise HTTPException(404, "Beneficiary profile not found")

    application.student_profile_id = None
    application.beneficiary_profile_id = beneficiary.id
    application.applicant_type = "beneficiary"
    application.relationship_to_applicant = beneficiary.relationship_to_applicant
    application.status = "Correction Submitted"
    db.add(ApplicationStatusHistory(
        application_id=application.id,
        status="Correction Submitted",
        comment=f"Applicant changed to beneficiary {beneficiary.full_name} after a document name mismatch.",
    ))
    db.commit()
    return {
        "id": application.id,
        "applicant_type": application.applicant_type,
        "beneficiary": beneficiary_payload(beneficiary),
        "status": application.status,
    }


@app.post("/api/applications/{application_id}/submit")
def submit_application(application_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        raise HTTPException(404, "Application not found")
    if current_user.role != "admin" and app.user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed")

    app.status = "Submitted"
    app.submitted_at = __import__("datetime").datetime.utcnow()
    db.add(app)
    db.add(ApplicationStatusHistory(application_id=app.id, status="Submitted", comment="Application submitted for AI verification."))
    add_notification(db, app.user_id, "Application submitted", f"Your application for {app.scheme.name} was submitted for automated verification.")
    required_types = {item.document_type for item in app.scheme.required_documents if item.required}
    verified_types = {item.document_type for item in app.documents if item.verification_status in ("AI Verified", "Verified")}
    profile = app.beneficiary_profile or app.student_profile
    eligible = True
    for rule in app.scheme.eligibility_rules:
        value = getattr(profile, rule.field, None) if profile else None
        if rule.operator == "equals":
            passed = str(value).casefold() == str(rule.value).casefold()
        elif rule.operator in ("not equals", "not_equals"):
            passed = str(value).casefold() != str(rule.value).casefold()
        elif rule.operator in ("gte", "greater than or equal"):
            passed = value is not None and float(value) >= float(rule.value)
        elif rule.operator in ("gt", "greater than"):
            passed = value is not None and float(value) > float(rule.value)
        elif rule.operator in ("lte", "less than or equal"):
            passed = value is not None and float(value) <= float(rule.value)
        elif rule.operator in ("lt", "less than"):
            passed = value is not None and float(value) < float(rule.value)
        elif rule.operator == "in":
            passed = value is not None and str(value).casefold() in [item.strip().casefold() for item in rule.value.split(",")]
        else:
            passed = False
        eligible = eligible and passed
    if required_types.issubset(verified_types) and eligible and not any(item.status == "Open" for item in app.deficiencies):
        app.status = "Ready for Apply"
        db.add(ApplicationStatusHistory(application_id=app.id, status="Ready for Decision", comment="AI verification and deterministic eligibility evaluation passed."))
        add_notification(db, app.user_id, "You're ready to apply", "Your eligibility and documents passed pre-application verification. Apply on the official scholarship portal to submit your actual application.")
    elif any(item.status == "Open" for item in app.deficiencies):
        app.status = "Deficiency Raised"
    else:
        app.status = "Under Verification"
        db.add(ApplicationStatusHistory(application_id=app.id, status="Under Verification", comment="Application is awaiting document completion or an exception review."))
    db.commit()
    return {"status": app.status}


@app.get("/api/notifications")
def list_notifications(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    notifications = db.query(Notification).filter(Notification.user_id == current_user.id).order_by(Notification.id.desc()).all()
    return [
        {"id": item.id, "title": item.title, "message": item.message, "is_read": item.is_read, "created_at": item.created_at.isoformat()}
        for item in notifications
    ]


@app.post("/api/notifications/{notification_id}/read")
def mark_notification_read(notification_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    notification = db.query(Notification).filter(Notification.id == notification_id, Notification.user_id == current_user.id).first()
    if not notification:
        raise HTTPException(404, "Notification not found")
    notification.is_read = True
    db.commit()
    return {"id": notification.id, "is_read": notification.is_read}


def officer_application_payload(application: Application) -> dict:
    profile = application.beneficiary_profile or application.student_profile
    eligibility_checks = []
    for rule in application.scheme.eligibility_rules:
        actual = getattr(profile, rule.field, None) if profile else None
        passed = False
        if rule.operator == "equals":
            passed = str(actual).casefold() == str(rule.value).casefold()
        elif rule.operator in ("not equals", "not_equals"):
            passed = str(actual).casefold() != str(rule.value).casefold()
        elif rule.operator in ("gte", "greater than or equal") and actual is not None:
            passed = float(actual) >= float(rule.value)
        elif rule.operator in ("lte", "less than or equal") and actual is not None:
            passed = float(actual) <= float(rule.value)
        elif rule.operator in ("gt", "greater than") and actual is not None:
            passed = float(actual) > float(rule.value)
        elif rule.operator in ("lt", "less than") and actual is not None:
            passed = float(actual) < float(rule.value)
        elif rule.operator == "in" and actual is not None:
            passed = str(actual).casefold() in [item.strip().casefold() for item in rule.value.split(",")]
        eligibility_checks.append({"rule": rule.description, "field": rule.field, "operator": rule.operator, "value": rule.value, "actual": actual, "passed": passed, "explanation": f"Student value {actual} {'satisfies' if passed else 'does not satisfy'} the requirement."})
    return {
        "id": application.id,
        "status": application.status,
        "submitted_at": application.submitted_at.isoformat() if application.submitted_at else None,
        "created_at": application.created_at.isoformat(),
        "student": {"id": application.user.id, "name": application.user.full_name, "email": application.user.email},
        "profile": {"category": profile.category, "income": profile.income, "age": profile.age, "education_level": profile.education_level, "course": profile.course, "percentage": profile.percentage, "state": profile.state, "district": profile.district} if profile else {},
        "scheme": {"id": application.scheme.id, "name": application.scheme.name, "benefit": application.scheme.benefit, "level": application.scheme.level, "deadline": application.scheme.deadline.isoformat(), "description": application.scheme.description},
        "rules": [{"id": rule.id, "field": rule.field, "operator": rule.operator, "value": rule.value, "description": rule.description} for rule in application.scheme.eligibility_rules],
        "eligibility": {"eligible": all(item["passed"] for item in eligibility_checks), "summary": "ELIGIBLE" if all(item["passed"] for item in eligibility_checks) else "NOT ELIGIBLE", "checks": eligibility_checks},
        "documents": [{"id": item.id, "document_type": item.document_type, "filename": item.filename, "verification_status": item.verification_status, "verification_summary": item.verification_summary, "extracted_data": json.loads(item.extracted_data) if item.extracted_data else None, "created_at": item.created_at.isoformat()} for item in application.documents],
        "deficiencies": [{"id": item.id, "document_id": item.document_id, "field": item.field, "deficiency_type": item.deficiency_type, "title": item.title, "reason": item.reason or item.description, "description": item.description, "required_action": item.required_action, "severity": item.severity, "status": item.status, "created_at": item.created_at.isoformat()} for item in application.deficiencies],
        "timeline": [{"id": item.id, "status": item.status, "comment": item.comment, "created_at": item.created_at.isoformat()} for item in sorted(application.status_history, key=lambda history: history.created_at)],
    }


@app.get("/api/admin/applications")
def admin_applications(status_filter: str | None = None, scheme_id: int | None = None, search: str | None = None, current_user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    query = db.query(Application)
    if status_filter:
        query = query.filter(Application.status == status_filter)
    if scheme_id:
        query = query.filter(Application.scheme_id == scheme_id)
    applications = query.order_by(Application.created_at.desc()).all()
    if search:
        search_lower = search.casefold()
        applications = [item for item in applications if search_lower in item.user.full_name.casefold() or search_lower in str(item.id)]
    applications.sort(key=lambda item: (not any(deficiency.status == "Open" for deficiency in item.deficiencies), item.created_at))
    return [officer_application_payload(item) for item in applications]


@app.get("/api/admin/applications/{application_id}")
def admin_application_detail(application_id: int, current_user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise HTTPException(404, "Application not found")
    return officer_application_payload(application)


@app.post("/api/admin/applications/{application_id}/deficiencies")
def officer_raise_deficiency(application_id: int, deficiency_data: OfficerDeficiencyCreate, current_user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise HTTPException(404, "Application not found")
    deficiency = Deficiency(application_id=application.id, document_id=deficiency_data.document_id, field=deficiency_data.field, deficiency_type=deficiency_data.deficiency_type, title=f"{deficiency_data.field} — {deficiency_data.deficiency_type}", description=deficiency_data.explanation, reason=deficiency_data.reason, required_action=deficiency_data.required_action, severity=deficiency_data.severity, status="Open")
    application.status = "Deficiency Raised"
    db.add(deficiency)
    db.add(ApplicationStatusHistory(application_id=application.id, status="Deficiency Raised", comment=deficiency_data.reason))
    add_notification(db, application.user_id, "Deficiency raised", f"Action required: {deficiency_data.required_action}")
    db.commit()
    db.refresh(deficiency)
    return {"id": deficiency.id, "status": deficiency.status}


@app.post("/api/admin/documents/{document_id}/review")
def officer_review_document(document_id: int, review: OfficerDocumentReview, current_user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    allowed = {"AI Verified", "Verified", "Mismatch Detected", "Missing Information", "Reupload Required"}
    if review.status not in allowed:
        raise HTTPException(400, f"Status must be one of: {', '.join(sorted(allowed))}")
    document = db.query(ApplicationDocument).filter(ApplicationDocument.id == document_id).first()
    if not document:
        raise HTTPException(404, "Document not found")
    application = document.application
    document.verification_status = review.status
    if review.notes:
        document.verification_summary = review.notes
    timeline_status = "Documents Under Verification" if review.status in ("AI Verified", "Verified") else "Deficiency Raised"
    db.add(ApplicationStatusHistory(application_id=application.id, status=timeline_status, comment=f"Officer marked {document.filename}: {review.status}."))
    if review.status in ("AI Verified", "Verified"):
        for deficiency in application.deficiencies:
            if deficiency.document_id == document.id and deficiency.status == "Open":
                deficiency.status = "Resolved"
        application.status = "Correction Submitted" if application.status == "Deficiency Raised" else "Ready for Decision"
        add_notification(db, application.user_id, "Document verified", f"{document.filename} was marked verified by a scholarship officer.")
    else:
        application.status = "Deficiency Raised"
        add_notification(db, application.user_id, "Correction required", f"Please correct {document.filename}: {review.notes or review.status}.")
    db.commit()
    return {"id": document.id, "verification_status": document.verification_status}


@app.post("/api/admin/applications/{application_id}/decision")
def officer_decision(application_id: int, decision: OfficerDecision, current_user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    allowed = {"Under Review", "Approved", "Rejected"}
    if decision.status not in allowed:
        raise HTTPException(400, "Unsupported application decision")
    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise HTTPException(404, "Application not found")
    unresolved_deficiencies = [item for item in application.deficiencies if item.status == "Open"]
    if decision.status == "Approved" and unresolved_deficiencies:
        raise HTTPException(409, "Resolve all open deficiencies before approval")
    application.status = decision.status
    comment = decision.comment or f"Officer changed application status to {decision.status}."
    db.add(ApplicationStatusHistory(application_id=application.id, status=decision.status, comment=comment))
    add_notification(db, application.user_id, "Application status changed", comment)
    db.commit()
    return {"id": application.id, "status": application.status}


@app.get("/api/admin/schemes")
def admin_schemes(current_user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    return [{"id": scheme.id, "name": scheme.name, "level": scheme.level, "benefit": scheme.benefit, "description": scheme.description, "deadline": scheme.deadline.isoformat(), "is_active": scheme.is_active, "rules": [{"id": rule.id, "field": rule.field, "operator": rule.operator, "value": rule.value, "description": rule.description} for rule in scheme.eligibility_rules], "required_documents": [{"id": item.id, "document_type": item.document_type, "label": item.label, "required": item.required} for item in scheme.required_documents]} for scheme in db.query(ScholarshipScheme).all()]


@app.put("/api/admin/schemes/{scheme_id}")
def update_scheme(scheme_id: int, scheme_data: ScholarshipCreate, current_user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    scheme = db.query(ScholarshipScheme).filter(ScholarshipScheme.id == scheme_id).first()
    if not scheme:
        raise HTTPException(404, "Scholarship not found")
    scheme.name, scheme.level, scheme.benefit, scheme.description, scheme.deadline = scheme_data.name, scheme_data.level, scheme_data.benefit, scheme_data.description, scheme_data.deadline
    db.query(EligibilityRule).filter(EligibilityRule.scheme_id == scheme.id).delete(synchronize_session=False)
    db.query(RequiredDocument).filter(RequiredDocument.scheme_id == scheme.id).delete(synchronize_session=False)
    for rule in scheme_data.rules:
        db.add(EligibilityRule(scheme_id=scheme.id, field=rule.field, operator=rule.operator, value=rule.value, description=rule.description))
    for document in scheme_data.required_documents:
        db.add(RequiredDocument(scheme_id=scheme.id, document_type=document, label=document, required=True))
    db.commit()
    return {"id": scheme.id, "name": scheme.name}


@app.get("/api/admin/dashboard")
def admin_dashboard(current_user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    total = db.query(Application).count()
    pending = db.query(Application).filter(Application.status.in_(["Submitted", "Under Verification", "Deficiency Raised", "Correction Submitted", "Under Review", "Under Officer Review"])).count()
    under_review = db.query(Application).filter(Application.status.in_(["Under Review", "Under Officer Review"])).count()
    deficiencies = db.query(Deficiency).filter(Deficiency.status == "Open").count()
    flagged_documents = db.query(ApplicationDocument).filter(ApplicationDocument.verification_status.in_(["Flagged for Review", "Mismatch Detected", "Missing Information", "Reupload Required"])).count()
    automatically_verified = db.query(ApplicationDocument).filter(ApplicationDocument.verification_status == "AI Verified").count()
    ready_for_decision = db.query(Application).filter(Application.status == "Ready for Decision").count()
    approved = db.query(Application).filter(Application.status == "Approved").count()
    rejected = db.query(Application).filter(Application.status == "Rejected").count()

    return {
        "total_applications": total,
        "pending_review": pending,
        "under_review": under_review,
        "deficiencies": deficiencies,
        "flagged_documents": flagged_documents,
        "automatically_verified": automatically_verified,
        "ready_for_decision": ready_for_decision,
        "approved": approved,
        "rejected": rejected,
        "status_distribution": {
            "Draft": db.query(Application).filter(Application.status == "Draft").count(),
            "Submitted": db.query(Application).filter(Application.status == "Submitted").count(),
            "Under Verification": db.query(Application).filter(Application.status == "Under Verification").count(),
            "Ready for Decision": ready_for_decision,
            "Deficiency Raised": db.query(Application).filter(Application.status == "Deficiency Raised").count(),
            "Approved": db.query(Application).filter(Application.status == "Approved").count(),
            "Rejected": db.query(Application).filter(Application.status == "Rejected").count(),
        },
        "applications_by_scholarship": {
            scheme.name: db.query(Application).filter(Application.scheme_id == scheme.id).count()
            for scheme in db.query(ScholarshipScheme).all()
        },
    }


@app.post("/api/applications/{application_id}/documents")
async def upload_document(
    application_id: int,
    document_type: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise HTTPException(404, "Application not found")
    if current_user.role != "admin" and application.user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed")

    safe_name = Path(file.filename or "document").name
    content = await file.read()
    target = UPLOAD_DIR / f"{application_id}_{safe_name}"
    target.write_bytes(content)
    previous = db.query(ApplicationDocument).filter(
        ApplicationDocument.application_id == application_id,
        ApplicationDocument.document_type == document_type,
        ApplicationDocument.verification_status != "Replaced",
    ).order_by(ApplicationDocument.id.desc()).first()
    if previous:
        previous.verification_status = "Replaced"
    document = ApplicationDocument(
        application_id=application_id,
        document_type=document_type,
        filename=safe_name,
        file_path=str(target),
        classification=document_type,
        verification_status="Pending Verification",
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    result = analyze_document(document_type, safe_name, content, application.beneficiary_profile or application.student_profile, application, application.scheme)
    document.extracted_data = serialize_analysis(result)
    document.verification_summary = "; ".join(item["reason"] for item in result["issues"]) or "Offline document checks passed."
    document.verification_status = result["status"]
    open_deficiencies = db.query(Deficiency).filter(Deficiency.application_id == application_id, Deficiency.status == "Open").all()
    related = [item for item in open_deficiencies if item.document_id in {document.id, previous.id if previous else None} or item.field == document_type]
    if result["issues"]:
        application.status = "Deficiency Raised"
        db.add(ApplicationStatusHistory(application_id=application_id, status="Deficiency Raised", comment=f"{safe_name} requires correction."))
        for issue in result["issues"]:
            deficiency = related.pop(0) if related else Deficiency(application_id=application_id)
            deficiency.document_id = document.id
            deficiency.field = issue["type"]
            deficiency.deficiency_type = issue["type"]
            deficiency.title = f"{safe_name} — {issue['type']}"
            deficiency.description = issue["reason"]
            deficiency.reason = issue["reason"]
            deficiency.required_action = issue["action"]
            deficiency.severity = "High"
            deficiency.status = "Open"
            db.add(deficiency)
        add_notification(db, application.user_id, "Deficiency raised", f"Action is required on {safe_name}: {result['issues'][0]['reason']}")
    else:
        for deficiency in related:
            deficiency.status = "Resolved"
            deficiency.required_action = "No further action required."
            db.add(deficiency)
        application.status = "Correction Submitted" if previous else ("Draft" if application.status == "Draft" else "Ready for Decision")
        db.add(ApplicationStatusHistory(application_id=application_id, status=application.status, comment=f"{safe_name} uploaded and queued for re-verification."))
        db.add(ApplicationStatusHistory(application_id=application_id, status="Re-verification", comment="Document analysis completed without a mismatch."))
        add_notification(db, application.user_id, "Document verification updated", f"{safe_name} passed the offline verification checks.")
    db.commit()
    return {
        "id": document.id,
        "document_type": document.document_type,
        "filename": document.filename,
        "verification_status": document.verification_status,
        "verification_summary": document.verification_summary,
        "extracted_data": json.loads(document.extracted_data),
        "issues": result["issues"],
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}
