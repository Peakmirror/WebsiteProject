# BookIt — Online Appointment Booking

A simple Flask web app for booking and managing appointments.  
Users can register, pick a service, choose a time slot, and cancel or view their bookings.  
Admins can manage services, view all appointments, and promote users.

## Features

- User registration with password strength rules and common-password check
- Login with lockout after 3 failed attempts
- Book appointments from available monthly time slots
- Cancel upcoming appointments
- Admin panel to manage services and users
- Password reset via email (optional)

## Tech stack

- Python / Flask
- SQLite (via the built-in `sqlite3` module)
- Jinja2 templates
- Plain CSS

## Getting started

### 1. Clone the repository

```bash
git clone https://github.com/your-username/your-repo.git
cd your-repo
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Set environment variables

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

At minimum, set a strong `SECRET_KEY`.

### 4. Run the app

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser.

**Default admin credentials:**  
Username: `admin`  
Password: `Admin@1234!`

Change these immediately after first login.

## Email notifications (optional)

Set `EMAIL_SENDER` and `EMAIL_APP_PASSWORD` in your `.env` file.  
If these are not set the app runs fine — confirmation and reset emails are simply skipped.

## Notes

- `users.db` is created automatically on first run — do not commit it.
- `rockyou.txt` is used locally to block common passwords — download separately if needed.
- Do **not** run with `debug=True` in production.


## Future plans
- Add more features, like better usability for site admins, technician availability (some others)
- Make the frontend more appealing and nicer to look at
Note that this is on the back burner currently but if you happen to have interest in this project, please feel free to contact me (or add them yourself)
