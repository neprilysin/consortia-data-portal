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

1. Create or activate your Conda environment:

```bash
conda activate consortia
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root with at least:

```env
SUPABASE_URL=https://your-supabase-url
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=admin123
```

4. Start the app:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Then open:

```text
http://127.0.0.1:8000
```

## Demo users

- Admin email: `admin@example.com`
- Admin password: `admin123`

Users must register before they can upload data. New user accounts remain in `pending` status until an administrator approves them.

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
