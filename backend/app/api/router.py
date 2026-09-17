from fastapi import APIRouter

from app.api.v1 import (
    applications,
    auth,
    career_applications,
    career_interviews,
    careers,
    departments,
    documents,
    employees,
    interviews,
    jobs,
    notifications,
    onboarding,
    training,
    users,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(departments.router)
api_router.include_router(employees.router)
api_router.include_router(documents.employees_router)
api_router.include_router(documents.me_router)
api_router.include_router(onboarding.employee_onboarding_router)
api_router.include_router(onboarding.me_router)
api_router.include_router(onboarding.router)
api_router.include_router(training.catalog_router)
api_router.include_router(training.onboarding_router)
api_router.include_router(training.me_router)
api_router.include_router(jobs.router)
api_router.include_router(applications.router)
api_router.include_router(careers.router)
api_router.include_router(career_applications.router)
api_router.include_router(career_applications.applications_router)
api_router.include_router(career_interviews.router)
api_router.include_router(notifications.router)
api_router.include_router(interviews.router)
