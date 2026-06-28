# MediBridge Medical Center

[![Django Version](https://img.shields.io/badge/Django-5.2-emerald.svg)](https://www.djangoproject.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue.svg)](https://www.postgresql.org/)
[![Docker Compose](https://img.shields.io/badge/Docker%20Compose-Orchestrated-blueviot.svg)](https://docs.docker.com/compose/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **Smart Hospital Management & Electronic Medical Records (EMR) System**

MediBridge is a clinical-grade hospital portal designed to streamline patient scheduling, Electronic Medical Records (EMRs), clinical prescription pipelines, and administrative hospital operations. Built on a modular Django 5.2 architecture, the platform enforces transactional integrity and operational safety through database-level row locks, asynchronous worker dispatching, and a serverless email service.

---

## 📖 Project Overview

The primary objective of **MediBridge** is to provide an intuitive, high-reliability platform that connects patients, doctors, and system administrators. Unlike legacy hospital portals, MediBridge prioritizes modern UX principles, absolute data consistency, and microservice segregation.

Key engineering highlights include:
* **Race-Condition Prevention**: row-level locking (`select_for_update`) protects calendar time slots during concurrent patient booking requests.
* **Microservices Design**: email delivery runs on an isolated Serverless offline function, triggered asynchronously.
* **Google Calendar Sync**: two-way OAuth2 synchronization maps clinic bookings directly to users' personal calendars.

---

## 🛠️ Technology Stack

* **Backend Framework**: Python 3.11+ / Django 5.2 (ORM, session auth, validation, contexts)
* **Database Layer**: PostgreSQL 15 (with local SQLite fallback for testing)
* **CSS & Frontend Styling**: Custom premium light theme using Tailwind CSS and Outfit/Inter google typography
* **Asynchronous Integration Worker**: Database-backed event task loop
* **Serverless Functions**: Local Serverless Framework Offline environment emulating Node Lambdas
* **Local SMTP Server**: Mailpit container with integrated web inspector dashboard
* **Calendar Sync**: Google Cloud Calendar API (OAuth2 Client)

---

## 📋 Features

### Authentication
* **Role-Based Access Control (RBAC)**: Enforces strict separation of concerns for `PATIENT`, `DOCTOR`, and `ADMIN` groups.
* **Registration Approvals**: Doctor signups start in a `PENDING` state and require administrative verification of documents.
* **Operational Lifecycles**: Strict state management transitions: `PENDING` ➔ `APPROVED` ➔ `SUSPENDED` ➔ `REMOVED`.
* **Collapsible Developer Panel**: Access coordinates for demo profiles are rendered in a hidden panel toggleable only when `DEBUG=True`.

### Patient Portal
* **Dedicated Booking Page**: Centered booking wizard located at `/patients/book-appointment/`.
* **Doctor Directory**: Instant directories with typeahead autocomplete suggestions.
* **Combinable Search Filters**: Filter doctors by Specialization, Average Rating, Availability (Today, Tomorrow, This Week), and Experience level.
* **Interactive Booking Wizard**: Dynamic three-step scheduling (Choose Doctor, Select Date/Slot, Review Summary).
* **Consultation Feedback**: 1–5 star rating forms and reviews linked to completed bookings.
* **Reports Hub**: Upload, view, and download clinical laboratory reports (PDF/Image formats).

### Doctor Dashboard
* **Patient Queue**: Daily schedule chronological timeline tracking today's bookings.
* **Practice Setup**: Custom slot intervals, durations, buffer times, and weekday hours.
* **Clinical Leaves**: Request leave windows which automatically cancel overlapping bookings.
* **EMR Form Panel**: Log symptoms, diagnoses, notes, and structured JSON prescriptions.
* **Google Sync Panel**: Link and synchronize appointments directly onto personal Google Calendars.

### Administrative Panel
* **Clinician Verifications**: Audit doctor profiles (license documents, degrees) to approve, suspend, or reactivate accounts.
* **Graceful Doctor Removal**: Soft-deletes doctors, deletes future slot timelines, cancels future bookings, and deletes synchronized Google Calendar events.
* **Hospital Settings Panel**: Configure clinic name, contact info, and branding dynamically using a singleton model.
* **System Health Monitor**: Live diagnostic board tracking DB, SMTP host, Google API secrets, and task backlog metrics.

### Medical Records (EMR)
* **Consultation Charts**: Symptoms, diagnoses, advice, and next check-up dates.
* **Structured Prescriptions**: Medication details, dosages, frequencies, and durations stored in robust JSON fields.
* **Lab Integrations**: Attach independent patient uploaded files directly to EMR logs during consults.

### Google Calendar Sync
* **Automatic Creation**: Syncs confirmed bookings directly to user calendars.
* **Reschedules & Deletes**: Automatically updates or deletes Google Calendar events when bookings are canceled or modified.

### Asynchronous Queue
* **AsyncTask Engine**: Offloads SMTP email transmissions and Google API latencies to a background queue.
* **Backoff Retries**: Automatic exponential backoffs protect against third-party network outages.

---

## 🔌 Prerequisites

Before running the application, ensure the following software is installed on your local machine:

1. **Python 3.11+** (for local development or SQLite fallback testing)
2. **Docker Desktop** (version 20+ with Docker Compose)
3. **Git** (for repository version tracking)
4. **Node.js (v18+) & npm** (required to run the Serverless Email Service local dev dependencies)
5. **Google Cloud Console account** (with the Google Calendar API enabled for sync workflows)

---

## ⚙️ Environment Variables

The project uses a `.env` file located in the root directory. To configure your settings, copy the provided `.env.example` file and fill in your details:

```bash
cp .env.example .env
```

| Key Name | Type | Description |
| :--- | :--- | :--- |
| `DEBUG` | Boolean | Enables Django development server details (`True` / `False`). |
| `SECRET_KEY` | String | Django secret cryptographic key used for session signing. |
| `ALLOWED_HOSTS` | List | Hostnames allowed to route to the Django application. |
| `USE_SQLITE` | Boolean | Set to `True` to bypass PostgreSQL and run local tests on SQLite. |
| `DB_NAME` | String | PostgreSQL database name (defaults to `hms_db`). |
| `DB_USER` | String | PostgreSQL database user (defaults to `hms_user`). |
| `DB_PASSWORD` | String | PostgreSQL secure database password. |
| `DB_HOST` | String | Database host address (e.g. `db` in Docker, `localhost` locally). |
| `DB_PORT` | Integer | Database connection port (defaults to `5432`). |
| `GOOGLE_CLIENT_ID` | String | Google OAuth2 client identification credentials. |
| `GOOGLE_CLIENT_SECRET`| String | Google OAuth2 client secret key. |
| `GOOGLE_REDIRECT_URI`| String | Authorized callback URL: `http://localhost:8000/oauth/callback/`. |
| `EMAIL_SERVICE_URL` | String | Local Serverless offline email handler API endpoint. |
| `SMTP_HOST` | String | SMTP email host (e.g. `mailpit` in Docker). |
| `SMTP_PORT` | Integer | SMTP email port (defaults to `1025`). |
| `EMAIL_FROM` | String | Dispatched system email address (defaults to `noreply@hospital.local`). |

*Note: Real secrets should NEVER be checked into source control. Placeholders are maintained inside the `.env.example` file.*

---

## ☁️ Google Calendar Setup

To configure two-way Google Calendar synchronization, follow these steps to retrieve credentials:

1. **Create Google Cloud Project**: Go to [Google Cloud Console](https://console.cloud.google.com/) and create a new project.
2. **Enable APIs**: Navigate to **API & Services > Library**, search for the **Google Calendar API**, and click **Enable**.
3. **Configure OAuth Consent Screen**:
   * Go to **OAuth Consent Screen**, select **External**, and input your support email and app name.
   * Add the `.../auth/calendar.events` scopes if planning live sync trials.
   * Add your Google accounts to the **Test Users** panel (required for OAuth testing).
4. **Create Client Credentials**:
   * Navigate to **Credentials > Create Credentials > OAuth Client ID**.
   * Set Application Type to **Web Application**.
   * Add **Authorized JavaScript Origins**: `http://localhost:8000`.
   * Add **Authorized Redirect URIs**: `http://localhost:8000/oauth/callback/`.
5. **Update Environment File**: Copy the generated **Client ID** and **Client Secret** into your `.env` file under `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.

---

## 🚀 Running the Project

### Option A: Standard Docker Build (Recommended)
1. **Clone the project and enter directory**:
   ```bash
   git clone <repository_url>
   cd <project_directory>
   ```
2. **Create environment configuration**:
   ```bash
   cp .env.example .env
   # Add your Google Calendar client IDs and secrets into the .env file
   ```
3. **Build and spin up the Docker services**:
   ```bash
   docker compose up --build
   ```
4. **Run database migrations inside the web container**:
   ```bash
   docker compose exec web python hms/manage.py migrate
   ```
5. **Seed the database with mock records and user accounts**:
   ```bash
   docker compose exec web python hms/manage.py seed_data
   ```
6. **Open browser interfaces**:
   * Main Portal: `http://localhost:8000/`
   * Mailpit Inbox: `http://localhost:8025/`

---

### Option B: Local Development Setup (SQLite Fallback)
If you want to run the project outside of Docker using a local SQLite database file:
1. **Activate virtual environment & install requirements**:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Initialize Environment Variables**:
   In your `.env` file, ensure `USE_SQLITE=True` is defined.
3. **Migrate and Seed**:
   ```bash
   python hms/manage.py migrate
   python hms/manage.py seed_data
   ```
4. **Start the Django Development Server**:
   ```bash
   python hms/manage.py runserver
   ```
5. **Launch Background Queue Worker**:
   Open a separate terminal window and run:
   ```bash
   python hms/manage.py process_tasks
   ```
6. **Launch Serverless Offline Email Service**:
   Open a separate terminal window, navigate to the `email-service` directory, and run:
   ```bash
   cd email-service
   npm install
   npx serverless offline
   ```

---

## 📦 Docker Services

The `docker-compose.yml` configures 5 isolated services:

* **`hms_db`** (`postgres:15-alpine`): Stores application models and audit records. Binds to port `5432`.
* **`hms_web`** (`Django App`): Evaluates queries, handles user sessions, and renders HTML/Tailwind templates. Binds to port `8000`.
* **`hms_worker`** (`Task Processor`): Polls the database queue to process asynchronous integrations (Google API calls, email dispatches). Runs `python hms/manage.py process_tasks`.
* **`hms_email_service`** (`Serverless offline`): An isolated NodeJS container emulating AWS Lambda. Formats email templates and passes SMTP requests to Mailpit. Binds to port `3000`.
* **`hms_mailpit`** (`axllent/mailpit`): Development SMTP server mapping port `1025`. Runs web inspector UI on port `8025` for email previewing.

---

## 🔌 Default Ports Mapping

| Service Name | Port | Description | URL |
| :--- | :--- | :--- | :--- |
| **Django Application** | `8000` | Main client frontend & administration panel | `http://localhost:8000/` |
| **PostgreSQL Database**| `5432` | Relational transactional database | `localhost:5432` |
| **Serverless Email API**| `3000` | NodeJS offline Lambda service endpoints | `http://localhost:3000/` |
| **Mailpit SMTP Server** | `1025` | Port used by Django and Serverless to route emails | `localhost:1025` |
| **Mailpit Web UI** | `8025` | Graphical web interface to inspect sent emails | `http://localhost:8025/` |

---

## 💾 Database Schema & Configuration

* **Production (PostgreSQL)**: Enforces relational constraints, UUID primary keys, and pessimistic locking queries during booking transactions.
* **Testing Fallback (SQLite)**: Automatically selected if `USE_SQLITE=True` is defined. Useful for fast, environment-independent unit tests.

To run the unit test suite under the SQLite environment:
```bash
$env:USE_SQLITE="True"
python hms/manage.py test hms
```

---

## 🔍 System Architecture & Design Decisions

### Modular Applications Separation
To avoid monolithic file bloat, domain logic is isolated inside specialized app folders (`accounts`, `appointments`, `doctors`, `medical_records`, `calendar_sync`, `notifications`, `admin_panel`, `common`, `core`).

### Concurrency Protection
To block double-bookings under concurrent client requests, Django locks selected slots inside an atomic transaction:
```python
slot = AvailabilitySlot.objects.select_for_update().get(id=slot_id)
```
This forces database threads to block and execute sequentially, guaranteeing slot integrity.

### Asynchronous Integrations
Calling third-party APIs (Google Cloud APIs) or executing HTTP POSTs (Serverless email) directly inside the booking transaction block introduces latency and vulnerability to network drops. MediBridge maps transactions to a database-backed `AsyncTask` model. A background worker polls the tasks and executes integration calls in separate process queues, protecting client experience.

### Soft-Delete Auditing
Removing doctor profiles transitions their account status to `REMOVED` instead of physically deleting them. This preserves historical bookings, clinical prescriptions, EMR charts, audits, and ratings, maintaining regulatory medical compliance.

---

## 🔑 Demo Access Credentials

The database contains pre-configured credentials for quick evaluation:

| Target Dashboard | Role / Persona | Username / Email | Password |
| :--- | :--- | :--- | :--- |
| **Admin Console** | System Administrator | `admin@medibridge.com` | `MediBridge@2024` |
| **Admin Console (Alt)** | System Administrator | `demo_admin@hospital.local` | `hms_admin123` |
| **Doctor Portal** | Cardiology Specialist | `doctor@medibridge.com` | `MediBridge@2024` |
| **Doctor Portal (Alt)** | Dermatology Specialist | `demo_doctor@hospital.local` | `hms_doctor123` |
| **Patient Portal** | Registered Patient | `patient@medibridge.com` | `MediBridge@2024` |
| **Patient Portal (Alt)** | Registered Patient | `demo_patient@example.com` | `hms_patient123` |

*To access Django's native administrative panel directly: `http://localhost:8000/admin/` (use `admin@medibridge.com`).*

---

## 🛠️ Assignment Requirements Mapping

The following matrix maps primary project design criteria to the implemented code solutions:

| Required Specification | Implemented Feature in MediBridge | Implementation File |
| :--- | :--- | :--- |
| **Session Authentication** | Role-based signup, login, and registration dashboards | [accounts/views.py](file:///c:/Users/agarw/Downloads/Task1/hms/accounts/views.py) |
| **Practice Slot Calculator** | Automated slot constructor checking doctor working hours, leaves, and buffers | [appointments/services.py](file:///c:/Users/agarw/Downloads/Task1/hms/appointments/services.py) |
| **Transactional Booking Locks**| Pessimistic row-locking block checking slot reservation parameters | [appointments/services.py](file:///c:/Users/agarw/Downloads/Task1/hms/appointments/services.py) |
| **Electronic Health Records** | EMR logs, consultation diaries, and structured prescriptions in JSON | [medical_records/models.py](file:///c:/Users/agarw/Downloads/Task1/hms/medical_records/models.py) |
| **Google Calendar API Sync** | OAuth Callback links, calendar event builder, update, and delete dispatches | [calendar_sync/services.py](file:///c:/Users/agarw/Downloads/Task1/hms/calendar_sync/services.py) |
| **Serverless Email Microservice**| Serverless NodeJS microservice templates dispatching SMTP mails | [email-service/handler.py](file:///c:/Users/agarw/Downloads/Task1/email-service/handler.py) |
| **Background Task Processor** | Poll-based worker running tasks asynchronously with backoff retries | [common/tasks.py](file:///c:/Users/agarw/Downloads/Task1/hms/common/tasks.py) |
| **System Diagnostics** | Health monitor checks testing PostgreSQL, Mailpit, Google APIs, and queue backlog | [admin_panel/views.py](file:///c:/Users/agarw/Downloads/Task1/hms/admin_panel/views.py) |
| **Soft Doctor Deletion** | Suspension, Soft-deletion status, booking cancels, slot purging, calendars delete | [doctors/services.py](file:///c:/Users/agarw/Downloads/Task1/hms/doctors/services.py) |

---

## ⚠️ Known Issues & Workarounds

* **Google OAuth Callback Port Limit**: The authorized Google Calendar Redirect URI in Google Cloud Console is bound to `http://localhost:8000/oauth/callback/`. Using a different port or host (e.g. `127.0.0.1`) will throw a redirect URL mismatch error.
* **Serverless Service Requirement**: If the Serverless Offline service container is stopped, email tasks in the database queue will fail, log retries, and retry inside the backoff window. The container stack must remain fully active.
* **Docker Dependencies**: Running the Postgres DB, Mailpit, and NodeJS lambda emulator requires Docker Desktop to be running. If running bare-metal, database configurations inside Django must be redirected to SQLite (`USE_SQLITE=True`).

---

## 🛡️ Production Notice

This project was developed for **educational and evaluation purposes** as a university submission. Before deploying this portal to a production server, implement the following security and architecture enhancements:
1. **Enforce HTTPS**: Route traffic through SSL/TLS certificates to encrypt session payloads and API requests.
2. **Secrets Storage**: Manage environment secrets (`SECRET_KEY`, `GOOGLE_CLIENT_SECRET`) using dedicated secret managers (e.g. AWS Secrets Manager, HashiCorp Vault) rather than static `.env` text files.
3. **Reverse Proxy (Nginx)**: Deploy a production proxy like Nginx or Traefik in front of Gunicorn/web containers to manage SSL termination and serve static assets.
4. **SMTP Service**: Transition from Mailpit development SMTP capture to production APIs (e.g. Amazon SES, SendGrid).
5. **Application Server (Gunicorn)**: Serve the Django web application via multi-worker production WSGI services rather than the development server `runserver`.
6. **Centralized Log Manager**: Route clinical diagnostic audits and queue records to persistent telemetry services (e.g., Elasticsearch, CloudWatch).

---

## 🔬 AI Usage

For transparency regarding AI-assisted development, engineering design, code refactoring, styling, and verification scripts, see the [ai-tool-usage-log/](file:///c:/Users/agarw/Downloads/Task1/ai-tool-usage-log/usage_notes.md) directory.

---

## 🚀 Future Improvements

* **Video Consultation**: Embed tele-health capabilities using WebRTC integrations.
* **SMS Notifications**: Connect Twilio SMS gateways to trigger text alerts for scheduled appointments.
* **Payment Gateways**: Incorporate Stripe checkout integrations inside the confirmation step of the booking wizard.
* **Multi-Hospital Support**: Support administrative multi-clinic directories.
* **Cloud Deployment**: Deployment scripts targeting AWS ECS or Kubernetes clusters.
* **Clinical Decision Support**: AI-assisted clinical diagnosis verification matching EMR inputs against standard medical taxonomies.

---

## 📄 License

This project is licensed under the MIT License. See the LICENSE file for details.
