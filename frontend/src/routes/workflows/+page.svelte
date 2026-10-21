<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { api } from '$lib/api';
  import { notify } from '$lib/stores/notify.svelte';
  import CyberCard from '$lib/components/ui/CyberCard.svelte';
  import CyberButton from '$lib/components/ui/CyberButton.svelte';
  import AgentNode from '$lib/components/workflow/AgentNode.svelte';
  import { SvelteFlow, Controls, Background, BackgroundVariant } from '@xyflow/svelte';
  import '@xyflow/svelte/dist/style.css';
  import {
    Network,
    Plus,
    Trash2,
    Play,
    ArrowRight,
    ArrowDown,
    RotateCcw,
    CheckCircle,
    Sliders,
    Save,
    Cpu,
    LayoutGrid,
    ListFilter,
    ShieldCheck,
} from 'lucide-svelte';

  let workflows = $state<any[]>([]);
  let agents = $state<any[]>([]);
  let loading = $state<boolean>(true);

  // View Mode: 'canvas' (Xyflow interactive graph) vs 'list' (sequential configuration)
  let viewMode = $state<'canvas' | 'list'>('canvas');

  // Active / Selected Workflow for visual editing
  let selectedWorkflow = $state<any | null>(null);

  // Form State for new or edited workflow
  let wfName = $state<string>('');
  let wfDesc = $state<string>('');
  let wfMaxRevisions = $state<number>(3);
  let pipelineNodes = $state<Array<{ nodeId: string; agentId: string }>>([]);
  let conditionalEdges = $state<Array<{ from: string; on_approve: string; on_reject: string }>>([]);
  let isSaving = $state<boolean>(false);

  const nodeTypes = {
    agentNode: AgentNode,
  };

  async function loadData() {
    try {
      loading = true;
      const [w, a] = await Promise.all([
        api.getWorkflows(),
        api.getAgents(),
      ]);
      workflows = w;
      agents = a;
      if (workflows.length > 0 && !selectedWorkflow) {
        selectWorkflow(workflows[0]);
      } else if (workflows.length === 0) {
        initNewPipeline();
      }
    } catch (err: any) {
      console.error(err);
    } finally {
      loading = false;
    }
  }

  onMount(loadData);

  function selectWorkflow(wf: any) {
    selectedWorkflow = wf;
    wfName = wf.name;
    wfDesc = wf.description || '';
    wfMaxRevisions = wf.max_revisions || 3;

    const schema = wf.graph_schema || {};
    pipelineNodes = (schema.nodes || []).map((n: any) => ({
      nodeId: n.node_id,
      agentId: n.agent_id,
    }));

    conditionalEdges = (schema.edges || [])
      .filter((e: any) => e.type === 'conditional')
      .map((e: any) => ({
        from: e.from,
        on_approve: e.on_approve || 'END',
        on_reject: e.on_reject || (pipelineNodes[0]?.nodeId || 'END'),
      }));
  }

  function initNewPipeline() {
    selectedWorkflow = null;
    wfName = 'CUSTOM // Autonomous Multi-Agent Pipeline';
    wfDesc = 'Sequential pipeline with automated QA review loop';
    wfMaxRevisions = 3;

    if (agents.length >= 2) {
      pipelineNodes = [
        { nodeId: 'node_1', agentId: agents[0].id },
        { nodeId: 'node_2', agentId: agents[1].id },
      ];
    } else {
      pipelineNodes = [];
    }
    conditionalEdges = [];
  }

  function addNodeToPipeline() {
    if (agents.length === 0) return;
    const nextIdx = pipelineNodes.length + 1;
    const newNodeId = `node_${nextIdx}`;
    pipelineNodes = [
      ...pipelineNodes,
      { nodeId: newNodeId, agentId: agents[0].id },
    ];
  }

  function removeNodeFromPipeline(idx: number) {
    pipelineNodes = pipelineNodes.filter((_, i) => i !== idx);
  }

  function getAgent(agentId: string) {
    return agents.find(a => a.id === agentId);
  }

  function buildGraphSchema(nodes: any[], edges: any[]) {
    return {
      entry_point: pipelineNodes[0]?.nodeId || 'node_1',
      nodes,
      edges,
    };
  }

  /** Builds the current graph the same way save does, for validation. */
  function currentGraph() {
    const nodes = pipelineNodes.map((n) => ({ node_id: n.nodeId, agent_id: n.agentId }));
    const edges: any[] = [];
    for (let i = 0; i < pipelineNodes.length; i++) {
      const curr = pipelineNodes[i];
      const next = pipelineNodes[i + 1];
      const ag = getAgent(curr.agentId);
      if (ag?.node_type === 'reviewer') {
        const prevWorker = pipelineNodes
          .slice(0, i)
          .reverse()
          .find((p) => getAgent(p.agentId)?.node_type === 'worker');
        edges.push({
          from: curr.nodeId,
          type: 'conditional',
          on_approve: next ? next.nodeId : 'END',
          on_reject: prevWorker ? prevWorker.nodeId : pipelineNodes[0].nodeId,
        });
      } else {
        edges.push({ from: curr.nodeId, to: next ? next.nodeId : 'END', type: 'normal' });
      }
    }
    return buildGraphSchema(nodes, edges);
  }

  let validation = $state<{
    valid: boolean;
    summary: string;
    issues: { code: string; message: string; node_id?: string; field?: string }[];
  } | null>(null);
  let validating = $state(false);

  /** Dry-run the graph so problems surface before saving. */
  async function handleValidateWorkflow() {
    validating = true;
    validation = null;
    try {
      const res = await api.validateWorkflowGraph({
        name: wfName || 'untitled',
        max_revisions: wfMaxRevisions,
        graph_schema: currentGraph(),
      });
      validation = res;
      if (res.valid) notify.success(res.summary);
      else notify.error(res.summary);
    } catch (err) {
      notify.fromError(err, 'Validation failed');
    } finally {
      validating = false;
    }
  }

  async function handleDuplicateWorkflow(id: string) {
    try {
      await api.duplicateWorkflow(id);
      await loadData();
      notify.success('Workflow duplicated');
    } catch (err) {
      notify.fromError(err, 'Duplicate failed');
    }
  }

  async function handleSaveWorkflow() {
    if (!wfName.trim() || pipelineNodes.length === 0) {
      notify.warning('Provide a workflow name and at least one step.');
      return;
    }

    isSaving = true;
    try {
      const nodes = pipelineNodes.map(n => ({
        node_id: n.nodeId,
        agent_id: n.agentId,
      }));

      const edges: any[] = [];
      for (let i = 0; i < pipelineNodes.length; i++) {
        const curr = pipelineNodes[i];
        const next = pipelineNodes[i + 1];
        const ag = getAgent(curr.agentId);

        if (ag?.node_type === 'reviewer') {
          const prevWorker = pipelineNodes.slice(0, i).reverse().find(p => getAgent(p.agentId)?.node_type === 'worker');
          const rejectTarget = prevWorker ? prevWorker.nodeId : pipelineNodes[0].nodeId;
          const approveTarget = next ? next.nodeId : 'END';

          edges.push({
            from: curr.nodeId,
            type: 'conditional',
            on_approve: approveTarget,
            on_reject: rejectTarget,
          });
        } else {
          edges.push({
            from: curr.nodeId,
            to: next ? next.nodeId : 'END',
            type: 'normal',
          });
        }
      }

      const graph_schema = buildGraphSchema(nodes, edges);

      const payload = {
        name: wfName,
        description: wfDesc,
        max_revisions: wfMaxRevisions,
        graph_schema,
      };

      if (selectedWorkflow?.id) {
        await api.updateWorkflow(selectedWorkflow.id, payload);
      } else {
        await api.createWorkflow(payload);
      }

      await loadData();
      notify.success('Workflow saved to the graph compiler registry.');
    } catch (err: any) {
      notify.fromError(err, "Save failed");
    } finally {
      isSaving = false;
    }
  }

  async function handleDeleteWorkflow(id: string) {
    const confirmed = await notify.confirm({
      title: 'DELETE WORKFLOW',
      message: 'Delete this workflow blueprint? This cannot be undone.',
      confirmLabel: 'DELETE',
    });
    if (!confirmed) return;
    try {
      await api.deleteWorkflow(id);
      await loadData();
    } catch (err: any) {
      notify.fromError(err, "Delete failed");
    }
  }

  async function handleLaunchWorkflow() {
    if (!selectedWorkflow) return;
    goto(`/playground?workflow_id=${selectedWorkflow.id}`);
  }

  // Derive Xyflow nodes & edges dynamically
  const xyflowNodes = $derived(
    pipelineNodes.map((n, idx) => {
      const ag = getAgent(n.agentId);
      return {
        id: n.nodeId,
        type: 'agentNode',
        position: { x: 200, y: idx * 150 + 30 },
        data: {
          label: n.nodeId,
          agent_name: ag?.name || n.nodeId,
          role: ag?.role,
          node_type: ag?.node_type || 'worker',
          model_name: ag?.model_name,
          tools_config: ag?.tools_config || [],
        },
      };
    })
  );

  const xyflowEdges = $derived(
    pipelineNodes.flatMap((n, idx) => {
      const next = pipelineNodes[idx + 1];
      const ag = getAgent(n.agentId);
      const list: any[] = [];

      if (next) {
        list.push({
          id: `edge-${n.nodeId}-${next.nodeId}`,
          source: n.nodeId,
          target: next.nodeId,
          animated: true,
          style: 'stroke: #00F0FF; stroke-width: 2px;',
        });
      }

      if (ag?.node_type === 'reviewer') {
        const prevWorker = pipelineNodes.slice(0, idx).reverse().find(p => getAgent(p.agentId)?.node_type === 'worker');
        if (prevWorker) {
          list.push({
            id: `edge-reject-${n.nodeId}-${prevWorker.nodeId}`,
            source: n.nodeId,
            sourceHandle: 'reject',
            target: prevWorker.nodeId,
            label: 'REVISE LOOP',
            animated: true,
            style: 'stroke: #FFB800; stroke-width: 2px; stroke-dasharray: 5,5;',
          });
        }
      }
      return list;
    })
  );
