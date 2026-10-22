import operator
from typing import TypedDict, Annotated, List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ReviewDecision(BaseModel):
    is_approved: bool = Field(
        description="True if the draft meets quality standards, False if it needs revision"
    )
    feedback: str = Field(
        description="Specific revision instructions if rejected, or concise validation summary if approved"
    )


class DynamicTeamState(TypedDict):
    task_prompt: str
    shared_context: str
    current_draft: str
    reviewer_feedback: str
    is_approved: bool
    revision_count: int
    generated_files: Annotated[List[Dict[str, Any]], operator.add]
    execution_history: Annotated[List[Dict[str, Any]], operator.add]
    # Set when any node had to fall back to simulated output because the
    # provider failed. Surfaced to clients so a degraded run is never
    # mistaken for a real model response.
    simulated: Annotated[bool, operator.or_]
