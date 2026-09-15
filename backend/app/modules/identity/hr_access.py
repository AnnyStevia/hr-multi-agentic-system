from fastapi import Depends, HTTPException, status

from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User


def require_hr_staff(*required_permissions: str):
    async def checker(current_user: User = Depends(get_current_user)) -> User:
        roles = {user_role.role.name for user_role in current_user.user_roles}
        if not {"admin", "hr"} & roles:
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
