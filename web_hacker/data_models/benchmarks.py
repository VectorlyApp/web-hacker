"""
web_hacker/data_models/benchmarks.py

Data models for routine evaluation and benchmarking.
"""

import statistics
from enum import StrEnum
from typing import Annotated, Any, Literal, Union

from openai import OpenAI
from pydantic import BaseModel, Field

from web_hacker.data_models.routine.routine import Routine


class ExpressionOperator(StrEnum):
    """Operators for evaluating expressions against data."""
    
    # Equality
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    
    # Containment
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    
    # Type checks
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    IS_TYPE = "is_type"
    
    # Comparison (for numbers)
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    
    # String operations
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    MATCHES_REGEX = "matches_regex"
    
    # Collection operations
    LENGTH_EQUALS = "length_equals"
    LENGTH_GREATER_THAN = "length_greater_than"
    LENGTH_LESS_THAN = "length_less_than"
    IS_EMPTY = "is_empty"
    IS_NOT_EMPTY = "is_not_empty"
    
    # Existence (for checking if path exists)
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"


# Operator display symbols for pretty printing
OPERATOR_SYMBOLS: dict[str, str] = {
    "equals": "==",
    "not_equals": "!=",
    "contains": "contains",
    "not_contains": "not contains",
    "is_null": "is null",
    "is_not_null": "is not null",
    "is_type": "is type",
    "greater_than": ">",
    "greater_than_or_equal": ">=",
    "less_than": "<",
    "less_than_or_equal": "<=",
    "starts_with": "starts with",
    "ends_with": "ends with",
    "matches_regex": "matches",
    "length_equals": "length ==",
    "length_greater_than": "length >",
    "length_less_than": "length <",
    "is_empty": "is empty",
    "is_not_empty": "is not empty",
    "exists": "exists",
    "not_exists": "not exists",
}


def _format_value(value: Any) -> str:
    """Format a value for display."""
    if value is None:
        return "null"
    elif isinstance(value, str):
        return f'"{value}"'
    elif isinstance(value, bool):
        return "true" if value else "false"
    elif isinstance(value, (list, dict)):
        import json
        return json.dumps(value)
    else:
        return str(value)


def _get_value_at_path(data: Any, path: str) -> tuple[bool, Any]:
    """
    Get value at a dot-notation path from data.
    
    Uses dot notation everywhere:
        - Object keys: "user.name"
        - Array indices: "items.0.name" (not items[0])
        - Nested paths: "data.users.0.profile.email"
    
    Returns:
        tuple[bool, Any]: (exists, value) - exists is False if path doesn't exist
    """
    if not path:
        return True, data
    
    current = data
    parts = path.split('.')
    
    for part in parts:
        if current is None:
            return False, None
        
        # Check if part is a numeric index
        if part.isdigit():
            index = int(part)
            if isinstance(current, (list, tuple)) and 0 <= index < len(current):
                current = current[index]
            else:
                return False, None
        else:
            # Regular key access
            if isinstance(current, dict) and part in current:
                current = current[part]
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                return False, None
    
    return True, current


