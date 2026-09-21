from datetime import date
from io import BytesIO

from openpyxl import Workbook
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.security import create_access_token, get_password_hash, verify_password
from app.modules.employees.models import DepartmentStatus, Employee, EmploymentStatus
from app.modules.employees.repository import DepartmentRepository, EmployeeRepository
from app.modules.employees.service import _normalize_phone
from app.modules.identity.models import Candidate, Permission, Role, RolePermission, User, UserRole
from app.modules.identity.schemas import UserListItem, UserResponse
from app.shared.exceptions import AppException


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def authenticate(self, email: str, password: str) -> User | None:
        user = (
            self.db.query(User)
            .options(
                joinedload(User.user_roles)
                .joinedload(UserRole.role)
                .joinedload(Role.role_permissions)
                .joinedload(RolePermission.permission)
            )
            .filter(User.email == email)
            .first()
        )
        if not user or not user.is_active:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    def create_token_for_user(self, user: User) -> str:
        return create_access_token({"sub": str(user.id), "email": user.email})

    def get_user_by_id(self, user_id: int) -> User | None:
        return (
            self.db.query(User)
            .options(
                joinedload(User.candidate_profile),
                joinedload(User.user_roles)
                .joinedload(UserRole.role)
                .joinedload(Role.role_permissions)
                .joinedload(RolePermission.permission)
            )
            .filter(User.id == user_id)
            .first()
        )

    @staticmethod
    def build_user_response(user: User, *, onboarding_status: str | None = None) -> UserResponse:
        roles = [ur.role for ur in user.user_roles]
        permission_names: set[str] = set()
        for role in roles:
            for rp in role.role_permissions:
                permission_names.add(rp.permission.name)

        return UserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            full_name=user.full_name,
            is_active=user.is_active,
            roles=roles,
            permissions=sorted(permission_names),
            phone=user.candidate_profile.phone if user.candidate_profile else None,
            onboarding_status=onboarding_status,
        )

    def build_user_response_with_onboarding(self, user: User) -> UserResponse:
        from app.modules.employees.repository import EmployeeRepository
        from app.modules.onboarding.repository import OnboardingRepository
        from app.modules.onboarding.service import OnboardingService

        status = OnboardingService(
            OnboardingRepository(self.db),
            EmployeeRepository(self.db),
        ).get_onboarding_status_for_user(user.id)
        return self.build_user_response(
            user,
            onboarding_status=status.value if status is not None else None,
        )


class UserService:
    HR_ROLE_NAME = "hr"
    CANDIDATE_ROLE_NAME = "candidate"

    def __init__(self, db: Session):
        self.db = db

    def create_hr_account(
        self,
        first_name: str,
        last_name: str,
        email: str,
        password: str,
        *,
        phone: str,
        department_id: int,
        position: str,
        hire_date: date,
    ) -> User:
        existing = self.db.query(User).filter(User.email == email).first()
        if existing is not None:
            raise AppException("A user with this email already exists", status_code=409)

        if EmployeeRepository(self.db).get_by_email(email) is not None:
            raise AppException("An employee with this email already exists", status_code=409)

        department = DepartmentRepository(self.db).get_by_id(department_id)
        if department is None:
            raise AppException("Department not found", status_code=400)
        if department.status != DepartmentStatus.ACTIVE:
            raise AppException("Department is not active", status_code=400)

        hr_role = self.db.query(Role).filter(Role.name == self.HR_ROLE_NAME).first()
        if hr_role is None:
            raise AppException("HR role is not configured", status_code=500)

        user = User(
            email=email,
            hashed_password=get_password_hash(password),
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            is_active=True,
        )
        self.db.add(user)
        self.db.flush()
        self.db.add(UserRole(user_id=user.id, role_id=hr_role.id))

        from app.modules.employees.repository import PositionRepository
        from app.modules.employees.service import DepartmentService, PositionService

        position_title = position.strip()
        position_service = PositionService(
            PositionRepository(self.db),
            DepartmentService(DepartmentRepository(self.db)),
        )
        org_position = position_service.get_or_create_by_title(
            position_title, department_id=department.id, commit=False
        )

        employee = Employee(
            employee_number="PENDING",
            first_name=user.first_name,
            last_name=user.last_name,
            email=email,
            phone=_normalize_phone(phone),
            department_id=department.id,
            position=position_title,
            position_id=org_position.id,
            hire_date=hire_date,
            employment_status=EmploymentStatus.ACTIVE,
            user_id=user.id,
        )
        EmployeeRepository(self.db).add(employee)

        created = AuthService(self.db).get_user_by_id(user.id)
        if created is None:
            raise AppException("Failed to load created HR account", status_code=500)
        return created

    def register_candidate(
        self,
        first_name: str,
        last_name: str,
        email: str,
        password: str,
    ) -> User:
        existing = self.db.query(User).filter(User.email == email).first()
        if existing is not None:
            raise AppException("A user with this email already exists", status_code=409)

        candidate_role = self.db.query(Role).filter(Role.name == self.CANDIDATE_ROLE_NAME).first()
        if candidate_role is None:
            raise AppException("Candidate role is not configured", status_code=500)

        user = User(
            email=email,
            hashed_password=get_password_hash(password),
            first_name=first_name,
            last_name=last_name,
            is_active=True,
        )
        self.db.add(user)
        self.db.flush()
        self.db.add(UserRole(user_id=user.id, role_id=candidate_role.id))
        self.db.add(Candidate(user_id=user.id))
        self.db.commit()

        created = AuthService(self.db).get_user_by_id(user.id)
        if created is None:
            raise AppException("Failed to load created candidate account", status_code=500)
        return created

    def list_accounts(self) -> list[User]:
        return (
            self.db.query(User)
            .options(selectinload(User.user_roles).joinedload(UserRole.role))
            .order_by(User.id.asc())
            .all()
        )

    def export_accounts_excel(self) -> bytes:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Accounts"
        sheet.append(
            ["ID", "First name", "Last name", "Email", "Roles", "Status", "Created at"]
        )

        for user in self.list_accounts():
            roles = ", ".join(user_role.role.name for user_role in user.user_roles)
            created_at = user.created_at.strftime("%Y-%m-%d %H:%M") if user.created_at else ""
            sheet.append(
                [
                    user.id,
                    user.first_name,
                    user.last_name,
                    user.email,
                    roles,
                    "Active" if user.is_active else "Inactive",
                    created_at,
                ]
            )

        buffer = BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()

    @staticmethod
    def build_list_item(user: User) -> UserListItem:
        return UserListItem(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            full_name=user.full_name,
            is_active=user.is_active,
            roles=[user_role.role for user_role in user.user_roles],
            created_at=user.created_at,
        )


