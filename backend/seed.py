import asyncio
import uuid
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core.security import encrypt_api_key
from app.models.provider import LLMProvider
from app.models.agent import AgentTemplate
from app.models.workflow import Workflow


async def seed() -> None:
    print("[*] Starting database seeding for Omnigensi...")
    async with AsyncSessionLocal() as session:
        # 1. Check or create default providers
        q = await session.execute(select(LLMProvider).limit(1))
        existing_provider = q.scalar_one_or_none()

        if not existing_provider:
            openrouter = LLMProvider(
                id=uuid.uuid4(),
                name="Omnirouter Primary Gateway",
                provider_type="openrouter",
                base_url="https://openrouter.ai/api/v1",
                api_key_encrypted=encrypt_api_key("sk-or-v1-demo-key"),
                default_headers={"HTTP-Referer": "https://omnigensi.local"},
                is_active=True,
            )
            ollama = LLMProvider(
                id=uuid.uuid4(),
                name="Local Ollama Gateway",
                provider_type="ollama",
                base_url="http://localhost:11434",
                api_key_encrypted=encrypt_api_key(""),
                default_headers={},
                is_active=True,
            )
            session.add_all([openrouter, ollama])
            await session.commit()
            await session.refresh(openrouter)
            provider = openrouter
            print(f"[+] Created providers: {openrouter.name}, {ollama.name}")
        else:
            provider = existing_provider
            print(f"[=] Reusing existing provider: {provider.name}")

        # 2. Check or create 4 sample agents
        q_agents = await session.execute(select(AgentTemplate))
        existing_agents = q_agents.scalars().all()

        if not existing_agents:
            agent1 = AgentTemplate(
                id=uuid.uuid4(),
                provider_id=provider.id,
                name="CYPHER-01 // Deep Researcher",
                avatar_code="cyber-bot-01",
                role="OSINT & Systems Research Analyst",
                goal="Investigate and collect architecture blueprints, technical documentation, and structured research insights.",
                backstory="Elite cyberspace operative trained in gathering deep intelligence and structural data for modern software stacks.",
                node_type="worker",
                model_name="meta-llama/llama-3.3-70b-instruct",
                temperature=0.4,
                max_tokens=4096,
                tools_config=["read_local_workspace_file", "list_local_workspace_files"],
                require_device_approval=False,
            )

            agent2 = AgentTemplate(
                id=uuid.uuid4(),
                provider_id=provider.id,
                name="SCRIBE-02 // Technical Architect Writer",
                avatar_code="cyber-bot-02",
                role="Lead Systems Architect & Technical Writer",
                goal="Transform raw research notes and user objectives into exhaustive, enterprise-grade technical specifications.",
                backstory="Master specification architect who drafts enterprise-grade documentation with military precision.",
                node_type="worker",
                model_name="anthropic/claude-3.5-sonnet",
                temperature=0.6,
                max_tokens=4096,
                tools_config=[],
                require_device_approval=False,
            )

            agent3 = AgentTemplate(
                id=uuid.uuid4(),
                provider_id=provider.id,
                name="OVERSEER-03 // Strict QA Reviewer",
                avatar_code="cyber-bot-03",
                role="Automated QA Sentinel & Reviewer",
                goal="Critically evaluate technical drafts against industry standards, spotting flaws, omissions, and ambiguities.",
                backstory="Ruthless quality assurance sentinel programmed to accept only 100% rigorous drafts. Rejects incomplete drafts with clear feedback.",
                node_type="reviewer",
                model_name="openai/gpt-4o",
                temperature=0.2,
                max_tokens=2048,
                tools_config=[],
                require_device_approval=False,
            )

            agent4 = AgentTemplate(
                id=uuid.uuid4(),
                provider_id=provider.id,
                name="FABRICATOR-04 // Device Document Publisher",
                avatar_code="cyber-bot-04",
                role="Device & Hardware Artifact Publisher",
                goal="Transform approved technical specifications into production-ready .md, .docx, and .pdf documents on local storage.",
                backstory="Industrial cyber-fabricator that translates digital thought streams into local disk artifacts.",
                node_type="worker",
                model_name="meta-llama/llama-3.3-70b-instruct",
                temperature=0.5,
                max_tokens=4096,
                tools_config=["create_markdown_document", "create_word_document", "create_pdf_document"],
                require_device_approval=False,
            )

            session.add_all([agent1, agent2, agent3, agent4])
            await session.commit()
            print("[+] Seeded 4 default agents: CYPHER-01, SCRIBE-02, OVERSEER-03, FABRICATOR-04")
            agents = [agent1, agent2, agent3, agent4]
        else:
            agents = list(existing_agents)
            print(f"[=] Found {len(agents)} existing agents.")

        # 3. Check or create supervisor agent
        q_sup = await session.execute(
            select(AgentTemplate).where(AgentTemplate.node_type == "supervisor")
        )
        existing_supervisor = q_sup.scalar_one_or_none()

        if not existing_supervisor:
            agent_sup = AgentTemplate(
                id=uuid.uuid4(),
                provider_id=provider.id,
                name="CHRONOS-05 // Strategic Team Supervisor",
                avatar_code="cyber-bot-05",
                role="Executive Multi-Agent Orchestrator & Strategic Synthesizer",
                goal="Harmonize multi-agent outputs, eliminate domain contradictions, and formulate unified strategic deliverables.",
                backstory="High-level orchestration entity designed to govern autonomous agent clusters and enforce executive coherence.",
                node_type="supervisor",
                model_name="openai/gpt-4o",
                temperature=0.3,
                max_tokens=4096,
                tools_config=["mcp_read_file", "mcp_write_file"],
                require_device_approval=True,
            )
            session.add(agent_sup)
            await session.commit()
            print("[+] Seeded supervisor agent: CHRONOS-05 // Strategic Team Supervisor")
            agents.append(agent_sup)

        # 4. Create default workflows
        q_wf = await session.execute(select(Workflow).limit(1))
        existing_wf = q_wf.scalar_one_or_none()

        if not existing_wf and len(agents) >= 4:
            schema1 = {
                "entry_point": "node_1",
                "nodes": [
                    {"node_id": "node_1", "agent_id": str(agents[0].id)},
                    {"node_id": "node_2", "agent_id": str(agents[1].id)},
                    {"node_id": "node_3", "agent_id": str(agents[2].id)},
                    {"node_id": "node_4", "agent_id": str(agents[3].id)},
                ],
                "edges": [
                    {"from": "node_1", "to": "node_2", "type": "normal"},
                    {"from": "node_2", "to": "node_3", "type": "normal"},
                    {
                        "from": "node_3",
                        "type": "conditional",
                        "on_approve": "node_4",
                        "on_reject": "node_2",
                    },
                    {"from": "node_4", "to": "END", "type": "normal"},
                ],
            }

            workflow = Workflow(
                id=uuid.uuid4(),
                name="CYBER-PIPELINE // Full Blueprint & Local Artifact Publisher",
                description="End-to-end multi-agent pipeline with conditional QA review loop and automated .md/.docx/.pdf generation onto local disk.",
                max_revisions=3,
                graph_schema=schema1,
            )
            session.add(workflow)
            await session.commit()
            print(f"[+] Created sample workflow: {workflow.name}")

        # Check if supervisor workflow exists
        q_wf2 = await session.execute(
            select(Workflow).where(Workflow.name.like("%SUPERVISOR%"))
        )
        if not q_wf2.scalar_one_or_none() and len(agents) >= 5:
            schema2 = {
                "entry_point": "node_1",
                "nodes": [
                    {"node_id": "node_1", "agent_id": str(agents[0].id)},
                    {"node_id": "node_2", "agent_id": str(agents[4].id)},
                    {"node_id": "node_3", "agent_id": str(agents[3].id)},
                ],
                "edges": [
                    {"from": "node_1", "to": "node_2", "type": "normal"},
                    {"from": "node_2", "to": "node_3", "type": "normal"},
                    {"from": "node_3", "to": "END", "type": "normal"},
                ],
            }
            wf_supervisor = Workflow(
                id=uuid.uuid4(),
                name="SUPERVISOR-FLOW // Strategic Executive Synthesis & Export",
                description="Supervisor-governed workflow: Deep Researcher passes findings to Chronos-05 Supervisor for master synthesis, then Fabricator materializes disk artifacts.",
                max_revisions=2,
                graph_schema=schema2,
            )
            session.add(wf_supervisor)
            await session.commit()
            print(f"[+] Created supervisor workflow: {wf_supervisor.name}")

    print("[*] Seeding finished successfully!")


if __name__ == "__main__":
    asyncio.run(seed())
