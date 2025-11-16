import asyncio
import logging
import typing
from abc import ABC
from functools import wraps
from inspect import Parameter, signature
from random import random
from typing import Awaitable, Callable, Concatenate, Generic, ParamSpec, TypeVar, overload

import asyncpg

from sftkit.database import Pool

T = TypeVar("T")


class Service(ABC, Generic[T]):
    def __init__(self, db_pool: Pool, config: T, transaction_retries: int | None = None):
        self.db_pool = db_pool
        self.config = config

        self.default_transaction_retries = transaction_retries or 10


R = TypeVar("R")
Self = TypeVar("Self", bound=Service)
P = ParamSpec("P")

_READONLY_KWARG_NAME = "__read_only__"


def _is_func_read_only(kwargs, func):
    is_readonly = kwargs.get(_READONLY_KWARG_NAME, False)
    if _READONLY_KWARG_NAME not in signature(func).parameters:
        kwargs.pop(_READONLY_KWARG_NAME)

    return is_readonly


def _add_readonly_to_kwargs(read_only: bool, kwargs, func):
    if _READONLY_KWARG_NAME in signature(func).parameters:
        kwargs[_READONLY_KWARG_NAME] = read_only


def _add_arg_to_signature(original_func, new_func, name: str, annotation):
    sig = signature(original_func)
    new_parameters = tuple(sig.parameters.values()) + (
        Parameter(name, kind=Parameter.KEYWORD_ONLY, annotation=annotation),
    )
    sig = sig.replace(parameters=new_parameters)
    new_func.__signature__ = sig  # type: ignore


def with_db_connection(
    func: Callable[Concatenate[Self, P], Awaitable[R]],
) -> Callable[Concatenate[Self, P], Awaitable[R]]:
    @wraps(func)
    async def wrapper(self, *args: P.args, **kwargs: P.kwargs):
        if "conn" in kwargs:
            return await func(self, *args, **kwargs)

        async with self.db_pool.acquire() as conn:
            return await func(self, *args, conn=conn, **kwargs)

    return wrapper


def _with_db_isolation_transaction(
    func: Callable[Concatenate[Self, P], Awaitable[R]], read_only: bool, n_retries: int | None = None
) -> Callable[Concatenate[Self, P], Awaitable[R]]:
    @wraps(func)
    async def wrapper(self, *args: P.args, **kwargs: P.kwargs):
        _add_readonly_to_kwargs(read_only, kwargs, func)

        max_retries = n_retries or self.default_transaction_retries
        current_retries = max_retries
        if "conn" in kwargs:
            return await func(self, *args, **kwargs)

        async with self.db_pool.acquire() as conn:
            exception = None
            while current_retries > 0:
                try:
                    async with conn.transaction(isolation=None if read_only else "serializable"):
                        return await func(self, *args, conn=conn, **kwargs)
                except (
                    asyncpg.exceptions.DeadlockDetectedError,
                    asyncpg.exceptions.SerializationError,
                ) as e:
                    current_retries -= 1
                    # random quadratic back off, with a max of 1 second
                    delay = min(random() * (max_retries - current_retries) ** 2 * 0.0001, 1.0)
                    if delay == 1.0:
                        logging.warning(
                            "Max waiting time in quadratic back off of one second reached,"
                            "check if there is any problem with your database transactions."
                        )
                    await asyncio.sleep(delay)

                    exception = e

            if exception:
                raise exception
            else:
                raise RuntimeError("Unexpected error")

    return wrapper


@overload
def with_db_transaction(
    func: Callable[Concatenate[Self, P], Awaitable[R]],
) -> Callable[Concatenate[Self, P], Awaitable[R]]:
    """Case without arguments"""


@overload
def with_db_transaction(
    read_only: bool,
    n_retries: int | None = None,
) -> Callable[[Callable[Concatenate[Self, P], Awaitable[R]]], Callable[Concatenate[Self, P], Awaitable[R]]]:
    """Case with arguments"""


@typing.no_type_check
def with_db_transaction(read_only, n_retries: int | None = None):
    if callable(read_only):
        return _with_db_isolation_transaction(read_only, read_only=False, n_retries=n_retries)
    else:

        def wrapper(func):
            return _with_db_isolation_transaction(func, read_only=read_only, n_retries=n_retries)

        return wrapper
