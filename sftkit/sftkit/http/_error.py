import typing

from fastapi import Request, status
from fastapi.responses import JSONResponse

from sftkit.error import (
    AccessDenied,
    NotFound,
    ServiceException,
    Unauthorized,
)


def not_found_exception_handler(request: Request, broad_exception: Exception) -> JSONResponse:
    del request
    exc = typing.cast(NotFound, broad_exception)
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "type": "notfound",
            "id": exc.id,
            "element_type": exc.element_type,
            "element_id": exc.element_id,
            "message": str(exc),
        },
    )


def service_exception_handler(request: Request, broad_exception: Exception) -> JSONResponse:
    del request
    exc = typing.cast(ServiceException, broad_exception)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "type": "service",
            "id": exc.id,
            "message": str(exc),
        },
    )


def access_exception_handler(request: Request, broad_exception: Exception) -> JSONResponse:
    del request
    exc = typing.cast(AccessDenied, broad_exception)
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "type": "access",
            "id": exc.id,
            "message": str(exc),
        },
    )


def unauthorized_exception_handler(request: Request, broad_exception: Exception) -> JSONResponse:
    del request
    exc = typing.cast(Unauthorized, broad_exception)
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "type": "unauthorized",
            "id": exc.id,
            "message": str(exc),
        },
    )


def try_again_later_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    del request
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        headers={"Retry-After": "2"},  # time in seconds
        content={
            "type": "service",
            "id": exc.__class__.__name__,
            "message": str(exc),
        },
    )


def bad_request_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    del request
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "type": "service",
            "id": exc.__class__.__name__,
            "message": str(exc),
        },
    )


def catchall_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    del request
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "type": "internal",
            "id": exc.__class__.__name__,
            "message": "Internal Server Error",
        },
    )
