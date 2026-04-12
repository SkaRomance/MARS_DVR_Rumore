from fastapi import APIRouter, HTTPException, status

from src.api.schemas.ateco import AtecoMacroCategoryResponse, AtecoCodeInfoResponse
from src.domain.services.ateco_service import (
    get_macro_category,
    get_all_macro_categories,
    get_macro_category_for_ateco,
)

router = APIRouter(prefix="/ateco", tags=["ATECO"])


@router.get(
    "/macro-categories",
    response_model=list[AtecoMacroCategoryResponse],
)
async def list_macro_categories():
    return get_all_macro_categories()


@router.get(
    "/macro-categories/{category_code}",
    response_model=AtecoMacroCategoryResponse,
)
async def get_single_macro_category(category_code: str):
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
async def get_ateco_code_info(ateco_code: str):
    macro = await get_macro_category_for_ateco(ateco_code)
    return AtecoCodeInfoResponse(ateco_code=ateco_code, macro_category=macro)
