import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict


class WorkflowNodeSchema(BaseModel):
    node_id: str
    agent_id: uuid.UUID


class WorkflowEdgeSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_node: str = Field(alias="from")
    to_node: Optional[str] = Field(default=None, alias="to")
    type: Literal["normal", "conditional"] = "normal"
    on_approve: Optional[str] = None
    on_reject: Optional[str] = None


class WorkflowGraphSchema(BaseModel):
    entry_point: str
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]


class WorkflowBase(BaseModel):
    name: str = Field(..., max_length=150)
    description: Optional[str] = None
    max_revisions: int = Field(default=3, ge=1, le=10)
    graph_schema: Dict[str, Any]


class WorkflowCreate(WorkflowBase):
    pass


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    max_revisions: Optional[int] = None
    graph_schema: Optional[Dict[str, Any]] = None


class WorkflowResponse(WorkflowBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class GraphIssueSchema(BaseModel):
    """One reason a workflow graph cannot run."""

    code: str
    message: str
    node_id: Optional[str] = None
    edge_index: Optional[int] = None
    field: Optional[str] = None


class GraphValidationResponse(BaseModel):
    """Result of a dry-run graph validation."""

    valid: bool
    summary: str
    node_count: int = 0
    edge_count: int = 0
    entry_point: Optional[str] = None
    issues: List[GraphIssueSchema] = Field(default_factory=list)


class WorkflowDuplicateRequest(BaseModel):
    """Optional overrides when cloning a workflow."""

    name: Optional[str] = Field(default=None, max_length=150)
