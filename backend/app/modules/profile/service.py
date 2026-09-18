from datetime import date
from io import BytesIO

from app.modules.employees.models import Employee
from app.modules.employees.repository import EmployeeRepository
from app.modules.employees.service import _normalize_phone
from app.modules.profile.image_validation import sanitize_filename, validate_profile_picture
from app.modules.profile.models import EmployeeEducation, EmployeeExperience
from app.modules.profile.repository import ProfileRepository
from app.modules.profile.schemas import (
    EducationCreateRequest,
    EducationResponse,
    EducationUpdateRequest,
    EmployeeProfileResponse,
    ExperienceCreateRequest,
    ExperienceResponse,
    ExperienceUpdateRequest,
    PresignedProfilePictureUrlResponse,
    ProfileUpdateRequest,
)
from app.shared.exceptions import AppException
from app.shared.storage.base import StorageService
from app.shared.storage.exceptions import StorageException

PRESIGNED_URL_EXPIRES_IN = 300


class ProfileService:
    def __init__(
        self,
        repository: ProfileRepository,
        employees: EmployeeRepository,
        storage: StorageService,
    ):
        self.repository = repository
        self.employees = employees
        self.storage = storage

    def get_for_user(self, user_id: int) -> Employee:
        return self._require_employee_for_user(user_id)

    def get_for_employee(self, employee_id: int) -> Employee:
        return self._require_employee(employee_id)

    def update_for_user(self, user_id: int, payload: ProfileUpdateRequest) -> Employee:
        employee = self._require_employee_for_user(user_id)
        data = payload.model_dump(exclude_unset=True)

        if "phone" in data and data["phone"] is not None:
            employee.phone = _normalize_phone(data["phone"])

        if "date_of_birth" in data:
            dob = data["date_of_birth"]
            if dob is not None and dob > date.today():
                raise AppException("Date of birth cannot be in the future", status_code=400)
            employee.date_of_birth = dob

        for field in ("address", "city", "country"):
            if field in data:
                value = data[field]
                if value is not None:
                    value = value.strip() or None
                setattr(employee, field, value)

        return self.employees.save(employee)

    def upload_picture_for_user(
        self,
        user_id: int,
        *,
        filename: str | None,
        content_type: str | None,
        content: bytes,
    ) -> Employee:
        employee = self._require_employee_for_user(user_id)
        upload = validate_profile_picture(filename, content_type, content)
        storage_key = _build_picture_key(employee.id, upload.filename)
        previous_key = employee.profile_picture_storage_key

        try:
            self.storage.upload_file(
                storage_key,
                BytesIO(upload.content),
                content_type=upload.content_type,
            )
        except StorageException as exc:
            raise AppException(exc.message, status_code=exc.status_code) from exc

        if previous_key and previous_key != storage_key:
            try:
                self.storage.delete_file(previous_key)
            except StorageException:
                pass

        employee.profile_picture_storage_key = storage_key
        employee.profile_picture_content_type = upload.content_type
        employee.profile_picture_filename = upload.filename
        employee.profile_picture_size_bytes = len(upload.content)
        return self.employees.save(employee)

    def presigned_url_for_user(self, user_id: int) -> PresignedProfilePictureUrlResponse:
        employee = self._require_employee_for_user(user_id)
        return self._presign(employee)

    def presigned_url_for_employee(self, employee_id: int) -> PresignedProfilePictureUrlResponse:
        employee = self._require_employee(employee_id)
        return self._presign(employee)

    def delete_picture_for_user(self, user_id: int) -> None:
        employee = self._require_employee_for_user(user_id)
        key = employee.profile_picture_storage_key
        if not key:
            raise AppException("Profile picture not found", status_code=404)
        try:
            self.storage.delete_file(key)
        except StorageException:
            pass
        employee.profile_picture_storage_key = None
        employee.profile_picture_content_type = None
        employee.profile_picture_filename = None
        employee.profile_picture_size_bytes = None
        self.employees.save(employee)

    def list_educations_for_user(self, user_id: int) -> list[EmployeeEducation]:
        employee = self._require_employee_for_user(user_id)
        return self.repository.list_educations(employee.id)

    def list_educations_for_employee(self, employee_id: int) -> list[EmployeeEducation]:
        self._require_employee(employee_id)
        return self.repository.list_educations(employee_id)

    def create_education_for_user(
        self, user_id: int, payload: EducationCreateRequest
    ) -> EmployeeEducation:
        employee = self._require_employee_for_user(user_id)
        _validate_date_range(payload.start_date, payload.end_date)
        education = EmployeeEducation(
            employee_id=employee.id,
            institution=payload.institution.strip(),
            degree=payload.degree.strip(),
            field_of_study=payload.field_of_study.strip(),
            start_date=payload.start_date,
            end_date=payload.end_date,
            description=_optional_text(payload.description),
        )
        return self.repository.add_education(education)

    def update_education_for_user(
        self, user_id: int, education_id: int, payload: EducationUpdateRequest
    ) -> EmployeeEducation:
        employee = self._require_employee_for_user(user_id)
        education = self.repository.get_education_for_employee(education_id, employee.id)
        if education is None:
            raise AppException("Education record not found", status_code=404)

        data = payload.model_dump(exclude_unset=True)
        if "institution" in data and data["institution"] is not None:
            education.institution = data["institution"].strip()
        if "degree" in data and data["degree"] is not None:
            education.degree = data["degree"].strip()
        if "field_of_study" in data and data["field_of_study"] is not None:
            education.field_of_study = data["field_of_study"].strip()
        if "start_date" in data and data["start_date"] is not None:
            education.start_date = data["start_date"]
        if "end_date" in data:
            education.end_date = data["end_date"]
        if "description" in data:
            education.description = _optional_text(data["description"])

        _validate_date_range(education.start_date, education.end_date)
        return self.repository.save_education(education)

    def delete_education_for_user(self, user_id: int, education_id: int) -> None:
        employee = self._require_employee_for_user(user_id)
        education = self.repository.get_education_for_employee(education_id, employee.id)
        if education is None:
            raise AppException("Education record not found", status_code=404)
        self.repository.delete_education(education)

    def list_experiences_for_user(self, user_id: int) -> list[EmployeeExperience]:
        employee = self._require_employee_for_user(user_id)
        return self.repository.list_experiences(employee.id)

    def list_experiences_for_employee(self, employee_id: int) -> list[EmployeeExperience]:
        self._require_employee(employee_id)
        return self.repository.list_experiences(employee_id)

    def create_experience_for_user(
        self, user_id: int, payload: ExperienceCreateRequest
    ) -> EmployeeExperience:
        employee = self._require_employee_for_user(user_id)
        _validate_date_range(payload.start_date, payload.end_date)
        experience = EmployeeExperience(
            employee_id=employee.id,
            company=payload.company.strip(),
            position=payload.position.strip(),
            description=_optional_text(payload.description),
            start_date=payload.start_date,
            end_date=payload.end_date,
        )
        return self.repository.add_experience(experience)

    def update_experience_for_user(
        self, user_id: int, experience_id: int, payload: ExperienceUpdateRequest
    ) -> EmployeeExperience:
        employee = self._require_employee_for_user(user_id)
        experience = self.repository.get_experience_for_employee(experience_id, employee.id)
        if experience is None:
            raise AppException("Experience record not found", status_code=404)

        data = payload.model_dump(exclude_unset=True)
        if "company" in data and data["company"] is not None:
            experience.company = data["company"].strip()
        if "position" in data and data["position"] is not None:
            experience.position = data["position"].strip()
        if "start_date" in data and data["start_date"] is not None:
            experience.start_date = data["start_date"]
        if "end_date" in data:
            experience.end_date = data["end_date"]
        if "description" in data:
            experience.description = _optional_text(data["description"])

        _validate_date_range(experience.start_date, experience.end_date)
        return self.repository.save_experience(experience)

    def delete_experience_for_user(self, user_id: int, experience_id: int) -> None:
        employee = self._require_employee_for_user(user_id)
        experience = self.repository.get_experience_for_employee(experience_id, employee.id)
        if experience is None:
            raise AppException("Experience record not found", status_code=404)
        self.repository.delete_experience(experience)

    def is_personal_information_complete(self, employee_id: int) -> bool:
        employee = self.employees.get_by_id(employee_id)
        if employee is None:
            return False
        return bool(
            employee.date_of_birth
            and employee.phone
            and employee.address
            and employee.city
            and employee.country
        )

    def has_profile_picture(self, employee_id: int) -> bool:
        employee = self.employees.get_by_id(employee_id)
        return bool(employee and employee.profile_picture_storage_key)

    def has_education(self, employee_id: int) -> bool:
        return self.repository.count_educations(employee_id) > 0

    def has_experience(self, employee_id: int) -> bool:
        return self.repository.count_experiences(employee_id) > 0

    def _presign(self, employee: Employee) -> PresignedProfilePictureUrlResponse:
        if not employee.profile_picture_storage_key:
            raise AppException("Profile picture not found", status_code=404)
        try:
            url = self.storage.generate_presigned_url(
                employee.profile_picture_storage_key,
                expires_in=PRESIGNED_URL_EXPIRES_IN,
                filename=employee.profile_picture_filename or "profile-picture",
                download=False,
            )
        except StorageException as exc:
            raise AppException(exc.message, status_code=exc.status_code) from exc
        return PresignedProfilePictureUrlResponse(
            url=url,
            filename=employee.profile_picture_filename or "profile-picture",
            content_type=employee.profile_picture_content_type or "application/octet-stream",
            expires_in=PRESIGNED_URL_EXPIRES_IN,
        )

    def _require_employee_for_user(self, user_id: int) -> Employee:
        employee = self.employees.get_by_user_id(user_id)
        if employee is None:
            raise AppException("Employee profile not found", status_code=404)
        return employee

    def _require_employee(self, employee_id: int) -> Employee:
        employee = self.employees.get_by_id(employee_id)
        if employee is None:
            raise AppException("Employee not found", status_code=404)
        return employee


