import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import settings


def get_minio_client():
    return boto3.client(
        "s3",
        endpoint_url=f"http{'s' if settings.MINIO_SECURE else ''}://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def ensure_bucket():
    client = get_minio_client()
    try:
        client.head_bucket(Bucket=settings.MINIO_BUCKET)
    except ClientError:
        client.create_bucket(Bucket=settings.MINIO_BUCKET)


def upload_file(local_path: str, object_key: str) -> str:
    client = get_minio_client()
    ensure_bucket()
    client.upload_file(local_path, settings.MINIO_BUCKET, object_key)
    return object_key


def download_file(object_key: str, local_path: str):
    client = get_minio_client()
    client.download_file(settings.MINIO_BUCKET, object_key, local_path)


def delete_object(object_key: str):
    client = get_minio_client()
    client.delete_object(Bucket=settings.MINIO_BUCKET, Key=object_key)


def get_presigned_url(object_key: str, expires_in: int = 3600) -> str:
    client = get_minio_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.MINIO_BUCKET, "Key": object_key},
        ExpiresIn=expires_in,
    )
