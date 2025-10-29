from enum import StrEnum
from pydantic import BaseModel
from src.data_models.network import Method

class ConfidenceLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class TransactionIdentificationResponse(BaseModel):
    """
    Response from the LLM for identifying the network transaction that directly corresponds to
    the user's requested task. 
    """
    transaction_ids: list[str]
    description: str
    url: str
    method: Method
    explanation: str
    confidence_level: ConfidenceLevel
    
    
class TransactionConfirmationResponse(BaseModel):
    """
    Response obejct for confirming the identified network transactions that directly correspond to
    the user's requested task.
    """
    is_correct: bool
    confirmed_transaction_ids: list[str]
    explanation: str
    confidence_level: ConfidenceLevel


class VariableType(StrEnum):
    ARGUMENT = "argument"
    COOKIE = "cookie"
    TOKEN = "token"
    SYSTEM_VARIABLE = "system_variable"
    CONSTANT = "constant"
    

class Variable(BaseModel):
    """
    A variable that was extracted from the network transaction.
    """
    type: VariableType
    name: str
    value: str
    explanation: str
    example: str

    
class ExtractedVariableResponse(BaseModel):
    """
    Response from the LLM for extracting variables from the network transaction.
    """
    transaction_id: str
    variables: list[Variable]
    explanation: str

