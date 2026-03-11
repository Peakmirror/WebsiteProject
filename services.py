from __future__ import annotations

from typing import Iterable, List, Optional, Tuple

from db import get_conn


class ServiceNotFoundError(Exception):
    # Raised when trying to remove a service that does not exist.
    pass


def list_services() -> List[Tuple[int, str, float]]:
    # Return all services ordered by name for display in UI.
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price FROM services ORDER BY name")
    rows = cursor.fetchall()
    conn.close()
    return [(row["id"], row["name"], row["price"]) for row in rows]


def add_service(name: str, price: float) -> None:
    # Add service once; duplicate names are ignored.
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO services (name, price) VALUES (?, ?)",
        (name, price),
    )
    conn.commit()
    conn.close()


def remove_service(service_id: int) -> None:
    # Delete service and raise custom error if id is unknown.
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM services WHERE id = ?", (service_id,))
    if cursor.rowcount == 0:
        conn.close()
        raise ServiceNotFoundError(f"Service with id {service_id} not found")
    conn.commit()
    conn.close()


def seed_services(defaults: Optional[Iterable[Tuple[str, float]]] = None) -> None:
    # Insert starter services for first-time setup.
    if defaults is None:
        defaults = [
            ("Consultation", 49.0),
            ("Follow-up", 29.0),
            ("Premium Support", 99.0),
        ]
    for name, price in defaults:
        add_service(name, price)