class SeedService:
    """Initial data seeding for roles, permissions, and admin user."""

    ROLES = [
        ("admin", "System administrator with full access"),
        ("hr", "Human Resources staff"),
        ("manager", "Department manager"),
        ("employee", "Regular employee"),
        ("candidate", "External job applicant"),
    ]

    PERMISSIONS = [
        ("users:read", "Read user information", "users", "read"),
        ("users:write", "Manage users", "users", "write"),
        ("employees:read", "Read employee records", "employees", "read"),
        ("employees:write", "Manage employee records", "employees", "write"),
        ("recruitment:read", "Read recruitment data", "recruitment", "read"),
        ("recruitment:write", "Manage recruitment", "recruitment", "write"),
        ("leaves:read", "Read leave data", "leaves", "read"),
        ("leaves:write", "Manage leave requests", "leaves", "write"),
        ("training:read", "Read training data", "training", "read"),
        ("training:write", "Manage training", "training", "write"),
        ("documents:read", "Read documents", "documents", "read"),
        ("documents:write", "Manage documents", "documents", "write"),
        ("onboarding:read", "Read onboarding data", "onboarding", "read"),
        ("onboarding:write", "Manage onboarding", "onboarding", "write"),
    ]

    ROLE_PERMISSIONS = {
        "admin": [p[0] for p in PERMISSIONS],
        "hr": [
            "users:read",
            "employees:read",
            "employees:write",
            "recruitment:read",
            "recruitment:write",
            "leaves:read",
            "leaves:write",
            "training:read",
            "training:write",
            "documents:read",
            "documents:write",
            "onboarding:read",
            "onboarding:write",
        ],
        "manager": [
            "employees:read",
            "recruitment:read",
            "leaves:read",
            "leaves:write",
            "training:read",
            "documents:read",
            "onboarding:read",
        ],
        "employee": [
            "employees:read",
            "leaves:read",
            "leaves:write",
            "training:read",
            "documents:read",
        ],
    }

    def __init__(self, db: Session):
        self.db = db

    def seed(self, admin_email: str, admin_password: str) -> None:
        if self.db.query(Role).first():
            self._ensure_candidate_role()
            return

        permissions: dict[str, Permission] = {}
        for name, desc, resource, action in self.PERMISSIONS:
            perm = Permission(
                name=name, description=desc, resource=resource, action=action
            )
            self.db.add(perm)
            permissions[name] = perm
        self.db.flush()

        roles: dict[str, Role] = {}
        for name, desc in self.ROLES:
            role = Role(name=name, description=desc)
            self.db.add(role)
            roles[name] = role
        self.db.flush()

        for role_name, perm_names in self.ROLE_PERMISSIONS.items():
            for perm_name in perm_names:
                self.db.add(
                    RolePermission(role_id=roles[role_name].id, permission_id=permissions[perm_name].id)
                )

        admin_user = User(
            email=admin_email,
            hashed_password=get_password_hash(admin_password),
            first_name="System",
            last_name="Admin",
            is_active=True,
        )
        self.db.add(admin_user)
        self.db.flush()

        self.db.add(UserRole(user_id=admin_user.id, role_id=roles["admin"].id))
        self.db.commit()

    def _ensure_candidate_role(self) -> None:
        existing = self.db.query(Role).filter(Role.name == "candidate").first()
        if existing is not None:
            return
        description = next(desc for name, desc in self.ROLES if name == "candidate")
        self.db.add(Role(name="candidate", description=description))
        self.db.commit()
