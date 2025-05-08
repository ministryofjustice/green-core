from typing import Annotated
import json
import pyarrow as pa
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from sqlmodel import Session, select
from models import Org, OrgDataStoreAccess, OrgMember, DataStore, Dataset
from jsonschema import Draft7Validator, exceptions
from pyiceberg.catalog import load_catalog

def json_schema_to_arrow_schema(spec: dict) -> pa.Schema:
    """
    Convert a JSON Schema into a PyArrow Schema, using
    the JSON Schema `type` → Arrow type mapping.
    """
    # Map JSON Schema types to PyArrow DataTypes
    TYPE_MAP = {
        "string":  pa.string(),
        "integer": pa.int32(),   # TODO: int64 maps to long in iceberg. look into this
        "number":  pa.float64(),
        "boolean": pa.bool_(),
    }

    required = set(spec.get("required", []))
    fields = []

    for name, subschema in spec.get("properties", {}).items():
        jtype = subschema.get("type")
        arrow_type = TYPE_MAP.get(jtype)
        if arrow_type is None:
            raise ValueError(f"Unsupported JSON Schema type: {jtype!r}")

        # nullable = False if in "required", else True
        nullable = name not in required
        fields.append(pa.field(name, arrow_type, nullable=nullable))

    return pa.schema(fields)

router = APIRouter(
    prefix="/orgs/{org_id}/datasets/{dataset_id}/upload",
    tags=["uploads"],
    responses={404: {"description": "Not found"}},
)

@router.post("")
async def upload_file(
    org_id: str,
    dataset_id: str,
    request: Request,
    file: UploadFile = File(...)):
    # Check that the requesting user is a member of the org
    session = request.state.db
    stmt = select(OrgMember).where(OrgMember.org_id == org_id, OrgMember.user_id == request.state.user.id)
    org_member = session.exec(stmt).first()

    # TODO: Check permission checks
    if not org_member or (org_member.role != "admin" and org_member.role != "write"):
        raise HTTPException(status_code=403, detail="Permission denied")

    # Check if the dataset exists
    stmt = select(Dataset).where(
        Dataset.org_id == org_id,
        Dataset.id == dataset_id
    )
    dataset = session.exec(stmt).first()
    if not dataset:
        raise HTTPException(status_code=400, detail="Dataset not found")

    # Get data store
    stmt = select(DataStore).where(DataStore.id == dataset.data_store_id)
    data_store = session.exec(stmt).first()

    # Validate uploaded data against the dataset spec 
    raw = await file.read()
    validator = Draft7Validator(dataset.spec)
    instance = json.loads(raw.decode("utf-8"))
    errors = sorted(validator.iter_errors(instance), key=lambda e: e.path)

    if errors:
        # Build a combined message
        messages = []
        for err in errors:
            # e.path is a deque showing where in the document the error occurred
            location = ".".join(str(p) for p in err.path) or "<root>"
            messages.append(f"{location}: {err.message}")
        detail = "JSON does not conform to schema:\n" + "\n".join(messages)
        raise HTTPException(status_code=400, detail=detail)


    schema = json_schema_to_arrow_schema(dataset.spec)
    # Load the data into a pyarrow table
    #df = pd.DataFrame([instance])
    #arrow_table = pa.Table.from_pandas(df)
    arrow_table = pa.Table.from_pylist([instance], schema=schema)

    # Authorize into the S3 tables Iceberg REST API (Need to do SIGV4 signing)
    # Load table into the iceberg table using the ICEBERG REST API

    # Replace these with your actual AWS Region, Account ID, and S3 Tables bucket name

    if data_store.storage_type == "s3tables":
        # 1. Load the S3 Tables catalog
        region      = data_store.config["region"]
        account_id  = data_store.config["account_id"]
        bucket_name = data_store.config["bucket_name"]

        rest_catalog = load_catalog(
          "s3tables_catalog",
          **{
            "type": "rest",
            "warehouse":f"arn:aws:s3tables:{region}:{account_id}:bucket/{bucket_name}",
            "uri": f"https://s3tables.{region}.amazonaws.com/iceberg",
            "rest.sigv4-enabled": "true",
            "rest.signing-name": "s3tables",
            "rest.signing-region": region
          }
        )

        # 2. Load the Iceberg table
        namespace = str(org_id).replace("-", "_")
        iceberg_table_name = str(dataset.id).replace("-", "_")
        iceberg_table = rest_catalog.load_table(f"{namespace}.{iceberg_table_name}")

        # 3. Append the data to the Iceberg table
        iceberg_table.append(arrow_table)

    return {"message": "File uploaded successfully"}

