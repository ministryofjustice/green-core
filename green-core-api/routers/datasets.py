from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select
from models import Org, OrgDataStoreAccess, OrgMember, DataStore, Dataset
from jsonschema import Draft7Validator, exceptions
from pyiceberg.catalog import load_catalog


# TODO: Centralise?
def json_schema_to_iceberg_metadata(spec):
    """
    Convert a JSON Schema (as a dict) into the 'metadata' block
    that AWS SDK's create_table expects for ICEBERG format.
    """
    # simple type‐mapping from JSON Schema to Iceberg
    TYPE_MAP = {
        "string":    "string",
        "integer":   "int",
        "number":    "double",
        "boolean":   "boolean",
        # you could extend this for object/array if needed:
        # "object":    "struct<…>",
        # "array":     "list<…>",
    }

    # which properties are required?
    required_fields = set(spec.get("required", []))

    fields = []
    for prop_name, prop_schema in spec.get("properties", {}).items():
        json_type = prop_schema.get("type")
        iceberg_type = TYPE_MAP.get(json_type)
        if iceberg_type is None:
            raise ValueError(f"Unsupported JSON Schema type: {json_type!r}")

        fields.append({
            "name":     prop_name,
            "type":     iceberg_type,
            "required": (prop_name in required_fields)
        })

    return {
        "iceberg": {
            "schema": {
                "fields": fields
            }
        }
    }

# function to lowercase and normalize the org name
def normalize(name: str) -> str:
    return name.lower().replace(" ", "_").replace("-", "_")

router = APIRouter(
    prefix="/orgs/{org_id}/datasets",
    tags=["datasets"],
    responses={404: {"description": "Not found"}},
)

@router.post("")
async def create_dataset(org_id: str, request: Request):
    data = await request.json()
    # name can only contain alphanumeric characters, underscores, and hyphens and spaces
    if not data.get("name") or not data["name"].isalnum():
        raise HTTPException(status_code=400, detail="Invalid name format")

    # Check that the requesting user is a member of the org
    session = request.state.db
    stmt = select(OrgMember).where(OrgMember.org_id == org_id, OrgMember.user_id == request.state.user.id)
    org_member = session.exec(stmt).first()

    # Only allow org admins to create datasets
    if not org_member or org_member.role != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")

    # Check that the data store exists
    stmt = select(DataStore).where(DataStore.id == data["dataStoreId"])
    data_store = session.exec(stmt).first()
    if not data_store:
        raise HTTPException(status_code=400, detail="Data store not found")

    # Check that the org has access to the data store
    stmt = select(OrgDataStoreAccess).where(
        OrgDataStoreAccess.org_id == org_id,
        OrgDataStoreAccess.data_store_id == data["dataStoreId"]
    )
    org_data_store_access = session.exec(stmt).first()
    if not org_data_store_access or org_data_store_access.permissions != "read-write":
        raise HTTPException(status_code=403, detail="Permission denied")

    # TODO: Validate the request data

    json_schema = data.get("spec")
    # Validate the JSON Schema
    try:
        Draft7Validator.check_schema(json_schema)
    except exceptions.SchemaError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON schema: {e.message}")

    # Check if the dataset already exists
    stmt = select(Dataset).where(
        Dataset.org_id == org_id,
        Dataset.name_normalized == normalize(data["name"])
    )
    existing_dataset = session.exec(stmt).first()
    if existing_dataset:
        raise HTTPException(status_code=400, detail="Dataset already exists")

    # Create the dataset
    dataset = Dataset(
        org_id=org_id,
        data_store_id=data["dataStoreId"],
        name=data["name"],
        name_normalized=normalize(data["name"]),
        description=data.get("description"),
        spec=json_schema
    )
    # Create the dataset in the appropriate storage system
    if data_store.storage_type == "s3tables":
        iceberg_metadata = json_schema_to_iceberg_metadata(json_schema)
        response = request.state.s3tables.create_table(
            tableBucketARN=str(data_store.config["arn"]),
            namespace=org_id.replace("-", "_"),
            name=str(str(dataset.id).replace("-", "_")),
            format='ICEBERG',
            metadata=iceberg_metadata,
            encryptionConfiguration={
                'sseAlgorithm': 'AES256'
            }
        )
        print("S3Tables response:", response)

    session.add(dataset)
    session.commit()
    return {"message": "Dataset created"}


@router.get("")
async def get_datasets(org_id: str, request: Request):
    # Check that the requesting user is a member of the org
    session = request.state.db
    stmt = select(OrgMember).where(OrgMember.org_id == org_id, OrgMember.user_id == request.state.user.id)
    org_member = session.exec(stmt).first()

    if not org_member:
        raise HTTPException(status_code=403, detail="Permission denied")

    # Get the datasets from the database
    stmt = select(Dataset).where(Dataset.org_id == org_id)
    datasets = session.exec(stmt).all()

    return datasets


@router.get("/{dataset_id}/data")
async def get_dataset_data(org_id: str, dataset_id: str, request: Request):
    session = request.state.db
    # Check that the requesting user is a member of the org
    stmt = select(OrgMember).where(OrgMember.org_id == org_id, OrgMember.user_id == request.state.user.id)
    org_member = session.exec(stmt).first()
    if not org_member:
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
    if not data_store:
        raise HTTPException(status_code=400, detail="Data store not found")

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

        # 3. Scan the table and convert to Arrow
        data = iceberg_table.scan().to_arrow()
        # return data as JSON
        return data.to_pandas().to_dict(orient="records")


    return dataset
