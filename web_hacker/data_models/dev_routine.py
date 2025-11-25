"""
web_hacker/data_models/dev_routine.py
"""

import re
from enum import StrEnum
from typing import Union, Literal

from pydantic import BaseModel


class HTTPMethod(StrEnum):
    """
    Supported HTTP methods for API endpoints.
    """
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


class CREDENTIALS(StrEnum):
    """
    Supported credentials modes for API requests.
    """
    SAME_ORIGIN = "same-origin"
    INCLUDE = "include"
    OMIT = "omit"


class Endpoint(BaseModel):
    """
    Endpoint model with comprehensive parameter validation.
    """
    url: str
    description: str | None
    method: HTTPMethod
    headers: str
    body: str
    credentials: CREDENTIALS = CREDENTIALS.SAME_ORIGIN
    

class Parameter(BaseModel):
    """
    Parameter model with comprehensive validation and type information.
    
    Fields:
        name (str): Parameter name (must be valid Python identifier)
        required (bool): Whether parameter is required
        description (str): Human-readable parameter description
        default (str | None): Default value if not provided
        examples (list[str]): Example values
    """
    name: str
    required: bool = True
    description: str
    default: str | None = None
    examples: list[str] = []


class RoutineOperationTypes(StrEnum):
    """
    Browser operation types for running routines.
    """
    NAVIGATE = "navigate"
    SLEEP = "sleep"
    FETCH = "fetch"
    RETURN = "return"


class RoutineOperation(BaseModel):
    """
    Base class for routine operations.
    
    Args:
        type (RoutineOperationTypes): The type of operation.
    
    Returns:
        RoutineOperation: The interpolated operation.
    """
    type: RoutineOperationTypes


class RoutineNavigateOperation(RoutineOperation):
    """
    Navigate operation for routine.
    
    Args:
        type (Literal[RoutineOperationTypes.NAVIGATE]): The type of operation.
        url (str): The URL to navigate to.
    
    Returns:
        RoutineNavigateOperation: The interpolated operation.
    """
    type: Literal[RoutineOperationTypes.NAVIGATE] = RoutineOperationTypes.NAVIGATE
    url: str


class RoutineSleepOperation(RoutineOperation):
    """
    Sleep operation for routine.
    
    Args:
        type (Literal[RoutineOperationTypes.SLEEP]): The type of operation.
        timeout_seconds (float): The number of seconds to sleep.
    
    Returns:
        RoutineSleepOperation: The interpolated operation.
    """
    type: Literal[RoutineOperationTypes.SLEEP] = RoutineOperationTypes.SLEEP
    timeout_seconds: float


class RoutineFetchOperation(RoutineOperation):
    """
    Fetch operation for routine.
    
    Args:
        type (Literal[RoutineOperationTypes.FETCH]): The type of operation.
        endpoint (Endpoint): The endpoint to fetch.
        session_storage_key (str | None): The session storage key to save the result to (optional).
    
    Returns:
        RoutineFetchOperation: The interpolated operation.
    """
    type: Literal[RoutineOperationTypes.FETCH] = RoutineOperationTypes.FETCH
    endpoint: Endpoint
    session_storage_key: str


class RoutineReturnOperation(RoutineOperation):
    """
    Return operation for routine.
    
    Args:
        type (Literal[RoutineOperationTypes.RETURN]): The type of operation.
        session_storage_key (str): The session storage key to return.
    
    Returns:
        RoutineReturnOperation: The interpolated operation.
    """
    type: Literal[RoutineOperationTypes.RETURN] = RoutineOperationTypes.RETURN
    session_storage_key: str


# Routine operation union _________________________________________________________________________

RoutineOperationUnion = Union[
    RoutineNavigateOperation,
    RoutineSleepOperation,
    RoutineFetchOperation,
    RoutineReturnOperation,
]


class Routine(BaseModel):
    """
    Routine model with comprehensive parameter validation.
    """
    name: str
    description: str
    operations: list[RoutineOperationUnion]
    parameters: list[Parameter]
    
    
    def validate(self) -> tuple[bool, list[str], Exception | None]:
        """
        Validate the routine.
        
        Returns:
            tuple[bool, list[str], Exception | None]: A tuple containing:
                - result: True if the routine is valid, False otherwise
                - errors: A list of error messages if the routine is not valid
                - exception: An exception if an error occurs
        """
        
        
        result = True
        errors = []
        exception = None
        
        try: 
            # must have at least 3 operations (navigate, fetch, return)
            if len(self.operations) < 3:
                result = False
                errors.append("Must have at least 3 operations (navigate, fetch, return)")
            
            # first operation should be a navigate operation
            if not isinstance(self.operations[0], RoutineNavigateOperation):
                result = False
                errors.append("First operation should be a navigate operation")
                
            # last operation should be a return operation
            if not isinstance(self.operations[-1], RoutineReturnOperation):
                result = False
                errors.append("Last operation should be a return operation")
                
            # second to last operation should be a fetch operation
            if not isinstance(self.operations[-2], RoutineFetchOperation):
                result = False
                errors.append("Second to last operation should be a fetch operation")
                
            # get all placeholders
            all_placeholders = self._get_all_placeholders(self.model_dump_json())
                
            # check that every parameter is used at least once
            routine_string = self.model_dump_json()
            for parameter in self.parameters:
                if parameter.name not in all_placeholders:
                    result = False
                    errors.append(f"Parameter '{parameter.name}' is not used in the routine operations...")
                else:
                    all_placeholders.remove(parameter.name)
                    
            # all remaining placeholders should be session storage keys, cookies, local storage
            for placeholder in all_placeholders:
                if placeholder.split(":")[0] not in ["sessionStorage", "cookie", "localStorage", "uuid", "epoch_milliseconds", "meta", "windowProperty"]:
                    result = False
                    errors.append(f"Placeholder '{placeholder}' is not a session storage key, cookie, local storage key, uuid, epoch_milliseconds, meta, or window property...")
                        
            # get all used session storage keys
            all_session_storage_keys = []
            for placeholder in all_placeholders:
                if placeholder.split(":")[0] == "sessionStorage":
                    all_session_storage_keys.append(placeholder.split(":")[1].split(".")[0])
                    
            # get all fetch session storage keys
            all_fetch_session_storage_keys = []
            for operation in self.operations:
                if isinstance(operation, RoutineFetchOperation):
                    all_fetch_session_storage_keys.append(operation.session_storage_key)
            
            # check that every fetch session storage key is used at least once
            for fetch_session_storage_key in all_fetch_session_storage_keys:
                if fetch_session_storage_key not in all_session_storage_keys and fetch_session_storage_key != self.operations[-1].session_storage_key:
                    result = False
                    errors.append(f"Fetch session storage key '{fetch_session_storage_key}' is not used in the routine operations. Fetch may not be necessary for this routine.")
                else:
                    all_session_storage_keys.remove(fetch_session_storage_key)
                    
            # session storage key of the last fetch operation should be the same as the return operation's session storage key
            if self.operations[-1].session_storage_key != self.operations[-2].session_storage_key:
                result = False
                errors.append("Session storage key of the last fetch operation should be the same as the return operation's session storage key")
            
        except Exception as e:
            result = False
            errors.append(f"Exception: {e}")
            exception = e
            
        # return the validation result, errors, and exception
        return result, errors, exception
    
    
    def _get_all_placeholders(self, routine_string: str) -> list[str]:
        """
        Use regex to find all placeholders in the routine string '{{*}}'
        """
        
        placeholders = re.findall(r'{{.*?}}', routine_string)
        return [placeholder[2:-2] for placeholder in set(placeholders)]