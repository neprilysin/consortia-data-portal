import hashlib
import shutil
import uuid
from datetime import datetime
from email.utils import formataddr
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, UploadFile, File, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse

load_dotenv()
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .email_utils import send_admin_notification
from .models import Submission, User
from .security import (
    get_admin_email,
    get_current_email,
    hash_password,
    is_admin,
    verify_admin_password,
    verify_password,
)
from .analysis import analyse_file
from .reporting import generate_report
from .supabase_store import save_consortia_record, upload_file_to_bucket

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Consortia Data Portal MVP")

templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

UPLOAD_DIR = Path("storage/uploads")
REPORT_DIR = Path("storage/reports")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_text(value: str | None) -> str:
    return (value or "").strip()


def get_user_by_email(db: Session, email: str | None) -> User | None:
    if not email:
        return None
    return db.query(User).filter(User.email == email.lower()).first()


@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    email = get_current_email(request)
    user = get_user_by_email(db, email)
    pending_count = 0

    if is_admin(email):
        pending_count = db.query(User).filter(User.status == "pending").count()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "email": email,
            "user": user,
            "is_admin": is_admin(email),
            "admin_email": get_admin_email(),
            "pending_count": pending_count,
        },
    )


@app.get("/register", response_class=HTMLResponse)
def show_register(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
def show_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/register")
def submit_register(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    title: str = Form(""),
    department: str = Form(""),
    organization: str = Form(""),
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    policy_accepted: bool = Form(False),
    db: Session = Depends(get_db),
):
    if not policy_accepted:
        raise HTTPException(status_code=400, detail="You must accept the scientific data integrity policy.")

    normalized_email = email.strip().lower()
    if not normalized_email:
        raise HTTPException(status_code=400, detail="Email is required.")

    if password != password_confirm:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "Passwords do not match.",
                "first_name": first_name,
                "last_name": last_name,
                "title": title,
                "department": department,
                "organization": organization,
                "email": email,
            },
            status_code=400,
        )

    if len(password) < 8:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "Password must be at least 8 characters long.",
                "first_name": first_name,
                "last_name": last_name,
                "title": title,
                "department": department,
                "organization": organization,
                "email": email,
            },
            status_code=400,
        )

    user = get_user_by_email(db, normalized_email)

    if normalized_email == get_admin_email().lower():
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "Admin must log in through the admin login page.",
                "first_name": first_name,
                "last_name": last_name,
                "title": title,
                "department": department,
                "organization": organization,
                "email": email,
            },
            status_code=400,
        )

    if not user:
        user = User(
            first_name=safe_text(first_name),
            last_name=safe_text(last_name),
            title=safe_text(title),
            department=safe_text(department),
            organization=safe_text(organization),
            email=normalized_email,
            password_hash=hash_password(password),
            policy_accepted="true",
            approved="false",
            status="pending",
        )
        db.add(user)
    else:
        user.first_name = safe_text(first_name)
        user.last_name = safe_text(last_name)
        user.title = safe_text(title)
        user.department = safe_text(department)
        user.organization = safe_text(organization)
        user.policy_accepted = "true"
        if user.status != "approved":
            user.status = "pending"
            user.approved = "false"
        user.password_hash = hash_password(password)

    db.commit()

    send_admin_notification(user=user, admin_email=get_admin_email())

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "success": "Registration submitted. Your account is pending admin approval.",
            "email": normalized_email,
        },
    )


@app.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    normalized_email = email.strip().lower()
    if not normalized_email:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Email is required."},
            status_code=400,
        )

    if is_admin(normalized_email):
        if not verify_admin_password(password):
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "error": "Invalid admin credentials."},
                status_code=401,
            )

        redirect = RedirectResponse("/dashboard", status_code=303)
        redirect.set_cookie("email", normalized_email, httponly=True)
        return redirect

    user = get_user_by_email(db, normalized_email)
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "No account found. Please register first."},
            status_code=404,
        )

    if not user.password_hash or not verify_password(user.password_hash, password):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid email or password."},
            status_code=401,
        )

    redirect = RedirectResponse("/", status_code=303)
    redirect.set_cookie("email", normalized_email, httponly=True)
    return redirect


@app.post("/logout")
def logout():
    redirect = RedirectResponse("/", status_code=303)
    redirect.delete_cookie("email")
    return redirect