</script>

<div class="space-y-6">
  <!-- Header Bar -->
  <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-[var(--border-color)] pb-4">
    <div>
      <div class="text-[11px] font-code text-[var(--accent-primary)] uppercase tracking-wider">
        MODULE // 04
      </div>
      <h1 class="text-xl md:text-2xl font-hud font-black text-[var(--text-primary)]">
        DYNAMIC WORKFLOW & LANGGRAPH COMPILER
      </h1>
      <p class="text-xs text-[var(--text-muted)] mt-1">
        Assemble sequential pipelines and cyclic feedback loops with automated Reviewer quality enforcement.
      </p>
    </div>

    <div class="flex items-center gap-2">
      <CyberButton variant="outline" size="sm" onclick={initNewPipeline}>
        <Plus class="w-4 h-4" />
        <span>NEW BLUEPRINT</span>
      </CyberButton>

      <CyberButton
        variant="primary"
        size="sm"
        disabled={!selectedWorkflow}
        onclick={handleLaunchWorkflow}
      >
        <Play class="w-4 h-4 fill-current" />
        <span>LAUNCH WORKFLOW</span>
      </CyberButton>
    </div>
  </div>

  <div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
    <!-- Saved Workflows Sidebar -->
    <div class="lg:col-span-1 space-y-3">
      <div class="text-xs font-hud font-bold text-[var(--text-primary)]">
        REGISTERED BLUEPRINTS
      </div>

      {#if workflows.length === 0}
        <div class="border border-dashed border-[var(--border-color)] p-4 text-center chamfer-sm space-y-2">
          <Network class="w-6 h-6 mx-auto text-[var(--text-muted)] opacity-50" />
          <p class="text-[10px] font-code text-[var(--text-muted)]">
            No blueprints yet. Build one and press PERSIST GRAPH BLUEPRINT.
          </p>
        </div>
      {/if}
      {#each workflows as wf}
        {@const isSel = selectedWorkflow?.id === wf.id}
        <button
          type="button"
          onclick={() => selectWorkflow(wf)}
          class="w-full text-left p-3 border rounded-sm transition-all cursor-pointer font-code text-xs {isSel ? 'border-[var(--accent-primary)] bg-[var(--accent-primary)]/10 text-[var(--text-primary)] shadow-[var(--border-glow)]' : 'border-[var(--border-color)] bg-[var(--bg-surface)] text-[var(--text-muted)] hover:border-[var(--accent-primary)]/60'}"
        >
          <div class="font-bold text-[11px] font-hud line-clamp-1">{wf.name}</div>
          <div class="text-[10px] text-[var(--text-muted)] mt-1">
            {wf.graph_schema?.nodes?.length || 0} Nodes • Max {wf.max_revisions} Revisions
          </div>
        </button>
      {/each}
    </div>

    <!-- Active Pipeline Visual Canvas & Configurator -->
    <div class="lg:col-span-3 space-y-4">
      <CyberCard code="GRAPH.COMPILER" title={selectedWorkflow?.name || 'NEW PIPELINE BUILDER'}>
        <div class="space-y-4 font-code text-xs">
          <!-- Metadata Form -->
          <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div class="sm:col-span-2">
              <label class="block text-[var(--text-muted)] mb-1">
                <span>Workflow Title</span>
                <input
                  type="text"
                  bind:value={wfName}
                  class="w-full mt-1 px-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
                />
              </label>
            </div>

            <div>
              <label class="block text-[var(--text-muted)] mb-1">
                <span>Max Revisions Loop</span>
                <input
                  type="number"
                  min="1"
                  max="10"
                  bind:value={wfMaxRevisions}
                  class="w-full mt-1 px-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
                />
              </label>
            </div>
          </div>

          <!-- Visual Node Flow Canvas & Xyflow View -->
          <div class="pt-4 border-t border-[var(--border-color)]/50">
            <div class="flex items-center justify-between mb-3">
              <div class="flex items-center gap-2">
                <span class="font-hud font-bold text-xs text-[var(--text-primary)]">
                  ASSEMBLY PIPELINE GRAPH
                </span>
                <!-- View Mode Switcher -->
                <div class="flex items-center border border-[var(--border-color)] rounded-sm overflow-hidden text-[10px]">
                  <button
                    type="button"
                    onclick={() => viewMode = 'canvas'}
                    class="px-2 py-1 flex items-center gap-1 font-hud transition-colors {viewMode === 'canvas' ? 'bg-[var(--accent-primary)] text-black font-bold' : 'bg-[var(--bg-surface)] text-[var(--text-muted)] hover:text-[var(--text-primary)]'}"
                  >
                    <LayoutGrid class="w-3 h-3" />
                    XYFLOW CANVAS
                  </button>
                  <button
                    type="button"
                    onclick={() => viewMode = 'list'}
                    class="px-2 py-1 flex items-center gap-1 font-hud transition-colors {viewMode === 'list' ? 'bg-[var(--accent-primary)] text-black font-bold' : 'bg-[var(--bg-surface)] text-[var(--text-muted)] hover:text-[var(--text-primary)]'}"
                  >
                    <ListFilter class="w-3 h-3" />
                    STEP SEQUENCE
                  </button>
                </div>
              </div>

              <CyberButton variant="outline" size="sm" onclick={addNodeToPipeline}>
                <Plus class="w-3.5 h-3.5" />
                <span>ADD STEP</span>
              </CyberButton>
            </div>

            {#if viewMode === 'canvas'}
              <!-- Xyflow Interactive Graph Canvas -->
              <div class="h-[460px] w-full border border-[var(--border-color)] bg-[#030712] chamfer-sm relative overflow-hidden">
                <SvelteFlow
                  nodes={xyflowNodes}
                  edges={xyflowEdges}
                  {nodeTypes}
                  fitView
                  class="bg-[#030712]"
                >
                  <Controls class="!bg-[var(--bg-surface)] !border-[var(--border-color)] !text-[var(--text-primary)]" />
                  <Background variant={BackgroundVariant.Dots} gap={16} size={1} patternColor="#00F0FF" />
                </SvelteFlow>
              </div>
            {:else}
              <!-- Step Sequence List -->
              <div class="space-y-3">
                {#each pipelineNodes as node, idx (node.nodeId + idx)}
                  {@const currentAgent = getAgent(node.agentId)}
                  {@const isReviewer = currentAgent?.node_type === 'reviewer'}

                  <div class="relative border p-3 chamfer-sm transition-all {isReviewer ? 'border-[var(--status-warning)]/60 bg-[var(--status-warning)]/5' : 'border-[var(--border-color)] bg-[var(--bg-elevated)]/40'}">
                    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div class="flex items-center gap-2">
                        <span class="w-6 h-6 rounded-full bg-[var(--accent-primary)] text-black font-hud font-bold text-xs flex items-center justify-center">
                          {idx + 1}
                        </span>
                        <span class="font-hud font-bold text-xs text-[var(--text-primary)]">
                          NODE: {node.nodeId}
                        </span>
                        <span class="px-1.5 py-0.2 rounded text-[9px] uppercase font-bold {isReviewer ? 'bg-[var(--status-warning)]/20 text-[var(--status-warning)]' : 'bg-[var(--accent-primary)]/20 text-[var(--accent-primary)]'}">
                          {currentAgent?.node_type || 'worker'}
                        </span>
                      </div>

                      <div class="flex items-center gap-2">
                        <select
                          bind:value={node.agentId}
                          class="px-2.5 py-1.5 bg-[var(--bg-surface)] border border-[var(--border-color)] text-xs text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
                        >
                          {#each agents as ag}
                            <option value={ag.id}>{ag.name} ({ag.node_type})</option>
                          {/each}
                        </select>

                        <button
                          type="button"
                          onclick={() => removeNodeFromPipeline(idx)}
                          class="p-2.5 text-[var(--status-danger)] hover:bg-[var(--status-danger)]/10 rounded"
                          title="Remove step"
                        >
                          <Trash2 class="w-4 h-4" />
                        </button>
                      </div>
                    </div>

                    <!-- Reviewer Cyclic Edge Indicator -->
                    {#if isReviewer}
                      <div class="mt-2.5 pt-2 border-t border-[var(--status-warning)]/30 flex items-center gap-2 text-[10px] text-[var(--status-warning)]">
                        <RotateCcw class="w-3.5 h-3.5 animate-spin-slow" />
                        <span>
                          Cyclic Loop Active: If <code class="font-bold">is_approved = false</code>, rolls back to preceding Worker node for revision (Max {wfMaxRevisions} loops).
                        </span>
                      </div>
                    {/if}
                  </div>

                  <!-- Edge Connector Arrow -->
                  {#if idx < pipelineNodes.length - 1}
                    <div class="flex justify-center my-1 text-[var(--accent-primary)]">
                      <ArrowDown class="w-4 h-4" />
                    </div>
                  {/if}
                {/each}
              </div>
            {/if}
          </div>

          <!-- Validation result -->
          {#if validation}
            <div
              class="mt-3 border chamfer-sm px-3 py-2.5 font-code text-xs space-y-1.5 {validation.valid
                ? 'border-[var(--status-success)]/50 bg-[var(--status-success)]/10'
                : 'border-[var(--status-danger)]/50 bg-[var(--status-danger)]/10'}"
              role="status"
            >
              <div class="flex items-center justify-between gap-2">
                <span class="font-bold {validation.valid ? 'text-[var(--status-success)]' : 'text-[var(--status-danger)]'}">
                  {validation.valid ? 'GRAPH VALID' : 'GRAPH INVALID'}
                </span>
                <button
                  type="button"
                  onclick={() => (validation = null)}
                  class="px-2 py-1 text-[10px] text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                >
                  DISMISS
                </button>
              </div>
              <p class="text-[11px] text-[var(--text-primary)] break-words">{validation.summary}</p>
              {#if !validation.valid && validation.issues.length > 0}
                <ul class="list-disc pl-4 space-y-0.5 text-[10px] text-[var(--text-muted)]">
                  {#each validation.issues as issue}
                    <li class="break-words">
                      {issue.message}{#if issue.field} <span class="opacity-70">({issue.field})</span>{/if}
                    </li>
                  {/each}
                </ul>
              {/if}
            </div>
          {/if}

          <!-- Save Actions -->
          <div class="pt-4 border-t border-[var(--border-color)] flex flex-wrap justify-between items-center gap-2">
            <div class="flex items-center gap-2">
              {#if selectedWorkflow}
                <button
                  type="button"
                  onclick={() => handleDuplicateWorkflow(selectedWorkflow.id)}
                  class="px-3 py-2.5 text-[11px] font-hud border border-[var(--border-color)] text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] chamfer-sm"
                >
                  DUPLICATE
                </button>
                <button
                  type="button"
                  onclick={() => handleDeleteWorkflow(selectedWorkflow.id)}
                  class="px-3 py-2.5 text-[11px] font-hud border border-[var(--status-danger)]/40 text-[var(--status-danger)] hover:bg-[var(--status-danger)]/10 chamfer-sm"
                >
                  DELETE
                </button>
              {/if}
            </div>

            <div class="flex items-center gap-2">
              <CyberButton
                variant="outline"
                disabled={validating || pipelineNodes.length === 0}
                onclick={handleValidateWorkflow}
              >
                <ShieldCheck class="w-4 h-4" />
                <span>{validating ? 'VALIDATING...' : 'VALIDATE'}</span>
              </CyberButton>
              <CyberButton variant="primary" disabled={isSaving} onclick={handleSaveWorkflow}>
                <Save class="w-4 h-4" />
                <span>{isSaving ? 'COMPILING GRAPH...' : 'PERSIST GRAPH BLUEPRINT'}</span>
              </CyberButton>
            </div>
          </div>
        </div>
      </CyberCard>
    </div>
  </div>
</div>
