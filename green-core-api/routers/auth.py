import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import select
from models import Org, OrgDataStoreAccess, OrgMember, DataStore, Session, User, UserPassword
from pydantic import BaseModel
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
    responses={404: {"description": "Not found"}},
)

ph = PasswordHasher()

class Login(BaseModel):
    email: str
    password: str

@router.post("/login")
async def create_user(login: Login, request: Request):
    session = request.state.db

    # Get user
    stmt = select(User).where(User.email == login.email)
    existing_user = session.exec(stmt).first()
    if not existing_user:
        raise HTTPException(status_code=400, detail="User does not exist")

    # Get password record
    stmt = select(UserPassword).where(UserPassword.user_id == existing_user.id)
    user_password = session.exec(stmt).first()
    if not user_password:
        raise HTTPException(status_code=400, detail="User does not exist")

    # Verify password
    try:
        ph.verify(user_password.hashed_password, login.password)
    except VerifyMismatchError:
        raise HTTPException(status_code=400, detail="Invalid password")

    # Create a new session for the user with a 1 day expiration
    now = datetime.datetime.now()
    user_session = Session(user_id=existing_user.id, expires_at=now + datetime.timedelta(days=1))
    session.add(user_session)
    session.commit()

    return {"sid": user_session.id}

