from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.dataset import Dataset
from app.models.user import User
from app.schemas.analysis import AutomaticInsight, DatasetAnalysisResponse
from app.schemas.dataset import DatasetResponse
from app.schemas.exploration import DatasetExplorationRequest, DatasetExplorationResponse
from app.services.dataset_analysis import (
    DatasetAnalysisError,
    DatasetFileNotFoundError,
    analyze_dataset,
)
from app.services.datasets import create_dataset, remove_upload, store_upload
from app.services.exploration import build_exploration_capabilities
from app.services.exploration_execution import execute_exploration


router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.post("/upload", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dataset:
    stored_filename, file_path, file_size = await store_upload(file)
    try:
        return create_dataset(
            db=db,
            user_id=current_user.id,
            original_filename=file.filename or Path(stored_filename).name,
            file_type=Path(stored_filename).suffix,
            stored_filename=stored_filename,
            file_path=file_path,
            file_size=file_size,
        )
    except Exception:
        remove_upload(file_path)
        raise


@router.get("", response_model=list[DatasetResponse])
def list_datasets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Dataset]:
    return list(
        db.scalars(
            select(Dataset)
            .where(Dataset.user_id == current_user.id)
            .order_by(Dataset.created_at.desc(), Dataset.id.desc())
        )
    )


@router.get("/{dataset_id}/analysis", response_model=DatasetAnalysisResponse)
def analyze_dataset_route(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DatasetAnalysisResponse:
    dataset = db.scalar(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
    )
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    try:
        return analyze_dataset(dataset)
    except DatasetFileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except DatasetAnalysisError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error


@router.get("/{dataset_id}/insights", response_model=list[AutomaticInsight])
def get_dataset_insights(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    dataset = db.scalar(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
    )
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    try:
        analysis = analyze_dataset(dataset)
    except DatasetFileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except DatasetAnalysisError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error

    return analysis["dashboard"].get("automatic_insights", [])


@router.get("/{dataset_id}/explore/capabilities", response_model=dict[str, Any])
def get_dataset_exploration_capabilities(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    dataset = db.scalar(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
    )
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    try:
        analysis = analyze_dataset(dataset)
    except DatasetFileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except DatasetAnalysisError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error

    return build_exploration_capabilities(analysis).model_dump(mode="json")


@router.post("/{dataset_id}/explore", response_model=DatasetExplorationResponse)
def explore_dataset_route(
    dataset_id: int,
    request: DatasetExplorationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    dataset = db.scalar(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
    )
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    try:
        analysis = analyze_dataset(dataset)
        result = execute_exploration(dataset, request, analysis)
    except DatasetFileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except DatasetAnalysisError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error

    return DatasetExplorationResponse.model_validate(result)


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    dataset = db.scalar(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
    )
    if dataset is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    remove_upload(dataset.file_path)
    db.delete(dataset)
    db.commit()