class SimpleExpression(BaseModel):
    """
    A simple expression that evaluates a condition against data at a given path.
    
    Examples:
        {"type": "simple", "path": "user.name", "operator": "equals", "value": "John"}
        {"type": "simple", "path": "items.0.name", "operator": "equals", "value": "Apple"}
        {"type": "simple", "path": "count", "operator": "greater_than", "value": 10}
    """
    
    type: Literal["simple"] = Field(
        default="simple",
        description="Expression type discriminator"
    )
    
    path: str = Field(
        description="Dot notation path to the data (e.g., 'user.name', 'items.0.id', 'data.results')"
    )
    
    operator: ExpressionOperator = Field(
        description="The operator to use for comparison"
    )
    
    value: Any = Field(
        default=None,
        description="The expected value to compare against. Can be any type: str, int, float, bool, list, dict, None"
    )
    
    def stringify(self) -> str:
        """Convert expression to human-readable string."""
        op_symbol = OPERATOR_SYMBOLS.get(self.operator.value, self.operator.value)
        
        # Operators that don't need a value
        if self.operator in (
            ExpressionOperator.IS_NULL,
            ExpressionOperator.IS_NOT_NULL,
            ExpressionOperator.IS_EMPTY,
            ExpressionOperator.IS_NOT_EMPTY,
            ExpressionOperator.EXISTS,
            ExpressionOperator.NOT_EXISTS,
        ):
            return f"{self.path} {op_symbol}"
        
        return f"{self.path} {op_symbol} {_format_value(self.value)}"
    
    def evaluate(self, data: Any) -> bool:
        """
        Evaluate this expression against the given data.
        
        Args:
            data: The data object to evaluate against (dict, object, etc.)
            
        Returns:
            bool: True if the expression passes, False otherwise
        """
        import re
        
        exists, actual = _get_value_at_path(data, self.path)
        
        # Handle existence operators first
        if self.operator == ExpressionOperator.EXISTS:
            return exists
        if self.operator == ExpressionOperator.NOT_EXISTS:
            return not exists
        
        # For all other operators, path must exist
        if not exists:
            return False
        
        # Null checks
        if self.operator == ExpressionOperator.IS_NULL:
            return actual is None
        if self.operator == ExpressionOperator.IS_NOT_NULL:
            return actual is not None
        
        # Type check
        if self.operator == ExpressionOperator.IS_TYPE:
            type_map = {
                "str": str, "string": str,
                "int": int, "integer": int,
                "float": float, "number": (int, float),
                "bool": bool, "boolean": bool,
                "list": list, "array": list,
                "dict": dict, "object": dict,
                "none": type(None), "null": type(None),
            }
            expected_type = type_map.get(str(self.value).lower())
            if expected_type:
                return isinstance(actual, expected_type)
            return False
        
        # Empty checks
        if self.operator == ExpressionOperator.IS_EMPTY:
            if actual is None:
                return True
            if isinstance(actual, (str, list, dict, tuple)):
                return len(actual) == 0
            return False
        if self.operator == ExpressionOperator.IS_NOT_EMPTY:
            if actual is None:
                return False
            if isinstance(actual, (str, list, dict, tuple)):
                return len(actual) > 0
            return True
        
        # Equality
        if self.operator == ExpressionOperator.EQUALS:
            return actual == self.value
        if self.operator == ExpressionOperator.NOT_EQUALS:
            return actual != self.value
        
        # Containment
        if self.operator == ExpressionOperator.CONTAINS:
            if isinstance(actual, str) and isinstance(self.value, str):
                return self.value in actual
            if isinstance(actual, (list, tuple)):
                return self.value in actual
            if isinstance(actual, dict):
                return self.value in actual
            return False
        if self.operator == ExpressionOperator.NOT_CONTAINS:
            if isinstance(actual, str) and isinstance(self.value, str):
                return self.value not in actual
            if isinstance(actual, (list, tuple)):
                return self.value not in actual
            if isinstance(actual, dict):
                return self.value not in actual
            return True
        
        # Comparison (numbers)
        if self.operator == ExpressionOperator.GREATER_THAN:
            try:
                return float(actual) > float(self.value)
            except (TypeError, ValueError):
                return False
        if self.operator == ExpressionOperator.GREATER_THAN_OR_EQUAL:
            try:
                return float(actual) >= float(self.value)
            except (TypeError, ValueError):
                return False
        if self.operator == ExpressionOperator.LESS_THAN:
            try:
                return float(actual) < float(self.value)
            except (TypeError, ValueError):
                return False
        if self.operator == ExpressionOperator.LESS_THAN_OR_EQUAL:
            try:
                return float(actual) <= float(self.value)
            except (TypeError, ValueError):
                return False
        
        # String operations
        if self.operator == ExpressionOperator.STARTS_WITH:
            if isinstance(actual, str) and isinstance(self.value, str):
                return actual.startswith(self.value)
            return False
        if self.operator == ExpressionOperator.ENDS_WITH:
            if isinstance(actual, str) and isinstance(self.value, str):
                return actual.endswith(self.value)
            return False
        if self.operator == ExpressionOperator.MATCHES_REGEX:
            if isinstance(actual, str) and isinstance(self.value, str):
                return bool(re.search(self.value, actual))
            return False
        
        # Length operations
        if self.operator == ExpressionOperator.LENGTH_EQUALS:
            if hasattr(actual, '__len__'):
                return len(actual) == self.value
            return False
        if self.operator == ExpressionOperator.LENGTH_GREATER_THAN:
            if hasattr(actual, '__len__'):
                return len(actual) > self.value
            return False
        if self.operator == ExpressionOperator.LENGTH_LESS_THAN:
            if hasattr(actual, '__len__'):
                return len(actual) < self.value
            return False
        
        return False


