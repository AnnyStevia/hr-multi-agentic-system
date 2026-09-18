from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import Role, User, UserRole

HR_STAFF_ROLE_NAMES = frozenset({"admin", "hr"})


def list_hr_staff_user_ids(db: Session) -> list[int]:
    """Return active user ids with HR or admin role (deduplicated, sorted)."""
    rows = (
        db.query(User.id)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .filter(User.is_active.is_(True), Role.name.in_(HR_STAFF_ROLE_NAMES))
        .distinct()
        .order_by(User.id.asc())
        .all()
    )
    return [row[0] for row in rows]


def require_hr_staff(*required_permissions: str):
    async def checker(current_user: User = Depends(get_current_user)) -> User:
        roles = {user_role.role.name for user_role in current_user.user_roles}
        if not HR_STAFF_ROLE_NAMES & roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Requires HR or administrator access",
            )
        if required_permissions:
            user_permissions: set[str] = set()
            for user_role in current_user.user_roles:
                for role_perm in user_role.role.role_permissions:
                    user_permissions.add(role_perm.permission.name)
            missing = set(required_permissions) - user_permissions
            if missing:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing permissions: {', '.join(sorted(missing))}",
                )
        return current_user

    return checker
