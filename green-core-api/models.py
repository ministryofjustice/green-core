from typing import Optional
from datetime import datetime
from sqlmodel import Field, Session, SQLModel, Column, TIMESTAMP, text, create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import MetaData
import uuid

metadata = MetaData(schema="greencore")

class User(SQLModel, table=True):
    metadata = metadata
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(max_length=100, nullable=False, unique=True)
    global_role: str = Field(max_length=50, nullable=True)
    created_at: Optional[datetime] = Field(sa_column=Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    ))
    updated_at: Optional[datetime] = Field(sa_column=Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    ))


class UserPassword(SQLModel, table=True):
    metadata = metadata
    __tablename__ = "user_passwords"

    user_id: uuid.UUID = Field(foreign_key="users.id", nullable=False, primary_key=True)
    hashed_password: str = Field(max_length=255, nullable=False)


class Session(SQLModel, table=True):
    metadata = metadata
    __tablename__ = "sessions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", nullable=False)
    expires_at: Optional[datetime] = Field(sa_column=Column(TIMESTAMP(timezone=True), nullable=True))
    created_at: Optional[datetime] = Field(sa_column=Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    ))
    updated_at: Optional[datetime] = Field(sa_column=Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    ))

class DataStore(SQLModel, table=True):
    metadata = metadata
    __tablename__ = "data_stores"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=100, nullable=False)
    storage_type: str = Field(max_length=50, nullable=False)
    description: Optional[str] = Field(nullable=True)
    config: dict = Field(
        sa_column=Column(
            JSONB,
            nullable=True,
        )
    )
    created_at: Optional[datetime] = Field(sa_column=Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    ))
    updated_at: Optional[datetime] = Field(sa_column=Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    ))

class Org(SQLModel, table=True):
    metadata = metadata
    __tablename__ = "orgs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=100, nullable=False)
    created_at: Optional[datetime] = Field(sa_column=Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    ))
    updated_at: Optional[datetime] = Field(sa_column=Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    ))

class OrgMember(SQLModel, table=True):
    metadata = metadata
    __tablename__ = "org_members"

    user_id: uuid.UUID = Field(foreign_key="users.id", nullable=False, primary_key=True)
    org_id: uuid.UUID = Field(foreign_key="orgs.id", nullable=False, primary_key=True)
    role: str = Field(max_length=100, nullable=False)
    created_at: Optional[datetime] = Field(sa_column=Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    ))
    updated_at: Optional[datetime] = Field(sa_column=Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    ))

class OrgDataStoreAccess(SQLModel, table=True):
    metadata = metadata
    __tablename__ = "org_data_store_access"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    org_id: uuid.UUID = Field(foreign_key="orgs.id", nullable=False)
    data_store_id: uuid.UUID = Field(foreign_key="data_stores.id", nullable=False)
    allowed_path: str = Field(max_length=255, nullable=False)
    permissions: str = Field(max_length=50, nullable=False)
    created_at: Optional[datetime] = Field(sa_column=Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    ))
    updated_at: Optional[datetime] = Field(sa_column=Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    ))

class Dataset(SQLModel, table=True):
    metadata = metadata
    __tablename__ = "datasets"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    org_id: uuid.UUID = Field(foreign_key="orgs.id", nullable=False)
    data_store_id: uuid.UUID = Field(foreign_key="data_stores.id", nullable=False)
    name: str = Field(max_length=100, nullable=False)
    name_normalized: str = Field(max_length=100, nullable=False)
    description: Optional[str] = Field(nullable=True)
    spec: Optional[dict] = Field(
        sa_column=Column(
            JSONB,
            nullable=True,
        )
    )
    created_at: Optional[datetime] = Field(sa_column=Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    ))


class Upload(SQLModel, table=True):
    metadata = metadata
    __tablename__ = "uploads"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", nullable=False)
    dataset_id: uuid.UUID = Field(foreign_key="datasets.id", nullable=False)
    original_filename: str = Field(max_length=255, nullable=False)
    file_size: int = Field(nullable=False)
    status: str = Field(max_length=50, nullable=False)
    error_message: Optional[str] = Field(nullable=True)
    uploaded_at: Optional[datetime] = Field(sa_column=Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    ))
    validated_at: Optional[datetime] = Field(sa_column=Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    ))
    processed_at: Optional[datetime] = Field(sa_column=Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    ))
