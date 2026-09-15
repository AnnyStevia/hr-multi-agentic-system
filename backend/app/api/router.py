from fastapi import APIRouter

from app.api.v1 import (
    applications,
    auth,
    career_applications,
    career_interviews,
    careers,
    departments,
    employees,
    interviews,
    jobs,
    notifications,
    users,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(departments.router)
api_router.include_router(employees.router)
api_router.include_router(jobs.router)
api_router.include_router(applications.router)
api_router.include_router(careers.router)
api_router.include_router(career_applications.router)
api_router.include_router(career_interviews.router)
api_router.include_router(notifications.router)
api_router.include_router(interviews.router)
