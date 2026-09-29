from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import (
    Application,
    ApplicationDocument,
    ApplicationStatusHistory,
    Deficiency,
    EligibilityRule,
    Notification,
    RequiredDocument,
    ScholarshipScheme,
    StudentProfile,
    User,
)
from app.utils import hash_password


def seed_database(db: Session) -> None:
    existing_schemes = db.query(ScholarshipScheme).count()
    if existing_schemes > 0:
        return

    admin = User(
        email="admin@scholarshipsetu.demo",
        full_name="Scholarship Officer",
        password_hash=hash_password("admin123"),
        role="admin",
    )
    student = User(
        email="student@scholarshipsetu.demo",
        full_name="Aditi Majhi",
        password_hash=hash_password("student123"),
        role="student",
    )
    db.add_all([admin, student])
    db.commit()
    db.refresh(admin)
    db.refresh(student)

    profile = StudentProfile(
        user_id=student.id,
        category="ST",
        income=76000,
        age=20,
        education_level="UG",
        course="B.Tech",
        percentage=85.5,
        phone="9876543210",
        state="Odisha",
        district="Mayurbhanj",
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    scheme1 = ScholarshipScheme(
        name="Tribal Higher Education Support Scheme",
        slug="tribal-higher-education-support-scheme",
        level="Undergraduate",
        benefit="Annual academic support grant",
        description="Support for ST undergraduate students pursuing higher education.",
        deadline=date(2026, 11, 30),
    )
    scheme2 = ScholarshipScheme(
        name="Post-Matric Scholarship for ST Students",
        slug="post-matric-scholarship-for-st-students",
        level="Post-Matric",
        benefit="Academic and maintenance support",
        description="Merit-based support for ST students in post-matric education.",
        deadline=date(2026, 12, 15),
    )
    db.add_all([scheme1, scheme2])
    db.commit()
    db.refresh(scheme1)
    db.refresh(scheme2)

    rules1 = [
        EligibilityRule(scheme_id=scheme1.id, field="category", operator="equals", value="ST", description="Applicant must belong to ST category."),
        EligibilityRule(scheme_id=scheme1.id, field="income", operator="lte", value="100000", description="Annual family income must be within Rs. 1,00,000."),
        EligibilityRule(scheme_id=scheme1.id, field="education_level", operator="equals", value="UG", description="Applicant must be pursuing undergraduate study."),
        EligibilityRule(scheme_id=scheme1.id, field="percentage", operator="gte", value="75", description="Minimum academic score of 75% required."),
    ]
    rules2 = [
        EligibilityRule(scheme_id=scheme2.id, field="category", operator="equals", value="ST", description="Applicant must belong to ST category."),
        EligibilityRule(scheme_id=scheme2.id, field="income", operator="lte", value="250000", description="Annual family income must be within Rs. 2,50,000."),
        EligibilityRule(scheme_id=scheme2.id, field="education_level", operator="in", value="UG,PG", description="Applicant must be in undergraduate or postgraduate education."),
        EligibilityRule(scheme_id=scheme2.id, field="percentage", operator="gte", value="60", description="Minimum academic score of 60% required."),
    ]
    db.add_all(rules1 + rules2)
    db.commit()

    docs1 = [
        RequiredDocument(scheme_id=scheme1.id, document_type="caste_certificate", label="Caste Certificate", required=True, description="Valid ST certificate"),
        RequiredDocument(scheme_id=scheme1.id, document_type="income_certificate", label="Income Certificate", required=True, description="Annual income proof"),
        RequiredDocument(scheme_id=scheme1.id, document_type="marksheet", label="Latest Marksheet", required=True, description="Academic record"),
    ]
    docs2 = [
        RequiredDocument(scheme_id=scheme2.id, document_type="caste_certificate", label="Caste Certificate", required=True, description="Valid ST certificate"),
        RequiredDocument(scheme_id=scheme2.id, document_type="income_certificate", label="Income Certificate", required=True, description="Annual income proof"),
        RequiredDocument(scheme_id=scheme2.id, document_type="admission_proof", label="Admission Proof", required=True, description="Institution enrollment proof"),
    ]
    db.add_all(docs1 + docs2)
    db.commit()

    application = Application(
        user_id=student.id,
        scheme_id=scheme1.id,
        student_profile_id=profile.id,
        status="Under Verification",
        eligibility_result="Eligible\n✓ ST requirement satisfied\n✓ Income requirement satisfied\n✓ Course requirement satisfied\n✓ Academic requirement satisfied",
        summary="Application in progress and under review.",
    )
    db.add(application)
    db.commit()
    db.refresh(application)

    doc = ApplicationDocument(
        application_id=application.id,
        document_type="caste_certificate",
        filename="caste_certificate.pdf",
        file_path="/tmp/caste_certificate.pdf",
        extracted_text="Tribal community certificate issued in Odisha.",
        classification="caste_certificate",
        verification_status="Verified",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    deficiency = Deficiency(
        application_id=application.id,
        title="Missing income proof",
        description="The income certificate must include the latest financial year declaration.",
        severity="Medium",
    )
    db.add(deficiency)
    db.commit()

    status_history = ApplicationStatusHistory(
        application_id=application.id,
        status="Submitted",
        comment="Application submitted and verification started.",
    )
    db.add(status_history)
    db.commit()

    notification1 = Notification(
        user_id=student.id,
        title="Application under verification",
        message="Your scholarship application for Tribal Higher Education Support Scheme is being reviewed.",
    )
    notification2 = Notification(
        user_id=student.id,
        title="Document requirement updated",
        message="Please upload the latest income certificate to complete document verification.",
    )
    db.add_all([notification1, notification2])
    db.commit()

    application2 = Application(
        user_id=student.id,
        scheme_id=scheme2.id,
        student_profile_id=profile.id,
        status="Deficiency Raised",
        eligibility_result="Not Eligible\n✓ ST category requirement satisfied\n✗ Income exceeds permitted limit",
        summary="Application was flagged due to income mismatch.",
    )
    db.add(application2)
    db.commit()
    db.refresh(application2)

    app_doc2 = ApplicationDocument(
        application_id=application2.id,
        document_type="income_certificate",
        filename="income_certificate.pdf",
        file_path="/tmp/income_certificate.pdf",
        extracted_text="Annual income reported as Rs. 3,20,000.",
        classification="income_certificate",
        verification_status="Rejected",
    )
    db.add(app_doc2)
    db.commit()

    bursary = ApplicationStatusHistory(
        application_id=application2.id,
        status="Deficiency Raised",
        comment="Income exceeds the threshold for this scheme.",
    )
    db.add(bursary)
    db.commit()