def build_profile_response(employee: Employee) -> EmployeeProfileResponse:
    return EmployeeProfileResponse(
        employee_id=employee.id,
        employee_number=employee.employee_number,
        first_name=employee.first_name,
        last_name=employee.last_name,
        full_name=employee.full_name,
        email=employee.email,
        phone=employee.phone,
        department_id=employee.department_id,
        department=employee.department.name if employee.department else "",
        position=employee.position,
        hire_date=employee.hire_date,
        date_of_birth=employee.date_of_birth,
        address=employee.address,
        city=employee.city,
        country=employee.country,
        has_profile_picture=bool(employee.profile_picture_storage_key),
        profile_picture_filename=employee.profile_picture_filename,
        profile_picture_content_type=employee.profile_picture_content_type,
    )


def build_education_response(education: EmployeeEducation) -> EducationResponse:
    return EducationResponse.model_validate(education)


def build_experience_response(experience: EmployeeExperience) -> ExperienceResponse:
    return ExperienceResponse.model_validate(experience)


def _build_picture_key(employee_id: int, filename: str) -> str:
    safe = sanitize_filename(filename)
    return f"employees/{employee_id}/profile-picture/{safe}"


def _validate_date_range(start_date: date, end_date: date | None) -> None:
    if end_date is not None and end_date < start_date:
        raise AppException("End date cannot be before start date", status_code=400)


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
