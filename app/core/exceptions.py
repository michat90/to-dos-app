
from fastapi import HTTPException, status


class BusinessException(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class NotFoundException(BusinessException):
    def __init__(self, resource_name: str, resource_id: int | str):
        message = f"{resource_name} with id {resource_id} was not found."
        super().__init__(message=message, status_code=404)


class ProjectNotFoundException(NotFoundException):
    def __init__(self, project_id: int):
        super().__init__(f"Project with ID {project_id} was not found.")


class TaskNotFoundException(NotFoundException):
    def __init__(self, task_id: int):
        super().__init__(f"Task with ID {task_id} was not found.")


class InvalidTaskDueDateException(BusinessException):
    def __init__(self):
        super().__init__("Task due date cannot be in the past.")


class UserAlreadyExistsException(HTTPException):
    def __init__(self, email: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with email '{email}' already exists.",
        )


class InvalidCredentialsException(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )


class CredentialsException(HTTPException):
    def __init__(self, detail: str = "Could not validate credentials"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )
