from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select
from models import Org, OrgDataStoreAccess, OrgMember, DataStore, User, UserPassword
from pydantic import BaseModel
from argon2 import PasswordHasher

router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={404: {"description": "Not found"}},
)

ph = PasswordHasher()

class UserCreate(BaseModel):
    email: str
    password: str
    global_role: str | None = None

# Admin (global_role) users can create new users
@router.post("")
async def create_user(user: UserCreate, request: Request):
    # Only allow admin users to create new users
    if request.state.user.global_role != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")

    # Check if the user already exists
    session = request.state.db
    stmt = select(User).where(User.email == user.email)
    existing_user = session.exec(stmt).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")

    # Create the new user
    new_user = User(
        email=user.email,
    )
    if user.global_role:
        new_user.global_role = user.global_role

    # Hash the password using Argon2 and store it in the database
    hashed_password = ph.hash(user.password)
    user_password = UserPassword(
        user_id=new_user.id,
        hashed_password=hashed_password
    )

    # Add the new user to the database
    session.add(new_user)
    session.flush()  # Flush to get the new user's ID
    session.add(user_password)
    session.commit()

    return new_user

