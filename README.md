# MendMate

A peer-to-peer web app that connects people who need help with small tasks to nearby helpers.
This is **Project Development 1: Account Feature** (IT 317, Section G10).

**Tech stack:** Django (full stack, Django templates) + PostgreSQL (Supabase).

## Features in this phase
- **Registration** with validation (required fields, valid email, unique username/email, matching passwords). Passwords are hashed by Django.
- **Login / Logout** with error and success messages. Pages that need a login send logged-out users to the login page.
- **Role-based dashboards**: Task Poster, Helper, and Admin. Each user goes to their own dashboard and cannot open another role's dashboard by typing its URL.
- **User profile**: view and update your own details (name, email, contact number, barangay/area, skills for helpers, bio, profile photo).

## Run it on your computer (Windows PowerShell)
```powershell
git clone https://github.com/YOUR-USERNAME/MendMate-Abella-Ernest-G10.git
cd MendMate-Abella-Ernest-G10

python -m venv venv
venv\Scripts\Activate.ps1

pip install -r requirements.txt

copy .env.example .env
# open .env and fill in SECRET_KEY and your Supabase DATABASE_URL

python manage.py migrate
python manage.py createsuperuser     # this account becomes the Admin role
python manage.py runserver
```
Open http://127.0.0.1:8000/

## Run the tests
```powershell
python manage.py test
```

## Roles
| Role | How you get it | Dashboard |
|---|---|---|
| Task Poster | Choose it when you sign up | `/dashboard/poster/` |
| Helper | Choose it when you sign up | `/dashboard/helper/` |
| Admin | Created with `createsuperuser` | `/dashboard/admin/` |

## Project structure
```
mendmate/        project settings and main urls
accounts/        the Account Feature (model, forms, views, urls, tests)
templates/       HTML pages (Django templates)
static/css/      stylesheet
```
Secrets (`.env`) are never pushed to GitHub.
