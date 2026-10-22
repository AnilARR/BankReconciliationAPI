"""Shared helpers for endpoints that accept transaction files."""

from fastapi import HTTPException, UploadFile, status

from app.config import get_settings
from app.schemas import DuplicateReference, RowErrorOut
from app.services.importer import FileFormatError, ParsedFile, parse_transactions

MAX_ERRORS_RETURNED = 200


async def read_and_parse(file: UploadFile) -> ParsedFile:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A file name is required")
    limit = get_settings().max_upload_bytes
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="File exceeds the upload limit")
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is empty")
    try:
        return parse_transactions(content, file.filename)
    except FileFormatError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


def error_list(parsed: ParsedFile) -> list[RowErrorOut]:
    return [RowErrorOut(**vars(e)) for e in parsed.errors[:MAX_ERRORS_RETURNED]]


def duplicate_list(duplicates: dict[str, list[int]]) -> list[DuplicateReference]:
    return [
        DuplicateReference(reference=ref, row_numbers=rows, occurrences=len(rows))
        for ref, rows in sorted(duplicates.items())
    ]
