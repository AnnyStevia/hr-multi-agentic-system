from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.identity.dependencies import get_auth_service, get_current_user, get_user_service
from app.modules.identity.models import User
from app.modules.identity.schemas import CandidateRegisterRequest, LoginRequest, TokenResponse, UserResponse
from app.modules.identity.service import AuthService, UserService
from app.shared.exceptions import AppException

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(
    credentials: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    user = auth_service.authenticate(credentials.email, credentials.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    access_token = auth_service.create_token_for_user(user)
    return TokenResponse(access_token=access_token)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_candidate(
    payload: CandidateRegisterRequest,
    user_service: UserService = Depends(get_user_service),
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    try:
        user = user_service.register_candidate(
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            password=payload.password,
        )
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return TokenResponse(access_token=auth_service.create_token_for_user(user))


@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    return auth_service.build_user_response_with_onboarding(current_user)
