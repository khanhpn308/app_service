"""Deactivate users whose account period has ended (remaining days <= 0)."""

from datetime import date

from sqlalchemy.orm import Session

from app.models.user import User


def deactivate_expired_users(db: Session) -> None:
    """Set status to deactive when today >= expired_at (remaining calendar days <= 0)."""
    today = date.today()
    rows = db.query(User).filter(User.status == "active").all()
    changed = False
    for u in rows:
        if u.expired_at is not None and (u.expired_at - today).days <= 0:
            u.status = "deactive"
            changed = True
    if changed:
        db.commit()
