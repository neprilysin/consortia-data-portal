# Consortia Data Portal MVP

A starter project for a consortium-style platform where users upload raw data, admins review/analyse it, and certified PDF reports are generated.

## Features

- User/admin login placeholder
- Raw data upload endpoint
- Submission status tracking
- Admin review dashboard
- Analysis job placeholder
- Certified report PDF generation
- Certificate ID and SHA-256 dataset hash
- Local file storage for MVP
- SQLite database for MVP

## Tech Stack

- FastAPI
- SQLite
- Jinja2 templates
- ReportLab PDF generation

## Run locally

conda activate consortia
pip install -r requirements.txt
uvicorn app.main:app --reload

Then open:

```text
http://127.0.0.1:8000
```

## Demo users

- User: `user@example.com`
- Admin: `admin@example.com`

No password is required in this starter version. Replace this with proper authentication before production.

## Production notes

Before using this with real sensitive data, add:

- Real authentication
- Role-based access control
- Encrypted object storage, e.g. AWS S3
- Malware scanning
- File validation
- Audit logs
- Data retention rules
- GDPR / UK GDPR compliance review
- Proper digital signatures
- Backup and disaster recovery
