import logging
import uuid
import asyncio
from typing import Annotated, Union
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session as SQLSession, select
from fastapi.responses import JSONResponse
import boto3


from alembic.config import Config
from alembic import command

from models import User, Session
from routers import auth, data_stores, orgs, datasets, uploads, users


logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.DEBUG)


DATABASE_URL = "postgresql+psycopg2://postgres:password@localhost:5432/greencore"
logger.info("Connecting to database")
engine = create_engine(DATABASE_URL, echo=False)

#s3tables = boto3.client(
#    "s3tables",
#    endpoint_url="http://localhost:5000",
#    region_name="us-east-1",
#    aws_access_key_id="test",
#    aws_secret_access_key="test",
#)

s3tables = boto3.client(
    "s3tables",
    region_name="eu-west-1",
)


def get_session():
    with SQLSession(engine) as session:
        yield session


@asynccontextmanager
async def get_session_ctx():
    with SQLSession(engine) as session:
        yield session

SessionDep = Annotated[SQLSession, Depends(get_session)]

def run_migrations_sync() -> None:
    """Sync‑only migration runner: injects your Engine’s Connection into Alembic."""
    engine = create_engine(DATABASE_URL)
    with engine.begin() as connection:
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", str(engine.url))
        cfg.attributes['connection'] = engine
        command.upgrade(cfg, "head")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Lifespan started")

    # 1) Run migrations and create initial user
    engine = create_engine(DATABASE_URL, echo=False)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    try:
        logger.info("Running migrations…")
        run_migrations_sync()
        logger.info("Migrations complete.")

        # Now check for the initial admin user
        initial_email = "serj.hassan@justice.gov.uk"
        with SessionLocal() as session:
            stmt = select(User).where(User.email == initial_email)
            existing_user = session.execute(stmt).scalar_one_or_none()

            if existing_user:
                logger.info(f"Initial user {initial_email!r} already exists, skipping creation.")
                user_session = Session(user_id=existing_user.id)
                session.add(user_session)
                session.commit()
            else:
                logger.info(f"Creating initial user {initial_email!r}…")
                initial_user = User(email=initial_email, global_role="admin")
                user_session = Session(user_id=initial_user.id)
                session.add(initial_user)
                session.flush()
                session.add(user_session)
                session.commit()
                logger.info("Initial user created successfully.")

    except SQLAlchemyError as db_err:
        logger.error("Database error during setup:", exc_info=db_err)
        raise
    except Exception as err:
        logger.error("Unexpected error during setup:", exc_info=err)
        raise

    # 2) now start serving
    yield

#app = FastAPI()
app = FastAPI(lifespan=lifespan)
app.include_router(auth.router)
app.include_router(data_stores.router)
app.include_router(orgs.router)
app.include_router(datasets.router)
app.include_router(uploads.router)
app.include_router(users.router)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    async with get_session_ctx() as db:
        request.state.db = db
        request.state.s3tables = s3tables
        # Exclude the /auth/login endpoint from authentication
        if request.url.path.startswith("/auth/login"):
            return await call_next(request)


        auth = request.headers.get("Authorization", "")
        if not auth.lower().startswith("bearer "):
            return JSONResponse(content={"message": "Invalid token"}, status_code=401)
        token = auth.split(" ",1)[1].strip()
        # Validate that the token is a valid UUID
        try:
            token = uuid.UUID(token)
        except ValueError:
            return JSONResponse(content={"message": "Invalid token"}, status_code=201)
            #return JSONResponse(401, {"detail":"Invalid token"})

        stmt = select(Session).where(Session.id==token)
        session_record = db.exec(stmt).first()
        if not session_record:
            return JSONResponse(content={"message": "Invalid token"}, status_code=200)

        # Get user from session id
        stmt = select(User).where(User.id==session_record.user_id)
        user_record = db.exec(stmt).first()
        if not user_record:
            return JSONResponse(content={"message": "Unauthorized"}, status_code=401)
        # Check if the session is expired
        if session_record.expires_at and session_record.expires_at < datetime.datetime.now():
            return JSONResponse(content={"message": "Session expired"}, status_code=401)
        # Set user in request state
        request.state.user = user_record
        return await call_next(request)

@app.get("/health")
def read_root():
    return {"message": "healthy"}

@app.get("/profile")
def read_profile(session: SessionDep, request: Request):
    return request.state.user
