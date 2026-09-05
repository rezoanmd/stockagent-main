from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.db import create_user, get_user_by_username, verify_password, create_access_token, verify_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)

class UserAuth(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    username: str

@router.post("/register", response_model=TokenResponse)
def register(auth_data: UserAuth):
    username = auth_data.username.strip()
    
    # Check if user already exists
    existing_user = get_user_by_username(username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
        
    user_id = create_user(username, auth_data.password)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not register user"
        )
        
    # Generate token
    token = create_access_token({"user_id": user_id, "username": username})
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": username
    }

@router.post("/login", response_model=TokenResponse)
def login(auth_data: UserAuth):
    username = auth_data.username.strip()
    
    user = get_user_by_username(username)
    if not user or not verify_password(auth_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
        
    # Generate token
    token = create_access_token({"user_id": user["id"], "username": user["username"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": user["username"]
    }

def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[dict]:
    """
    Dependency that extracts the current user from JWT token.
    Returns None for guest users (no Authorization header).
    Raises 401 Unauthorized for invalid/expired tokens.
    """
    if not credentials:
        return None
        
    token = credentials.credentials
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return payload
