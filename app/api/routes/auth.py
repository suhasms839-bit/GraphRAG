from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.models import User
from app.core.schemas import UserCreate, UserLogin, TokenResponse, UserResponse
from app.core.security import hash_password, verify_password, create_access_token, verify_token
from app.core.logging import logger

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/signup", response_model=TokenResponse)
async def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    """Create a new user account"""
    
    normalized_email = user_data.email.strip().lower()
    normalized_username = user_data.username.strip()

    # Check if user already exists
    existing_user = db.query(User).filter(
        (User.email == normalized_email) | (User.username == normalized_username)
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username already registered"
        )
    
    # Create new user
    hashed_password = hash_password(user_data.password)
    new_user = User(
        email=normalized_email,
        username=normalized_username,
        hashed_password=hashed_password,
        password_hash=hashed_password,
        full_name=user_data.full_name,
        role=user_data.role,
        department=user_data.department,
        organization=user_data.organization,
        is_active=True
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    logger.info(f"New user created: {new_user.email}")
    
    # Generate token
    access_token = create_access_token(data={"sub": str(new_user.id), "email": new_user.email})
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.from_orm(new_user)
    )

@router.post("/login", response_model=TokenResponse)
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    """Login user and return JWT token"""

    normalized_email = user_data.email.strip().lower()
    user = db.query(User).filter(User.email == normalized_email).first()
    stored_password_hash = user.hashed_password if user else None
    if user and not stored_password_hash:
        stored_password_hash = user.password_hash
    
    if not user or not stored_password_hash or not verify_password(user_data.password, stored_password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    logger.info(f"User logged in: {user.email}")
    
    # Generate token
    access_token = create_access_token(data={"sub": str(user.id), "email": user.email})
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.from_orm(user)
    )

@router.get("/me", response_model=UserResponse)
async def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)):
    """Get current user info from JWT token"""

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header"
        )

    token = parts[1]
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    
    user_id = int(payload.get("sub"))
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse.from_orm(user)
