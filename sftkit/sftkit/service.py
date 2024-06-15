import asyncio
import logging
from abc import ABC
from functools import wraps
from inspect import Parameter, signature
from random import random
from typing import Awaitable, Callable, Generic, TypeVar, overload

import asyncpg

from sftkit.database import Pool

T = TypeVar("T")
R = TypeVar("R")


def with_db_connection(func: Callable[..., Awaitable[R]]) -> Callable[..., Awaitable[R]]:
    @wraps(func)
    async def wrapper(self, **kwargs):
        if "conn" in kwargs:
            return await func(self, **kwargs)

        async with self.db_pool.acquire() as conn:
            return await func(self, conn=conn, **kwargs)

    return wrapper


@overload
def with_db_transaction(func: Callable[..., Awaitable[R]]) -> Callable[..., Awaitable[R]]:
    """Case without arguments"""


@overload
def with_db_transaction(
    read_only: bool,
) -> Callable[[Callable[..., Awaitable[R]]], Callable[..., Awaitable[R]]]:
    """Case with arguments"""


def with_db_transaction(read_only):
    if callable(read_only):
        return with_db_isolation_transaction(read_only)
    else:

        def wrapper(func):
            return with_db_isolation_transaction(func, read_only=read_only)

        return wrapper


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


def with_db_isolation_transaction(func, read_only: bool = False):
    @wraps(func)
    async def wrapper(self, **kwargs):
        _add_readonly_to_kwargs(read_only, kwargs, func)

        if "conn" in kwargs:
            return await func(self, **kwargs)

        async with self.db_pool.acquire() as conn:
            async with conn.transaction(isolation=None if read_only else "serializable"):
                return await func(self, conn=conn, **kwargs)

    return wrapper


def with_retryable_db_transaction(
    n_retries: int = 10, read_only: bool = False
) -> Callable[[Callable[..., Awaitable[R]]], Callable[..., Awaitable[R]]]:
    def f(func: Callable[..., Awaitable[R]]):
        @wraps(func)
        async def wrapper(self, **kwargs):
            _add_readonly_to_kwargs(read_only, kwargs, func)

            current_retries = n_retries
            if "conn" in kwargs:
                return await func(self, **kwargs)

            async with self.db_pool.acquire() as conn:
                exception = None
                while current_retries > 0:
                    try:
                        async with conn.transaction(isolation=None if read_only else "serializable"):
                            return await func(self, conn=conn, **kwargs)
                    except (
                        asyncpg.exceptions.DeadlockDetectedError,
                        asyncpg.exceptions.SerializationError,
                    ) as e:
                        current_retries -= 1
                        # random quadratic back off, with a max of 1 second
                        delay = min(random() * (n_retries - current_retries) ** 2 * 0.0001, 1.0)
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

    return f


class Service(ABC, Generic[T]):
    def __init__(self, db_pool: Pool, config: T):
        self.db_pool = db_pool
        self.config = config
