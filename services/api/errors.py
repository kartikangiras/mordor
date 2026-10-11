"""Error envelope per DESIGN.md §8: {"error": {"code": ..., "message": ...}}."""
from __future__ import annotations

from fastapi import HTTPException


class ApiError(HTTPException):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(status_code=status, detail={"code": code, "message": message})
        self.code = code
        self.message = message
