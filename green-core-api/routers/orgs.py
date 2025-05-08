from enum import Enum
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select
from models import Org, OrgDataStoreAccess, OrgMember, DataStore
from pydantic import BaseModel
import boto3


router = APIRouter(
    prefix="/orgs",
    tags=["organisations"],
    responses={404: {"description": "Not found"}},
)

class OrgCreate(BaseModel):
    orgName: str
    dataStoreId: str

@router.post("")
async def create_org(request: Request):
    data = await request.json()
    # Only allow admin users to create data stores
    if request.state.user.global_role != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")

    # unpack the data
    org_name = data.get("orgName")
    data_store_id = data.get("dataStoreId")

    # Get the data store from the database
    session = request.state.db
    stmt = select(DataStore).where(DataStore.id == data_store_id)
    data_store = session.exec(stmt).first()
    if not data_store:
        raise HTTPException(status_code=400, detail="Data store not found")

    # Org model
    org = Org(
        name=org_name,
        data_store_id=data_store_id
    )

    org_member = OrgMember(
        user_id=request.state.user.id,
        org_id=org.id,
        role="admin"
    )

    org_data_store_access = OrgDataStoreAccess(
        org_id=org.id,
        data_store_id=data_store_id,
        allowed_path="/",
        permissions="read-write"
    )

    if data_store.storage_type == "s3tables":
        request.state.s3tables.create_namespace(
           tableBucketARN=str(data_store.config["arn"]),
           namespace=[str(org.id).replace("-", "_")], # Namespace regex [0-9a-z_]*
        )

    # Create the data store in the appropriate storage system
    session = request.state.db
    session.add(org)
    session.add(org_member)
    session.add(org_data_store_access)
    session.commit()
    return {"message": "Org created"}

@router.get("")
async def read_orgs(request: Request):
    # TODO: Allow org admins to list their orgs
    # Only allow global admin users to list orgs
    if request.state.user.global_role != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")
    # Get the data stores from the database
    session = request.state.db
    stmt = select(Org)
    orgs = session.exec(stmt).all()
    # Return the data stores
    return orgs

@router.get("/{org_id}")
async def read_org(request: Request, org_id: str):
    # TODO: Allow org admins to list their orgs
    # Only allow global admin users to get their orgs
    if request.state.user.global_role != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")
    # Get the data stores from the database
    session = request.state.db
    stmt = select(Org).where(Org.id == org_id)
    org = session.exec(stmt).first()
    if not org:
        raise HTTPException(status_code=404, detail="Org not found")
    # Return the data stores
    return org

class OrgRole(str, Enum):
    admin = "admin"
    write = "write"
    read  = "read"

class OrgMemberCreate(BaseModel):
    user_id: str
    role: OrgRole

@router.post("/{org_id}/members")
async def create_org_member(request: Request, org_id: str, member: OrgMemberCreate):
    #if request.state.user.global_role != "admin":
    #    raise HTTPException(status_code=403, detail="Permission denied")
    session = request.state.db

    # Get Org
    stmt = select(Org).where(Org.id == org_id)
    org = session.exec(stmt).first()
    if not org:
        raise HTTPException(status_code=404, detail="Org not found")

    # Check if the requesting user is an admin member of the org
    stmt = select(OrgMember).where(OrgMember.org_id == org_id, OrgMember.user_id == request.state.user.id)
    org_member = session.exec(stmt).first()
    if not org_member:
        raise HTTPException(status_code=404, detail="Org not found")
    if org_member.role != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")

    # Create the org member
    org_member = OrgMember(
        user_id=member.user_id,
        org_id=org.id,
        role=member.role
    )

    # Add the org member to the database
    session.add(org_member)
    session.commit()

    return {"message": "Org member created"}
