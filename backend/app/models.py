from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default="student")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    student_profile = relationship("StudentProfile", back_populates="user", uselist=False)
    applications = relationship("Application", back_populates="user")
    notifications = relationship("Notification", back_populates="user")


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    category = Column(String(50), default="ST")
    income = Column(Float, default=0)
    age = Column(Integer, default=0)
    education_level = Column(String(50), default="UG")
    course = Column(String(255), default="B.Tech")
    percentage = Column(Float, default=0.0)
    phone = Column(String(50), nullable=True)
    state = Column(String(255), nullable=True)
    district = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="student_profile")
    applications = relationship("Application", back_populates="student_profile")


class BeneficiaryProfile(Base):
    __tablename__ = "beneficiary_profiles"

    id = Column(Integer, primary_key=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    full_name = Column(String(255), nullable=False)
    age = Column(Integer, default=0)
    category = Column(String(50), default="ST")
    income = Column(Float, default=0)
    education_level = Column(String(50), default="UG")
    course = Column(String(255), default="B.Tech")
    percentage = Column(Float, default=0.0)
    institution = Column(String(255), nullable=True)
    state = Column(String(255), nullable=True)
    district = Column(String(255), nullable=True)
    relationship_to_applicant = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User")
    applications = relationship("Application", back_populates="beneficiary_profile")


class ScholarshipScheme(Base):
    __tablename__ = "scholarship_schemes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)
    level = Column(String(100), nullable=False)
    benefit = Column(String(255), nullable=False)
    description = Column(Text)
    deadline = Column(Date, nullable=False)
    is_active = Column(Boolean, default=True)
    source_name = Column(String(255), nullable=True)
    source_url = Column(String(500), nullable=True)
    academic_year = Column(String(20), nullable=True)
    last_verified_at = Column(DateTime, nullable=True)
    source_status = Column(String(50), default="official")
    created_at = Column(DateTime, default=datetime.utcnow)

    eligibility_rules = relationship("EligibilityRule", back_populates="scheme")
    required_documents = relationship("RequiredDocument", back_populates="scheme")
    applications = relationship("Application", back_populates="scheme")


class EligibilityRule(Base):
    __tablename__ = "eligibility_rules"

    id = Column(Integer, primary_key=True, index=True)
    scheme_id = Column(Integer, ForeignKey("scholarship_schemes.id"), nullable=False)
    field = Column(String(100), nullable=False)
    operator = Column(String(50), nullable=False)
    value = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    scheme = relationship("ScholarshipScheme", back_populates="eligibility_rules")


class RequiredDocument(Base):
    __tablename__ = "required_documents"

    id = Column(Integer, primary_key=True, index=True)
    scheme_id = Column(Integer, ForeignKey("scholarship_schemes.id"), nullable=False)
    document_type = Column(String(255), nullable=False)
    label = Column(String(255), nullable=False)
    required = Column(Boolean, default=True)
    description = Column(Text)

    scheme = relationship("ScholarshipScheme", back_populates="required_documents")


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    scheme_id = Column(Integer, ForeignKey("scholarship_schemes.id"), nullable=False)
    student_profile_id = Column(Integer, ForeignKey("student_profiles.id"), nullable=True)
    beneficiary_profile_id = Column(Integer, ForeignKey("beneficiary_profiles.id"), nullable=True)
    applicant_type = Column(String(30), default="self")
    relationship_to_applicant = Column(String(100), nullable=True)
    status = Column(String(50), default="Draft")
    eligibility_result = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="applications")
    scheme = relationship("ScholarshipScheme", back_populates="applications")
    student_profile = relationship("StudentProfile", back_populates="applications")
    beneficiary_profile = relationship("BeneficiaryProfile", back_populates="applications")
    documents = relationship("ApplicationDocument", back_populates="application")
    deficiencies = relationship("Deficiency", back_populates="application")
    status_history = relationship("ApplicationStatusHistory", back_populates="application")
    audit_logs = relationship("AuditLog", back_populates="application")


class ApplicationDocument(Base):
    __tablename__ = "application_documents"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    document_type = Column(String(255), nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    extracted_text = Column(Text, nullable=True)
    classification = Column(String(255), nullable=True)
    verification_status = Column(String(50), default="Pending")
    extracted_data = Column(Text, nullable=True)
    verification_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    application = relationship("Application", back_populates="documents")
    verification = relationship("DocumentVerification", back_populates="document", uselist=False)


class DocumentVerification(Base):
    __tablename__ = "document_verifications"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("application_documents.id"), nullable=False)
    check_type = Column(String(100), default="demo")
    result = Column(String(50), default="Pending")
    notes = Column(Text, nullable=True)
    verified_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("ApplicationDocument", back_populates="verification")


class Deficiency(Base):
    __tablename__ = "deficiencies"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String(50), default="Medium")
    document_id = Column(Integer, ForeignKey("application_documents.id"), nullable=True)
    field = Column(String(100), nullable=True)
    deficiency_type = Column(String(100), nullable=True)
    reason = Column(Text, nullable=True)
    required_action = Column(Text, nullable=True)
    status = Column(String(50), default="Open")
    created_at = Column(DateTime, default=datetime.utcnow)

    application = relationship("Application", back_populates="deficiencies")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="notifications")


class ApplicationStatusHistory(Base):
    __tablename__ = "application_status_history"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    status = Column(String(50), nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    application = relationship("Application", back_populates="status_history")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    actor = Column(String(255), nullable=False)
    action = Column(String(255), nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    application = relationship("Application", back_populates="audit_logs")
