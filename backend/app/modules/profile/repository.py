from sqlalchemy.orm import Session

from app.modules.profile.models import EmployeeEducation, EmployeeExperience


class ProfileRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_educations(self, employee_id: int) -> list[EmployeeEducation]:
        return (
            self.db.query(EmployeeEducation)
            .filter(EmployeeEducation.employee_id == employee_id)
            .order_by(EmployeeEducation.start_date.desc(), EmployeeEducation.id.desc())
            .all()
        )

    def get_education(self, education_id: int) -> EmployeeEducation | None:
        return (
            self.db.query(EmployeeEducation)
            .filter(EmployeeEducation.id == education_id)
            .first()
        )

    def get_education_for_employee(
        self, education_id: int, employee_id: int
    ) -> EmployeeEducation | None:
        return (
            self.db.query(EmployeeEducation)
            .filter(
                EmployeeEducation.id == education_id,
                EmployeeEducation.employee_id == employee_id,
            )
            .first()
        )

    def add_education(self, education: EmployeeEducation) -> EmployeeEducation:
        self.db.add(education)
        self.db.commit()
        self.db.refresh(education)
        return education

    def save_education(self, education: EmployeeEducation) -> EmployeeEducation:
        self.db.commit()
        self.db.refresh(education)
        return education

    def delete_education(self, education: EmployeeEducation) -> None:
        self.db.delete(education)
        self.db.commit()

    def list_experiences(self, employee_id: int) -> list[EmployeeExperience]:
        return (
            self.db.query(EmployeeExperience)
            .filter(EmployeeExperience.employee_id == employee_id)
            .order_by(EmployeeExperience.start_date.desc(), EmployeeExperience.id.desc())
            .all()
        )

    def get_experience(self, experience_id: int) -> EmployeeExperience | None:
        return (
            self.db.query(EmployeeExperience)
            .filter(EmployeeExperience.id == experience_id)
            .first()
        )

    def get_experience_for_employee(
        self, experience_id: int, employee_id: int
    ) -> EmployeeExperience | None:
        return (
            self.db.query(EmployeeExperience)
            .filter(
                EmployeeExperience.id == experience_id,
                EmployeeExperience.employee_id == employee_id,
            )
            .first()
        )

    def add_experience(self, experience: EmployeeExperience) -> EmployeeExperience:
        self.db.add(experience)
        self.db.commit()
        self.db.refresh(experience)
        return experience

    def save_experience(self, experience: EmployeeExperience) -> EmployeeExperience:
        self.db.commit()
        self.db.refresh(experience)
        return experience

    def delete_experience(self, experience: EmployeeExperience) -> None:
        self.db.delete(experience)
        self.db.commit()

    def count_educations(self, employee_id: int) -> int:
        return (
            self.db.query(EmployeeEducation)
            .filter(EmployeeEducation.employee_id == employee_id)
            .count()
        )

    def count_experiences(self, employee_id: int) -> int:
        return (
            self.db.query(EmployeeExperience)
            .filter(EmployeeExperience.employee_id == employee_id)
            .count()
        )
