"""Structural validation for workflow graphs.

The compiler only fails at execution time, and with raw exceptions
(``ValueError``/``KeyError``) surfaced through a background task. Clients -
especially a mobile editor - need the same checks *before* saving so a broken
graph is rejected with an actionable message instead of producing a run that
silently dies.

This module validates structure only; it does not touch the LLM.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set

VALID_NODE_TYPES = {"worker", "reviewer", "supervisor"}
VALID_EDGE_TYPES = {"normal", "conditional"}
END_TOKEN = "END"


@dataclass
class GraphIssue:
    """A single reason a graph cannot be executed."""

    code: str
    message: str
    node_id: Optional[str] = None
    edge_index: Optional[int] = None
    field_name: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"code": self.code, "message": self.message}
        if self.node_id is not None:
            data["node_id"] = self.node_id
        if self.edge_index is not None:
            data["edge_index"] = self.edge_index
        if self.field_name is not None:
            data["field"] = self.field_name
        return data


@dataclass
class GraphValidation:
    valid: bool
    issues: List[GraphIssue] = field(default_factory=list)
    node_count: int = 0
    edge_count: int = 0
    entry_point: Optional[str] = None

    @property
    def errors(self) -> List[Dict[str, Any]]:
        return [i.as_dict() for i in self.issues]

    def summary(self) -> str:
        if self.valid:
            return f"Graph is valid ({self.node_count} nodes, {self.edge_count} edges)"
        first = self.issues[0].message if self.issues else "Invalid graph"
        extra = len(self.issues) - 1
        return f"{first}" + (f" (+{extra} more issue(s))" if extra > 0 else "")


def _as_uuid(value: Any) -> Optional[uuid.UUID]:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def validate_graph(
    graph_schema: Optional[Dict[str, Any]],
    known_agent_ids: Optional[Iterable[Any]] = None,
) -> GraphValidation:
    """Checks a workflow graph for structural problems.

    ``known_agent_ids`` is optional: when supplied (the common case for a saved
    workflow) every node must reference an existing agent.
    """
    issues: List[GraphIssue] = []

    if not isinstance(graph_schema, dict):
        return GraphValidation(
            valid=False,
            issues=[
                GraphIssue(
                    code="invalid_schema",
                    message="graph_schema must be an object with 'nodes' and 'edges'",
                    field_name="graph_schema",
                )
            ],
        )

    nodes = graph_schema.get("nodes")
    edges = graph_schema.get("edges", [])

    if not isinstance(nodes, list):
        issues.append(
            GraphIssue(
                code="missing_nodes",
                message="graph_schema.nodes must be a list",
                field_name="nodes",
            )
        )
        nodes = []
    elif not nodes:
        issues.append(
            GraphIssue(
                code="empty_graph",
                message="A workflow needs at least one node",
                field_name="nodes",
            )
        )

    if not isinstance(edges, list):
        issues.append(
            GraphIssue(
                code="invalid_edges",
                message="graph_schema.edges must be a list",
                field_name="edges",
            )
        )
        edges = []

    known_agents: Optional[Set[str]] = None
    if known_agent_ids is not None:
        known_agents = {str(a) for a in known_agent_ids}

    node_ids: List[str] = []
    seen_ids: Set[str] = set()

    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            issues.append(
                GraphIssue(
                    code="invalid_node",
                    message=f"Node #{index} must be an object",
                    node_id=None,
                )
            )
            continue

        node_id = node.get("node_id")
        if not node_id or not isinstance(node_id, str):
            issues.append(
                GraphIssue(
                    code="missing_node_id",
                    message=f"Node #{index} is missing 'node_id'",
                    field_name="node_id",
                )
            )
        elif node_id in seen_ids:
            issues.append(
                GraphIssue(
                    code="duplicate_node_id",
                    message=f"Duplicate node_id '{node_id}'",
                    node_id=node_id,
                    field_name="node_id",
                )
            )
        else:
            seen_ids.add(node_id)
            node_ids.append(node_id)

        agent_id = node.get("agent_id")
        if not agent_id:
            issues.append(
                GraphIssue(
                    code="missing_agent_id",
                    message=f"Node '{node_id or index}' is missing 'agent_id'",
                    node_id=node_id if isinstance(node_id, str) else None,
                    field_name="agent_id",
                )
            )
        else:
            if _as_uuid(agent_id) is None:
                issues.append(
                    GraphIssue(
                        code="invalid_agent_id",
                        message=f"Node '{node_id}' has an agent_id that is not a UUID",
                        node_id=node_id if isinstance(node_id, str) else None,
                        field_name="agent_id",
                    )
                )
            elif known_agents is not None and str(agent_id) not in known_agents:
                issues.append(
                    GraphIssue(
                        code="unknown_agent",
                        message=f"Node '{node_id}' references agent '{agent_id}' which does not exist",
                        node_id=node_id if isinstance(node_id, str) else None,
                        field_name="agent_id",
                    )
                )

        node_type = node.get("node_type")
        if node_type is not None and node_type not in VALID_NODE_TYPES:
            issues.append(
                GraphIssue(
                    code="invalid_node_type",
                    message=f"Node '{node_id}' has invalid node_type '{node_type}'",
                    node_id=node_id if isinstance(node_id, str) else None,
                    field_name="node_type",
                )
            )

    valid_ids = set(node_ids)

    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            issues.append(
                GraphIssue(
                    code="invalid_edge",
                    message=f"Edge #{index} must be an object",
                    edge_index=index,
                )
            )
            continue

        source = edge.get("from")
        target = edge.get("to")
        edge_type = edge.get("type", "normal")

        if not source:
            issues.append(
                GraphIssue(
                    code="missing_edge_source",
                    message=f"Edge #{index} is missing 'from'",
                    edge_index=index,
                    field_name="from",
                )
            )
        elif source not in valid_ids:
            issues.append(
                GraphIssue(
                    code="unknown_edge_source",
                    message=f"Edge #{index} starts at unknown node '{source}'",
                    edge_index=index,
                    field_name="from",
                )
            )

        if edge_type not in VALID_EDGE_TYPES:
            issues.append(
                GraphIssue(
                    code="invalid_edge_type",
                    message=f"Edge #{index} has invalid type '{edge_type}'",
                    edge_index=index,
                    field_name="type",
                )
            )

        if edge_type == "conditional":
            on_approve = edge.get("on_approve", END_TOKEN)
            on_reject = edge.get("on_reject", END_TOKEN)
            for label, value in (("on_approve", on_approve), ("on_reject", on_reject)):
                if value and value != END_TOKEN and value not in valid_ids:
                    issues.append(
                        GraphIssue(
                            code="unknown_edge_target",
                            message=(
                                f"Edge #{index} routes {label} to unknown node '{value}'"
                            ),
                            edge_index=index,
                            field_name=label,
                        )
                    )
        else:
            if target and target != END_TOKEN and target not in valid_ids:
                issues.append(
                    GraphIssue(
                        code="unknown_edge_target",
                        message=f"Edge #{index} points to unknown node '{target}'",
                        edge_index=index,
                        field_name="to",
                    )
                )

    entry_point = graph_schema.get("entry_point")
    resolved_entry = entry_point
    if entry_point and node_ids and entry_point not in valid_ids:
        issues.append(
            GraphIssue(
                code="unknown_entry_point",
                message=f"entry_point '{entry_point}' is not one of the nodes",
                field_name="entry_point",
            )
        )
        resolved_entry = node_ids[0]
    elif not entry_point and node_ids:
        resolved_entry = node_ids[0]

    # A graph where no edge leads anywhere and there is more than one node is
    # almost always a wiring mistake, but not fatal - leave it to the compiler.

    return GraphValidation(
        valid=not issues,
        issues=issues,
        node_count=len(node_ids),
        edge_count=len(edges),
        entry_point=resolved_entry,
    )
