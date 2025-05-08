from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select
from models import DataStore


router = APIRouter(
    prefix="/stores",
    tags=["data stores"],
    responses={404: {"description": "Not found"}},
)


@router.post("")
async def create_data_store(request: Request):
    data = await request.json()
    print ("Req: ", request.state.user)
    print("Received data:", data)
    # Only allow admin users to create data stores
    if request.state.user.global_role != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")

    # unpack the data
    name = data.get("name")
    storage_type = data.get("storage_type")
    description = data.get("description")
    config = data.get("config")

    # TODO: Validate the data
    if not name or not storage_type:
        raise HTTPException(status_code=400, detail="Missing required fields")

    # Create model instance
    data_store = DataStore(
        name=name,
        storage_type=storage_type,
        description=description,
        config=config,
    )

    # Create the data store in the appropriate storage system
    if storage_type == "s3tables":
        # TODO: Add logic to handle cross account s3 table buckets
        # If config has bucket name, use it, else use the datastore id
        bucket_name = config.get("bucket_name", str(data_store.id))
        res = request.state.s3tables.create_table_bucket(name=bucket_name)
        arn = res["arn"]
        # Add the ARN to the data store config
        data_store.config["arn"] = arn

    # Insert data store record in the app database
    session = request.state.db
    session.add(data_store)
    session.commit()

    return {"message": "Data store created"}


# This endpoint is used to import existing datastores.
# e.g. to be able to use an existing s3 table bucket in this app
@router.post("/import")
async def import_data_store(request: Request):
    # Only allow admin users to list data stores
    if request.state.user.global_role != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")

    # unpack the data
    data = await request.json()
    name = data.get("name")
    storage_type = data.get("storage_type")
    description = data.get("description")
    # config needs to provide the bucket name and region
    config = data.get("config")

    s3_table_arn = f"arn:aws:s3tables:{config['region']}:{config['account_id']}:bucket/{config['bucket_name']}"

    # Check if the table bucket exists
    try:
        res = request.state.s3tables.get_table_bucket(tableBucketARN=s3_table_arn)
        print("Res: ", res)
    except Exception as e:
        print("Error: ", e)
        raise HTTPException(status_code=400, detail="Table bucket is not accessible")

    # Table bucket exists, add arn to the config
    config["arn"] = s3_table_arn
    # Add uploader id to the config
    config["uploader_id"] = str(request.state.user.id)

    # Create model instance
    data_store = DataStore(
        name=name,
        storage_type=storage_type,
        description=description,
        config=config,
    )

    session = request.state.db
    session.add(data_store)
    session.commit()


    return {"id": str(data_store.id)}

@router.get("")
async def read_items(request: Request):
    # Only allow admin users to list data stores
    if request.state.user.global_role != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")
    # Get the data stores from the database
    session = request.state.db
    stmt = select(DataStore)
    data_stores = session.exec(stmt).all()
    # Return the data stores
    return data_stores
