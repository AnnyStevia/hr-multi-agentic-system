from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.employees.repository import EmployeeRepository
from app.modules.profile.repository import ProfileRepository
from app.modules.profile.service import ProfileService
from app.shared.storage import StorageService, get_storage_service


def get_profile_service(
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> ProfileService:
    return ProfileService(ProfileRepository(db), EmployeeRepository(db), storage)