class CompositeExpression(BaseModel):
    """
    A composite expression that combines multiple expressions with AND/OR logic.
    
    Examples:
        {"type": "composite", "logic": "and", "expressions": [...]}
        {"type": "composite", "logic": "or", "expressions": [...]}
    """
    
    type: Literal["composite"] = Field(
        default="composite",
        description="Expression type discriminator"
    )
    
    logic: Literal["and", "or"] = Field(
        description="Logic operator: 'and' (all must pass) or 'or' (at least one must pass)"
    )
    
    expressions: list["Expression"] = Field(
        description="List of expressions to combine. Can be simple or composite (nested)."
    )
    
    def stringify(self) -> str:
        """Convert expression to human-readable string."""
        logic_str = " AND " if self.logic == "and" else " OR "
        parts = [stringify_expression(expr) for expr in self.expressions]
        inner = logic_str.join(parts)
        return f"({inner})"
    
    def evaluate(self, data: Any) -> bool:
        """
        Evaluate this composite expression against the given data.
        
        Args:
            data: The data object to evaluate against (dict, object, etc.)
            
        Returns:
            bool: True if the expression passes, False otherwise
                  - AND: all expressions must pass
                  - OR: at least one expression must pass
        """
        if self.logic == "and":
            return all(evaluate_expression(expr, data) for expr in self.expressions)
        else:  # or
            return any(evaluate_expression(expr, data) for expr in self.expressions)


def evaluate_expression(expr: "SimpleExpression | CompositeExpression", data: Any) -> bool:
    """
    Evaluate any expression against the given data.
    
    Args:
        expr: The expression to evaluate (simple or composite)
        data: The data object to evaluate against
        
    Returns:
        bool: True if the expression passes, False otherwise
    """
    return expr.evaluate(data)


def stringify_expression(expr: "SimpleExpression | CompositeExpression") -> str:
    """
    Convert any expression to a human-readable string.
    
    Examples:
        >>> stringify_expression(SimpleExpression(path="user.name", operator="equals", value="John"))
        'user.name == "John"'
        
        >>> stringify_expression(CompositeExpression(logic="and", expressions=[...]))
        '(user.age > 18 AND user.verified == true)'
    """
    return expr.stringify()


# Union type with discriminator for JSON parsing
Expression = Annotated[
    Union[SimpleExpression, CompositeExpression],
    Field(discriminator="type")
]

# Update forward reference for CompositeExpression
CompositeExpression.model_rebuild()


class DeterministicTest(BaseModel):
    """
    A deterministic test with a root expression that must pass.

    The expression can be:
    - A simple expression (type: "simple", path + operator + value)
    - A composite expression (type: "composite", logic + expressions)

    Example JSON:
        {
            "name": "user_is_adult_and_verified",
            "description": "User must be 18+ and verified",
            "expression": {
                "type": "composite",
                "logic": "and",
                "expressions": [
                    {"type": "simple", "path": "user.age", "operator": "greater_than", "value": 18},
                    {"type": "simple", "path": "user.verified", "operator": "equals", "value": true}
                ]
            }
        }
    """

    name: str = Field(
        description="Name of the test"
    )

    description: str = Field(
        default="",
        description="Description of what this test validates"
    )

    expression: SimpleExpression | CompositeExpression = Field(
        description="The expression to evaluate. Can be simple or composite (with AND/OR logic)."
    )

    result: bool | None = Field(
        default=None,
        description="Result of the test after running. True if passed, False if failed, None if not run."
    )

    def run(self, data: Any) -> bool:
        """
        Run the deterministic test against the provided data.

        Args:
            data: The data object to evaluate against

        Returns:
            bool: True if the test passed, False otherwise
        """
        self.result = evaluate_expression(self.expression, data)
        return self.result


class LLMTestResult(BaseModel):
    """
    Result of running an LLMTest.
    """

    score: float = Field(
        description="Normalized score produced by the LLM"
    )

    rationale: str | None = Field(
        default=None,
        description="LLM explanation for the score"
    )

    confidence: float | None = Field(
        default=None,
        description="Optional confidence estimate (0.0–1.0)"
    )

    def passed(self, threshold: float | None) -> bool | None:
        if threshold is None:
            return None
        return self.score >= threshold


