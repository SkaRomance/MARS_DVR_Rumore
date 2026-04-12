from pydantic import BaseModel


class AtecoMacroCategoryResponse(BaseModel):
    code: str
    name_it: str
    name_en: str
    description_it: str
    description_en: str
    typical_sources: list[str]
    typical_lex_range: list[int]


class AtecoCodeInfoResponse(BaseModel):
    ateco_code: str
    macro_category: AtecoMacroCategoryResponse | None
