from email.mime.text import MIMEText
from db import get_conn
import datetime
import calendar as cal_module
import os
import smtplib


def get_available_slots(year, month):
    """Returns list of (day, hour) tuples that are not yet booked and are in the future."""
    # Load already booked times for the selected month.
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT appointment_time FROM appointments WHERE appointment_time LIKE ?",
        (f"{year}-{month:02d}%",),
    )
    booked = {row["appointment_time"] for row in cursor.fetchall()}
    conn.close()

    today = datetime.date.today()
    slots = []
    # Build all future hourly slots from 10:00 to 18:00.
    for week in cal_module.monthcalendar(year, month):
        for day in week:
            if day == 0:
                continue
            if datetime.date(year, month, day) <= today:
                continue
            for hour in range(10, 19):
                slot_time = datetime.datetime(year, month, day, hour).isoformat()
                if slot_time not in booked:
                    slots.append((day, hour))
    return slots


def book_appointment(username, service_id, day, hour, email, phone_number):
    """Returns (True, None) on success or (False, error_message) on failure."""
    # Booking always targets the current month shown in the UI.
    year = datetime.datetime.now().year
    month = datetime.datetime.now().month
    appointment_time = datetime.datetime(year, month, day, hour).isoformat()

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM appointments WHERE appointment_time = ?", (appointment_time,)
    )
    if cursor.fetchone():
        conn.close()
        return False, "That time slot is already booked. Please choose another."

    # Keep user email up to date from the booking form.
    if email:
        cursor.execute("UPDATE users SET email = ? WHERE username = ?", (email, username))
    cursor.execute(
        "INSERT INTO appointments (username, appointment_time, service_id, phone_number) VALUES (?, ?, ?, ?)",
        (username, appointment_time, service_id, phone_number),
    )
    conn.commit()
    conn.close()
    # Send confirmation only when email notifications are configured.
    if email:
        _send_confirmation(email, day, month, year, hour)
    return True, None


def get_user_appointments(username):
    """Returns a list of dicts for all appointments belonging to username."""
    # Join services so the UI can show service name and price.
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT a.id, a.appointment_time, a.phone_number,
               s.name AS service_name, s.price
        FROM appointments a
        LEFT JOIN services s ON a.service_id = s.id
        WHERE a.username = ?
        ORDER BY a.appointment_time
        """,
        (username,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def cancel_appointment(appointment_id, username):
    """Returns (True, None) on success or (False, error_message) on failure."""
    # Only allow canceling appointments owned by this user.
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM appointments WHERE id = ? AND username = ?",
        (appointment_id, username),
    )
    if not cursor.fetchone():
        conn.close()
        return False, "Appointment not found."
    cursor.execute("DELETE FROM appointments WHERE id = ?", (appointment_id,))
    conn.commit()
    conn.close()
    return True, None


def get_all_appointments():
    """Returns all appointments (for admin view)."""
    # Admin query that returns every booking in time order.
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT a.id, a.username, a.appointment_time, a.phone_number,
               s.name AS service_name, s.price
        FROM appointments a
        LEFT JOIN services s ON a.service_id = s.id
        ORDER BY a.appointment_time
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def _send_confirmation(email, day, month, year, hour):
    # Read email settings from environment variables.
    sender = os.environ.get("EMAIL_SENDER", "")
    password = os.environ.get("EMAIL_APP_PASSWORD", "")
    if not sender or not password:
        return
    try:
        # If SMTP fails, booking still remains successful.
        msg = MIMEText(
            f"Your appointment has been confirmed for {day}/{month}/{year} at {hour}:00.\n\nThank you for booking with us."
        )
        msg["Subject"] = "Appointment Confirmation"
        msg["From"] = sender
        msg["To"] = email
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.send_message(msg)
    except Exception:
        pass
