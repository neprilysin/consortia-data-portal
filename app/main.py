import hashlib
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Depends, UploadFile, File, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import Submission
from .security import get_current_email, is_admin
from .analysis import analyse_file
from .reporting import generate_report
from .supabase_store import save_consortia_record

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


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    email = get_current_email(request)
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "email": email, "is_admin": is_admin(email)},
    )


@app.post("/login")
def login(email: str = Form(...)):
    redirect = RedirectResponse("/", status_code=303)
    redirect.set_cookie("email", email, httponly=True)
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

    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    safe_name = file.filename.replace("/", "_").replace("\\", "_")
    stored_name = f"{uuid.uuid4()}_{safe_name}"
    stored_path = UPLOAD_DIR / stored_name

    with stored_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    file_hash = sha256_file(stored_path)

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
        file_url=str(stored_path),
        status="Uploaded",
        certificate_url=None,
        dataset_hash=file_hash,
    )

    return RedirectResponse("/dashboard", status_code=303)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    email = get_current_email(request)

    if is_admin(email):
        submissions = db.query(Submission).order_by(Submission.created_at.desc()).all()
    else:
        submissions = (
            db.query(Submission)
            .filter(Submission.user_email == email)
            .order_by(Submission.created_at.desc())
            .all()
        )

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "email": email,
            "is_admin": is_admin(email),
            "submissions": submissions,
        },
    )


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
