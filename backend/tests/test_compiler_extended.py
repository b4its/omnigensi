import uuid
import pytest
from app.models.agent import AgentTemplate
from app.models.provider import LLMProvider
from app.engine.compiler import compile_workflow_graph, build_dynamic_agent_node, _simulate_agent_fallback


@pytest.mark.asyncio
async def test_supervisor_node_execution():
    provider_id = uuid.uuid4()
    provider = LLMProvider(
        id=provider_id,
        name="Test Provider",
        provider_type="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key_encrypted="mock_encrypted_key",
    )

    supervisor = AgentTemplate(
        id=uuid.uuid4(),
        provider_id=provider_id,
        name="CHRONOS-SUPERVISOR",
        avatar_code="cyber-bot-05",
        role="Executive System Orchestrator",
        goal="Synthesize deliverables and issue operational directives",
        backstory="Master operational strategist for autonomous multi-agent clusters",
        node_type="supervisor",
        model_name="openai/gpt-4o",
        temperature=0.5,
        max_tokens=2048,
        tools_config=[],
        require_device_approval=False,
    )

    state = {
        "task_prompt": "Design a distributed AI cluster",
        "shared_context": "Deep research complete.",
        "current_draft": "Draft specs v1",
        "revision_count": 0,
        "execution_history": [],
    }

    # Test supervisor fallback/simulation
    res = await _simulate_agent_fallback(supervisor, state, "supervisor-node-1", publisher=None)
    assert "current_draft" in res
    assert "Executive Directives" in res["current_draft"]
    assert res["execution_history"][0]["node_type"] == "supervisor"


@pytest.mark.asyncio
async def test_graph_with_supervisor_and_worker():
    provider_id = uuid.uuid4()
    p = LLMProvider(
        id=provider_id,
        name="Provider",
        provider_type="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key_encrypted="enc",
    )

    a1 = AgentTemplate(
        id=uuid.uuid4(),
        provider_id=provider_id,
        name="Worker 1",
        avatar_code="bot-1",
        role="Worker Researcher",
        goal="Research",
        backstory="Backstory",
        node_type="worker",
        model_name="gpt-4o-mini",
        tools_config=[],
        require_device_approval=False,
    )

    a2 = AgentTemplate(
        id=uuid.uuid4(),
        provider_id=provider_id,
        name="Supervisor 1",
        avatar_code="bot-2",
        role="Lead Supervisor",
        goal="Direct",
        backstory="Backstory",
        node_type="supervisor",
        model_name="gpt-4o",
        tools_config=[],
        require_device_approval=False,
    )

    agents_map = {str(a1.id): a1, str(a2.id): a2}
    providers_map = {str(provider_id): p}

    schema = {
        "nodes": [
            {"node_id": "n1", "agent_id": str(a1.id)},
            {"node_id": "n2", "agent_id": str(a2.id)},
        ],
        "edges": [
            {"from": "n1", "to": "n2", "type": "normal"},
            {"from": "n2", "to": "END", "type": "normal"},
        ],
        "entry_point": "n1",
    }

    compiled = compile_workflow_graph(schema, agents_map, providers_map, max_revisions=2)
    assert compiled is not None

    init_state = {
        "task_prompt": "Test mission",
        "shared_context": "",
        "current_draft": "",
        "reviewer_feedback": "",
        "is_approved": False,
        "revision_count": 0,
        "generated_files": [],
        "execution_history": [],
    }

    final_state = await compiled.ainvoke(init_state)
    assert len(final_state["execution_history"]) == 2
    assert final_state["execution_history"][1]["node_type"] == "supervisor"
