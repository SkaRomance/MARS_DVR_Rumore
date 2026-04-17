from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.ateco import AtecoCodeInfoResponse, AtecoMacroCategoryResponse
from src.bootstrap.database import get_db
from src.domain.services.ateco_service import (
    get_all_macro_categories,
    get_macro_category,
    get_macro_category_for_ateco,
)
from src.infrastructure.auth.dependencies import get_current_user
from src.infrastructure.database.models.user import User
from src.infrastructure.middleware.rate_limiter import default_limiter

router = APIRouter(prefix="/ateco", tags=["ATECO"])


@router.get(
    "/macro-categories",
    response_model=list[AtecoMacroCategoryResponse],
)
async def list_macro_categories(
    current_user: User = Depends(get_current_user),
    _rate_limit=Depends(default_limiter),
):
    return get_all_macro_categories()


@router.get(
    "/macro-categories/{category_code}",
    response_model=AtecoMacroCategoryResponse,
)
async def get_single_macro_category(
    category_code: str,
    current_user: User = Depends(get_current_user),
    _rate_limit=Depends(default_limiter),
):
    result = get_macro_category(category_code)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Macro-category {category_code} not found",
        )
    return result


@router.get(
    "/code/{ateco_code}",
    response_model=AtecoCodeInfoResponse,
)
async def get_ateco_code_info(
    ateco_code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _rate_limit=Depends(default_limiter),
):
    macro = await get_macro_category_for_ateco(ateco_code, db_session=db)
    return AtecoCodeInfoResponse(ateco_code=ateco_code, macro_category=macro)
