# HENalytics

HENalytics is a Django-based poultry management system for egg production, flock records, sales records, reports, and forecasting.

## Repository Access

### Option 1: Clone the Main Repository

Use this when the university server or teammate should directly download the latest project code.

```powershell
git clone https://github.com/6aboy/Henalytics.git
cd Henalytics
```

To get future updates:

```powershell
git pull origin main
```

### Option 2: Fork First, Then Clone

Use this when a teammate wants their own copy on GitHub before making changes.

1. Open the repository on GitHub.
2. Click `Fork`.
3. Clone the forked repository:

```powershell
git clone https://github.com/YOUR_USERNAME/Henalytics.git
cd Henalytics
```

To keep the fork updated with the original repository:

```powershell
git remote add upstream https://github.com/6aboy/Henalytics.git
git fetch upstream
git checkout main
git pull upstream main
git push origin main
```

## Local Setup

From the project root:

```powershell
python -m venv venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd henalytics
python manage.py migrate
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

## Server Setup Notes

For deployment, install the requirements, apply migrations, and collect static files:

```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd henalytics
python manage.py migrate
python manage.py collectstatic --noinput
```

The project includes local static vendor files for Bootstrap, DataTables, export buttons, SweetAlert2, and Plotly, so the main interface can work without relying on CDN internet access.

## Database

The SQLite database file is kept in the codebase:

```text
henalytics/db.sqlite3
```

If the server should use the included database, keep this file when transferring or cloning the project.

## Dataset Files

Raw Excel datasets are not tracked in Git. Keep local dataset files inside:

```text
datasets/
```

The historical import command can read files from this folder.

## Common Git Commands

Check current changes:

```powershell
git status
```

Stage selected files:

```powershell
git add path/to/file
```

Commit changes:

```powershell
git commit -m "describe your change"
```

Push changes:

```powershell
git push origin main
```

If push is rejected because the remote has newer changes:

```powershell
git pull --rebase origin main
git push origin main
```
