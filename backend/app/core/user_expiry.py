"""
Đồng bộ trạng thái tài khoản theo ngày: user có ``expired_at`` ≤ hôm nay → ``status = deactive``.

Gọi từ login và một số endpoint đọc user để giảm trường hợp token còn hạn nhưng tài khoản đã quá hạn theo lịch.
"""

from datetime import date

from sqlalchemy.orm import Session

from app.models.user import User


def deactivate_expired_users(db: Session) -> None:
    """
    Duyệt user đang ``active``; nếu ``expired_at`` không null và còn ≤ 0 ngày so với hôm nay thì chuyển ``deactive``.

    Commit một lần nếu có thay đổi.
    """
    today = date.today()
    rows = db.query(User).filter(User.status == "active").all()
    changed = False
    for u in rows:
        if u.expired_at is not None and (u.expired_at - today).days <= 0:
            u.status = "deactive"
            changed = True
    if changed:
        db.commit()
