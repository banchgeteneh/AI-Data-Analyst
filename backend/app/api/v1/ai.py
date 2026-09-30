from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.dataset import Dataset
from app.models.user import User
from app.schemas.ai import DatasetChatRequest, DatasetChatResponse, DatasetReportResponse
from app.services.dataset_analysis import (
    DatasetAnalysisError,
    DatasetFileNotFoundError,
    analyze_dataset,
)
from app.services.ai import (
    AIConfigurationError,
    AIProviderError,
    AIRequestTimeoutError,
    AIRateLimitError,
    AIUnavailableError,
    build_dataset_context,
    generate_dataset_answer,
    generate_dataset_report,
    get_conversational_reply,
)


router = APIRouter(prefix="/datasets", tags=["AI assistant"])


@router.post("/{dataset_id}/ai/chat", response_model=DatasetChatResponse)
def chat_about_dataset(
    dataset_id: int,
    request: DatasetChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DatasetChatResponse:
    dataset = db.scalar(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
    )
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    conversational_reply = get_conversational_reply(request.message)
    if conversational_reply is not None:
        return DatasetChatResponse(answer=conversational_reply, dataset_id=dataset_id)

    try:
        analysis = analyze_dataset(dataset)
    except DatasetFileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except DatasetAnalysisError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error

    context = build_dataset_context(analysis, dataset, request.exploration_context)
    history = [turn.model_dump() for turn in request.history]
    try:
        answer = generate_dataset_answer(context, request.message, history)
    except AIConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    except AIRateLimitError as error:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(error)) from error
    except AIRequestTimeoutError as error:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(error)) from error
    except AIUnavailableError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    except AIProviderError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error

    return DatasetChatResponse(answer=answer, dataset_id=dataset_id)


@router.post("/{dataset_id}/ai/report", response_model=DatasetReportResponse)
def generate_report_for_dataset(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DatasetReportResponse:
    dataset = db.scalar(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
    )
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    try:
        analysis = analyze_dataset(dataset)
    except DatasetFileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset file is not available") from error
    except DatasetAnalysisError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The dataset could not be analyzed.",
        ) from error

    dataset_name = dataset.original_filename.replace("\\", "/").rsplit("/", 1)[-1] or "Dataset"
    analysis["dataset"]["filename"] = dataset_name
    context = build_dataset_context(analysis)
    try:
        report = generate_dataset_report(context)
    except AIConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is not configured. Please contact the administrator.",
        ) from error
    except AIRateLimitError as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="AI requests are temporarily limited. Please wait a moment and try again.",
        ) from error
    except AIRequestTimeoutError as error:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="The AI request took too long to complete. Please try again.",
        ) from error
    except AIUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The AI service is temporarily unavailable. Please try again shortly.",
        ) from error
    except AIProviderError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI service returned an unexpected response. Please try again.",
        ) from error

    dataset_info = analysis["dataset"]
    return DatasetReportResponse(
        **report.model_dump(),
        dataset_id=dataset.id,
        dataset_name=dataset_name,
        row_count=dataset_info["rows"],
        column_count=dataset_info["columns"],
        generated_at=datetime.now(timezone.utc),
    )