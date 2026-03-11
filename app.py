# app.py
from flask import Flask, render_template, request, redirect, url_for, session, flash
from auth import register_user, login_user, request_password_reset, reset_password_token
from services import list_services, add_service, remove_service, ServiceNotFoundError
from appointments import (
    book_appointment,
    get_user_appointments,
    cancel_appointment,
    get_all_appointments,
    get_available_slots,
)
from db import init_db, seed_admin, is_admin, get_conn
import os
import datetime
import functools

app = Flask(__name__)
# Secret key is used for sessions and flash messages.
app.secret_key = os.environ.get("SECRET_KEY", "dev-key-please-change-in-production")

# Create tables and ensure default admin exists on app startup.
init_db()
seed_admin()


def login_required(f):
    # Protect routes that require a logged-in user.
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if "username" not in session:
            flash("Please log in to continue.", "info")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    # Protect routes that require admin privileges.
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if "username" not in session or not session.get("is_admin"):
            flash("Admin access only.", "error")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return wrapper


@app.route("/")
def index():
    # If already logged in, go straight to dashboard.
    if "username" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    # Handle account creation form.
    if "username" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        ok, err = register_user(email, username, password)
        if ok:
            flash("Account created! You can now log in.", "success")
            return redirect(url_for("login"))
        flash(err, "error")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    # Handle sign-in and session setup.
    if "username" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user, err = login_user(username, password)
        if user:
            session["username"] = user
            session["is_admin"] = is_admin(user)
            return redirect(url_for("dashboard"))
        flash(err, "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    # Clear all session data to log the user out safely.
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    # Show only a short list of upcoming appointments.
    username = session["username"]
    appointments = get_user_appointments(username)
    now = datetime.datetime.now().isoformat()
    upcoming = [a for a in appointments if a["appointment_time"] >= now]
    return render_template("dashboard.html", username=username, upcoming=upcoming[:3])


@app.route("/book", methods=["GET", "POST"])
@login_required
def book():
    # Show booking form and available slots for the current month.
    username = session["username"]
    services = list_services()
    now = datetime.datetime.now()
    year, month = now.year, now.month
    slots = get_available_slots(year, month)

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    user_email = row["email"] if row else ""

    if request.method == "POST":
        # Parse form values and validate slot/service selection.
        slot_val = request.form.get("slot", "")
        service_id_str = request.form.get("service_id", "")
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        try:
            day_str, hour_str = slot_val.split(":")
            day = int(day_str)
            hour = int(hour_str)
            service_id = int(service_id_str)
        except (ValueError, AttributeError):
            flash("Please select a valid time slot and service.", "error")
            return render_template("book.html", services=services, slots=slots, year=year, month=month, user_email=user_email)
        if not email:
            flash("Email is required.", "error")
            return render_template("book.html", services=services, slots=slots, year=year, month=month, user_email=user_email)
        # Create the booking in the database.
        ok, err = book_appointment(username, service_id, day, hour, email, phone)
        if ok:
            flash("Appointment booked successfully!", "success")
            return redirect(url_for("my_appointments"))
        flash(err, "error")
    return render_template("book.html", services=services, slots=slots, year=year, month=month, user_email=user_email)


@app.route("/appointments")
@login_required
def my_appointments():
    # List all appointments for the current user.
    username = session["username"]
    appointments = get_user_appointments(username)
    now = datetime.datetime.now().isoformat()
    return render_template("my_appointments.html", appointments=appointments, now=now)


@app.route("/appointments/cancel/<int:appt_id>", methods=["POST"])
@login_required
def cancel(appt_id):
    # Allow users to cancel only their own appointment.
    ok, err = cancel_appointment(appt_id, session["username"])
    if ok:
        flash("Appointment cancelled.", "success")
    else:
        flash(err or "Could not cancel appointment.", "error")
    return redirect(url_for("my_appointments"))


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    # Start reset flow without revealing whether email exists.
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        request_password_reset(email)
        flash("If that email is registered, a reset link has been sent.", "info")
        return redirect(url_for("login"))
    return render_template("forgot_password.html")


@app.route("/reset-password", methods=["GET", "POST"])
def reset_pw():
    # Complete password reset using the token from email.
    token = request.args.get("token", "")
    if request.method == "POST":
        token = request.form.get("token", "")
        new_password = request.form.get("password", "")
        ok, err = reset_password_token(token, new_password)
        if ok:
            flash("Password reset successfully. You can now log in.", "success")
            return redirect(url_for("login"))
        flash(err, "error")
    return render_template("reset_password.html", token=token)


@app.route("/admin")
@admin_required
def admin():
    # Admin overview: services, appointments, and users.
    services = list_services()
    appointments = get_all_appointments()
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT username, email, is_admin, created_at FROM users ORDER BY username")
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return render_template("admin.html", services=services, appointments=appointments, users=users)


@app.route("/admin/service/add", methods=["POST"])
@admin_required
def admin_add_service():
    # Add a new service from admin form input.
    name = request.form.get("name", "").strip()
    try:
        price = float(request.form.get("price", 0))
    except ValueError:
        flash("Invalid price.", "error")
        return redirect(url_for("admin"))
    if not name:
        flash("Service name is required.", "error")
        return redirect(url_for("admin"))
    add_service(name, price)
    flash(f"Service '{name}' added.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/service/remove/<int:svc_id>", methods=["POST"])
@admin_required
def admin_remove_service(svc_id):
    # Remove an existing service by id.
    try:
        remove_service(svc_id)
        flash("Service removed.", "success")
    except ServiceNotFoundError:
        flash("Service not found.", "error")
    return redirect(url_for("admin"))


@app.route("/admin/promote", methods=["POST"])
@admin_required
def admin_promote():
    # Promote a normal user account to admin.
    target = request.form.get("username", "").strip()
    if not target:
        flash("Username required.", "error")
        return redirect(url_for("admin"))
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_admin = 1 WHERE username = ?", (target,))
    if cursor.rowcount > 0:
        conn.commit()
        flash(f"{target} is now an admin.", "success")
    else:
        flash("User not found.", "error")
    conn.close()
    return redirect(url_for("admin"))


if __name__ == "__main__":
    # Development server entrypoint.
    app.run(debug=True)