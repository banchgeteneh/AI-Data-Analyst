from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.dataset import Dataset
from app.services.extractors import detect_file_type


ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".txt", ".docx", ".pdf"}
CHUNK_SIZE = 1024 * 1024


def _upload_directory() -> Path:
    upload_directory = Path(get_settings().upload_directory).resolve()
    upload_directory.mkdir(parents=True, exist_ok=True)
    return upload_directory


def _validate_extension(filename: str | None) -> str:
    if not filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A file is required")
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Supported formats are CSV, XLSX, TXT, DOCX, and PDF.",
        )
    return extension


async def store_upload(upload: UploadFile) -> tuple[str, str, int]:
    extension = _validate_extension(upload.filename)
    upload_directory = _upload_directory()
    stored_filename = f"{uuid4().hex}{extension}"
    destination = (upload_directory / stored_filename).resolve()
    if upload_directory not in destination.parents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid upload path")

    max_size = get_settings().max_dataset_size_mb * 1024 * 1024
    file_size = 0
    try:
        with destination.open("wb") as output:
            while chunk := await upload.read(CHUNK_SIZE):
                file_size += len(chunk)
                if file_size > max_size:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"File exceeds the {get_settings().max_dataset_size_mb} MB limit",
                    )
                output.write(chunk)
    except HTTPException:
        destination.unlink(missing_ok=True)
        raise
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()

    return stored_filename, str(destination), file_size


def remove_upload(file_path: str) -> None:
    upload_directory = _upload_directory()
    path = Path(file_path).resolve()
    if upload_directory not in path.parents:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid stored file path")
    path.unlink(missing_ok=True)


def create_dataset(
    db: Session,
    user_id: int,
    original_filename: str,
    file_type: str,
    stored_filename: str,
    file_path: str,
    file_size: int,
) -> Dataset:
    dataset = Dataset(
        user_id=user_id,
        original_filename=Path(original_filename).name,
        stored_filename=stored_filename,
        file_path=file_path,
        file_type=file_type,
        file_size=file_size,
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return dataset
