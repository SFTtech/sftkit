class ServiceException(Exception):
    id: str


class NotFound(ServiceException):
    """
    raised when something wasn't found.
    """

    id = "NotFound"

    def __init__(self, element_type: str, element_id: str | int | None = None):
        self.element_type = element_type
        self.element_id = element_id

    def __str__(self):
        if self.element_id is None:
            return f"{self.element_type} not found"

        return f"{self.element_type} with id {self.element_id} not found"


class InvalidArgument(ServiceException):
    """
    raised, when the argument error cannot be caught with pydantic, e.g. because of database constraints
    """

    id = "InvalidArgument"

    def __init__(self, msg: str):
        self.msg = msg

    def __str__(self):
        return self.msg


class AccessDenied(ServiceException):
    id = "AccessDenied"

    def __init__(self, msg: str):
        self.msg = msg

    def __str__(self):
        return self.msg


class ResourceNotAllowed(ServiceException):
    id = "ResourceNotAllowed"

    def __init__(self, msg: str):
        self.msg = msg

    def __str__(self):
        return self.msg


class Unauthorized(ServiceException):
    id = "Unauthorized"

    def __init__(self, msg: str):
        self.msg = msg

    def __str__(self):
        return self.msg