class LLMTest(BaseModel):
    """
    A non-deterministic test evaluated by an LLM.

    The LLM inspects some data and answers a question or produces a score.
    """

    name: str = Field(
        description="Name of the test"
    )

    description: str = Field(
        default="",
        description="What this test evaluates"
    )

    prompt: str = Field(
        description=(
            "The evaluation prompt given to the LLM. "
            "May reference the data under test."
        )
    )

    model: str = Field(
        description="LLM model identifier used for evaluation (e.g. gpt-4.1, claude-3.5-sonnet)"
    )

    n_trials: int = Field(
        default=3,
        ge=1,
        description="Number of independent LLM evaluations to run"
    )

    score_range: tuple[float, float] = Field(
        default=(0.0, 1.0),
        description="Minimum and maximum possible score"
    )

    passing_threshold: float | None = Field(
        default=None,
        description=(
            "Optional threshold above which the test is considered passing. "
            "If None, the test does not produce pass/fail directly."
        )
    )

    aggregation: Literal["mean", "median", "min", "max"] = Field(
        default="mean",
        description="How to aggregate scores across trials"
    )

    results: list[LLMTestResult] = Field(
        default_factory=list,
        description="Results from running this test. Populated after run() is called."
    )

    def run(self, data: Any, client: OpenAI) -> LLMTestResult:
        """
        Run the LLM test against the provided data.

        Args:
            data: The data to evaluate
            client: OpenAI client instance

        Returns:
            LLMTestResult: Aggregated result from n_trials evaluations
        """
        full_prompt = (
            f"{self.prompt}\n\n"
            f"Data to evaluate:\n{data}\n\n"
            f"Provide a score between {self.score_range[0]} and {self.score_range[1]}."
        )

        # Run n_trials evaluations
        trial_results: list[LLMTestResult] = []
        for _ in range(self.n_trials):
            response = client.responses.parse(
                model=self.model,
                input=[{"role": "user", "content": full_prompt}],
                text_format=LLMTestResult
            )
            trial_results.append(response.output_parsed)

        # Aggregate scores
        scores = [r.score for r in trial_results]
        if self.aggregation == "mean":
            final_score = statistics.mean(scores)
        elif self.aggregation == "median":
            final_score = statistics.median(scores)
        elif self.aggregation == "min":
            final_score = min(scores)
        else:  # max
            final_score = max(scores)

        # Aggregate confidence if present
        confidences = [r.confidence for r in trial_results if r.confidence is not None]
        final_confidence = statistics.mean(confidences) if confidences else None

        # Use rationale from the result closest to the aggregated score
        closest_result = min(trial_results, key=lambda r: abs(r.score - final_score))

        aggregated_result = LLMTestResult(
            score=final_score,
            rationale=closest_result.rationale,
            confidence=final_confidence
        )
        self.results.append(aggregated_result)
        return aggregated_result


class RoutineDiscoveryEvaluation(BaseModel):
    """
    A test case for evaluating routine discovery.

    Contains the task description, expected ground truth routine,
    model to use for discovery, and tests to validate the discovered routine.
    """
    
    name: str = Field(
        description="The name of the evaluation"
    )

    description: str = Field(
        default="",
        description="The description of the evaluation"
    )

    task: str = Field(
        description="The task description given to the routine discovery agent"
    )

    ground_truth_routine: Routine = Field(
        description="The expected routine that should be discovered"
    )

    llm_model: str = Field(
        description="The LLM model identifier to use for routine discovery (e.g. gpt-4.1, claude-3.5-sonnet)"
    )

    deterministic_tests: list[DeterministicTest] = Field(
        default_factory=list,
        description="List of deterministic tests to run against the discovered routine"
    )

    llm_tests: list[LLMTest] = Field(
        default_factory=list,
        description="List of LLM-based tests to run against the discovered routine"
    )

    # Results populated after running the evaluation
    generated_routine: Routine | None = Field(
        default=None,
        description="The routine generated by the discovery agent. Populated after running."
    )

    discovery_duration: float | None = Field(
        default=None,
        description="Time taken to discover the routine in seconds. Populated after running."
    )