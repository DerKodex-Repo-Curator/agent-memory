"""Utility functions for agent tool binding."""

import inspect
from functools import wraps


def bind_tool(func, neo4j_service):
    """Create a wrapper that binds neo4j_service to a tool function.

    ADK FunctionTool inspects the function signature to determine which
    parameters the LLM should provide. We create a wrapper with a
    modified signature that hides neo4j_service entirely.
    """
    sig = inspect.signature(func)
    if "neo4j_service" not in sig.parameters:
        raise TypeError(f"{func.__name__} must accept a 'neo4j_service' parameter")
    if not inspect.iscoroutinefunction(func):
        raise TypeError(f"{func.__name__} must be an async function")

    new_params = [p for name, p in sig.parameters.items() if name != "neo4j_service"]

    @wraps(func)
    async def wrapper(*args, **kwargs):
        kwargs["neo4j_service"] = neo4j_service
        return await func(*args, **kwargs)

    wrapper.__signature__ = sig.replace(parameters=new_params)
    return wrapper