@app.post("/upload")
def upload_file(
    request: Request,
    file: UploadFile = File(...),
    lab_name: str = Form(...),
    project_name: str = Form(""),
    molecule_name: str = Form(...),
    experiment_type: str = Form("logP"),
    instrument: str = Form(""),
    notes: str = Form(""),
    p0_phase: float = Form(74.0),
    p1_phase: float = Form(0.0),
    db: Session = Depends(get_db),
):
    email = get_current_email(request)
    user = get_user_by_email(db, email)
    normalized_email = email.lower() if email else None

    if not user:
        raise HTTPException(status_code=403, detail="Please register and wait for admin approval before uploading.")

    if user.status != "approved" or user.approved != "true":
        raise HTTPException(status_code=403, detail="Your account is not approved yet.")

    if user.policy_accepted != "true":
        raise HTTPException(status_code=403, detail="You must accept the data integrity policy before uploading.")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    safe_name = file.filename.replace("/", "_").replace("\\", "_")
    stored_name = f"{uuid.uuid4()}_{safe_name}"
    stored_path = UPLOAD_DIR / stored_name

    with stored_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    file_hash = sha256_file(stored_path)
    supabase_upload_path = f"{normalized_email}/{stored_name}"

    upload_file_to_bucket(
        bucket_name="uploads",
        local_path=stored_path,
        storage_path=supabase_upload_path,
    )

    submission = Submission(
        user_email=email,
        lab_name=safe_text(lab_name),
        project_name=safe_text(project_name),
        molecule_name=safe_text(molecule_name),
        experiment_type=safe_text(experiment_type),
        instrument=safe_text(instrument),
        notes=safe_text(notes),
        p0_phase=p0_phase,
        p1_phase=p1_phase,
        original_filename=safe_name,
        stored_filename=stored_name,
        file_hash=file_hash,
        status="Uploaded",
        updated_at=datetime.utcnow(),
    )

    db.add(submission)
    db.commit()

    save_consortia_record(
        user_name=email,
        lab=safe_text(lab_name),
        project=safe_text(project_name),
        molecule=safe_text(molecule_name),
        experiment=safe_text(experiment_type),
        phase=f"p0={p0_phase}, p1={p1_phase}",
        file_url=supabase_upload_path,
        status="Uploaded",
        certificate_url=None,
        dataset_hash=file_hash,
    )

    return RedirectResponse("/dashboard", status_code=303)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    email = get_current_email(request)
    user = get_user_by_email(db, email)

    if is_admin(email):
        submissions = db.query(Submission).order_by(Submission.created_at.desc()).all()
        pending_users = db.query(User).filter(User.status == "pending").order_by(User.registered_at.desc()).all()
    else:
        submissions = (
            db.query(Submission)
            .filter(Submission.user_email == email)
            .order_by(Submission.created_at.desc())
            .all()
        )
        pending_users = []

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "email": email,
            "user": user,
            "is_admin": is_admin(email),
            "submissions": submissions,
            "pending_users": pending_users,
        },
    )


@app.post("/admin/users/{user_id}/approve")
def approve_user(request: Request, user_id: int, db: Session = Depends(get_db)):
    email = get_current_email(request)
    if not is_admin(email):
        raise HTTPException(status_code=403, detail="Admin only")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.approved = "true"
    user.status = "approved"
    user.approved_at = datetime.utcnow()
    db.commit()

    return RedirectResponse("/dashboard", status_code=303)


@app.post("/admin/users/{user_id}/reject")
def reject_user(request: Request, user_id: int, db: Session = Depends(get_db)):
    email = get_current_email(request)
    if not is_admin(email):
        raise HTTPException(status_code=403, detail="Admin only")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.approved = "false"
    user.status = "rejected"
    db.commit()

    return RedirectResponse("/dashboard", status_code=303)


@app.post("/admin/submissions/{submission_id}/analyse")
def analyse_submission(
    request: Request,
    submission_id: int,
    db: Session = Depends(get_db),
):
    email = get_current_email(request)

    if not is_admin(email):
        raise HTTPException(status_code=403, detail="Admin only")

    submission = db.query(Submission).filter(Submission.id == submission_id).first()

    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    submission.status = "In Analysis"
    submission.updated_at = datetime.utcnow()
    db.commit()

    file_path = UPLOAD_DIR / submission.stored_filename

    molecule_name = submission.molecule_name or "CMPD1"

    summary = analyse_file(
        file_path=file_path,
        molecule_name=molecule_name,
        p0_phase=submission.p0_phase if submission.p0_phase is not None else 74.0,
        p1_phase=submission.p1_phase if submission.p1_phase is not None else 0.0,
    )

    certificate_id = f"CERT-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    report_filename = f"report_submission_{submission.id}.pdf"
    report_path = REPORT_DIR / report_filename

    generate_report(
        output_path=report_path,
        submission_id=submission.id,
        user_email=submission.user_email,
        original_filename=submission.original_filename,
        file_hash=submission.file_hash,
        analysis_summary=summary,
        certificate_id=certificate_id,
        lab_name=submission.lab_name or "",
        project_name=submission.project_name or "",
        molecule_name=submission.molecule_name or "",
        experiment_type=submission.experiment_type or "",
        instrument=submission.instrument or "",
        notes=submission.notes or "",
        p0_phase=submission.p0_phase,
        p1_phase=submission.p1_phase,
    )

    supabase_report_path = f"{submission.user_email}/{report_filename}"

    upload_file_to_bucket(
        bucket_name="reports",
        local_path=report_path,
        storage_path=supabase_report_path,
    )

    submission.analysis_summary = summary
    submission.certificate_id = certificate_id
    submission.report_filename = report_filename
    submission.status = "Report Ready"
    submission.updated_at = datetime.utcnow()

    db.commit()

    return RedirectResponse("/dashboard", status_code=303)


@app.get("/reports/{submission_id}")
def download_report(
    request: Request,
    submission_id: int,
    db: Session = Depends(get_db),
):
    email = get_current_email(request)
    submission = db.query(Submission).filter(Submission.id == submission_id).first()

    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    if not is_admin(email) and submission.user_email != email:
        raise HTTPException(status_code=403, detail="Not allowed")

    if not submission.report_filename:
        raise HTTPException(status_code=404, detail="Report is not ready")

    report_path = REPORT_DIR / submission.report_filename

    return FileResponse(
        report_path,
        media_type="application/pdf",
        filename=submission.report_filename,
    )
