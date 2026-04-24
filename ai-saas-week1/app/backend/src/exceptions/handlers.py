"""全局异常处理器"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse
from schemas.common import ErrorResponse


def register_exception_handlers(app: FastAPI):
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(status_code=exc.status_code, content=ErrorResponse(code=exc.status_code, message=exc.detail, detail=str(exc)).model_dump())

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        error_details = []
        for error in exc.errors():
            field = ".".join(str(p) for p in error["loc"])
            error_details.append(f"{field}: {error['msg']}")
        return JSONResponse(status_code=422, content=ErrorResponse(code=422, message="Validation Error", detail="; ".join(error_details)).model_dump())

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        return JSONResponse(status_code=500, content=ErrorResponse(code=500, message="Internal Server Error", detail=str(exc) if app.debug else "An unexpected error occurred").model_dump())
