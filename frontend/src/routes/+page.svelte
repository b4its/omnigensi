<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { api } from '$lib/api';
  import { notify } from '$lib/stores/notify.svelte';
  import { deviceBridge } from '$lib/stores/deviceBridge.svelte';
  import CyberCard from '$lib/components/ui/CyberCard.svelte';
  import CyberButton from '$lib/components/ui/CyberButton.svelte';
  import {
    Activity,
    Server,
    Bot,
    Network,
    Terminal,
    HardDrive,
    ArrowRight,
    Play,
    CheckCircle2,
    Clock,
    FileText,
    Cpu,
    ExternalLink,
  } from 'lucide-svelte';

  let providers = $state<any[]>([]);
  let agents = $state<any[]>([]);
  let workflows = $state<any[]>([]);
  let executions = $state<any[]>([]);
  let loading = $state<boolean>(true);
  let quickTask = $state<string>('Design a high-availability banking gateway architecture with real-time fraud detection');
  let launching = $state<boolean>(false);

  onMount(async () => {
    try {
      const [p, a, w, e] = await Promise.all([
        api.getProviders().catch(() => []),
        api.getAgents().catch(() => []),
        api.getWorkflows().catch(() => []),
        api.getExecutions().catch(() => []),
      ]);
      providers = p;
      agents = a;
      workflows = w;
      executions = e;
    } finally {
      loading = false;
    }
  });

  async function handleQuickLaunch() {
    if (!quickTask.trim()) return;
    const targetWorkflow = workflows[0];
    if (!targetWorkflow) {
      notify.warning("No workflow found. Assemble a workflow in Graph Builder first.");
      return;
    }

    launching = true;
    try {
      const res = await api.executeWorkflow(targetWorkflow.id, quickTask);
      goto(`/playground?execution_id=${res.id}`);
    } catch (err: any) {
      notify.fromError(err, "Launch failed");
    } finally {
      launching = false;
    }
  }
</script>

<div class="space-y-6">
  <!-- Hero Section -->
  <div class="relative overflow-hidden border border-[var(--border-color)] bg-[var(--bg-surface)] p-6 chamfer">
    <div class="absolute -right-10 -bottom-10 opacity-10 pointer-events-none">
      <Cpu class="w-64 h-64 text-[var(--accent-primary)]" />
    </div>

    <div class="relative z-10 max-w-3xl space-y-3">
      <div class="inline-flex items-center gap-2 px-2.5 py-1 text-[11px] font-code rounded border border-[var(--accent-primary)]/40 bg-[var(--accent-primary)]/10 text-[var(--accent-primary)]">
        <span class="w-1.5 h-1.5 rounded-full bg-[var(--accent-primary)] animate-ping"></span>
        NEXUS-BLUE // MULTI-AGENT AIaaS ORCHESTRATOR 2.0
      </div>

      <h1 class="text-2xl md:text-3xl font-hud font-black text-[var(--text-primary)] tracking-wide">
        DYNAMIC AGENT COLLABORATION & LOCAL DEVICE BRIDGE
      </h1>

      <p class="text-sm text-[var(--text-muted)] leading-relaxed">
        Assemble role-based CrewAI personas into stateful cyclic LangGraph pipelines. Connect directly to Omnirouter, LiteLLM, or local Ollama, and autonomously generate <code class="text-[var(--accent-primary)]">.md</code>, <code class="text-[var(--accent-primary)]">.docx</code>, and <code class="text-[var(--accent-primary)]">.pdf</code> artifacts onto your local workstation hard drive.
      </p>

      <!-- Quick Launch Bar -->
      <div class="pt-2 flex flex-col sm:flex-row gap-2">
        <div class="relative flex-1">
          <input
            type="text"
            bind:value={quickTask}
            placeholder="Enter mission objective..."
            class="w-full px-3.5 py-2.5 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-xs font-code text-[var(--text-primary)] rounded-none focus:outline-none focus:border-[var(--accent-primary)]"
          />
        </div>
        <CyberButton
          variant="primary"
          disabled={launching || workflows.length === 0}
          onclick={handleQuickLaunch}
        >
          <Play class="w-4 h-4 fill-current" />
          <span>{launching ? 'INITIALIZING...' : 'QUICK LAUNCH'}</span>
        </CyberButton>
      </div>
    </div>
  </div>

  <!-- Metric HUD Cards -->
  <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
    <CyberCard code="METRIC.01" title="LLM PROVIDERS">
      <div class="flex items-center justify-between">
        <div>
          <div class="text-3xl font-hud font-black text-[var(--accent-primary)]">
            {providers.length}
          </div>
          <div class="text-[11px] text-[var(--text-muted)] mt-1">Omnirouter / Ollama Vaults</div>
        </div>
        <Server class="w-8 h-8 text-[var(--accent-secondary)] opacity-60" />
      </div>
      <div class="mt-3 pt-2 border-t border-[var(--border-color)]/50 text-[10px] text-[var(--accent-primary)]">
        <a href="/providers" class="hover:underline flex items-center gap-1">
          Configure vaults &rarr;
        </a>
      </div>
    </CyberCard>

    <CyberCard code="METRIC.02" title="AGENT TEMPLATES">
      <div class="flex items-center justify-between">
        <div>
          <div class="text-3xl font-hud font-black text-[var(--accent-primary)]">
            {agents.length}
          </div>
          <div class="text-[11px] text-[var(--text-muted)] mt-1">Dynamic Worker & QA Personas</div>
        </div>
        <Bot class="w-8 h-8 text-[var(--accent-secondary)] opacity-60" />
      </div>
      <div class="mt-3 pt-2 border-t border-[var(--border-color)]/50 text-[10px] text-[var(--accent-primary)]">
        <a href="/agents" class="hover:underline flex items-center gap-1">
          Open Agent Studio &rarr;
        </a>
      </div>
    </CyberCard>

    <CyberCard code="METRIC.03" title="WORKFLOW GRAPHS">
      <div class="flex items-center justify-between">
        <div>
          <div class="text-3xl font-hud font-black text-[var(--accent-primary)]">
            {workflows.length}
          </div>
          <div class="text-[11px] text-[var(--text-muted)] mt-1">Cyclic LangGraph Blueprints</div>
        </div>
        <Network class="w-8 h-8 text-[var(--accent-secondary)] opacity-60" />
      </div>
      <div class="mt-3 pt-2 border-t border-[var(--border-color)]/50 text-[10px] text-[var(--accent-primary)]">
        <a href="/workflows" class="hover:underline flex items-center gap-1">
          Build & Route Graphs &rarr;
        </a>
      </div>
    </CyberCard>

    <CyberCard code="METRIC.04" title="HARDWARE BRIDGE">
      <div class="flex items-center justify-between">
        <div>
          <div class="text-base font-hud font-bold {deviceBridge.directoryHandle ? 'text-[var(--status-success)]' : 'text-[var(--status-warning)]'}">
            {deviceBridge.directoryHandle ? 'ACTIVE DISK' : 'STANDBY'}
          </div>
          <div class="text-[11px] text-[var(--text-muted)] mt-1 truncate max-w-[140px]">
            {deviceBridge.mountedFolderName || 'No local disk mounted'}
          </div>
        </div>
        <HardDrive class="w-8 h-8 text-[var(--accent-secondary)] opacity-60" />
      </div>
      <div class="mt-3 pt-2 border-t border-[var(--border-color)]/50 text-[10px]">
        {#if deviceBridge.directoryHandle}
          <span class="text-[var(--status-success)] font-semibold">Auto-write verified</span>
        {:else}
          <button
            type="button"
            onclick={() => deviceBridge.mountLocalDirectory()}
            class="text-[var(--accent-primary)] hover:underline"
          >
            Mount Local Drive &rarr;
          </button>
        {/if}
      </div>
    </CyberCard>
  </div>

  <!-- Main Grid: Recent Telemetry & Active Pipeline -->
  <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
    <!-- Active Agents Showcase -->
    <div class="lg:col-span-2 space-y-4">
      <CyberCard code="REGISTRY.01" title="INSTANTIATED DYNAMIC AGENT ROSTER">
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {#each agents as agent}
            <div class="border border-[var(--border-color)] bg-[var(--bg-elevated)]/50 p-3 chamfer-sm space-y-2">
              <div class="flex items-center justify-between">
                <span class="font-hud font-bold text-xs text-[var(--text-primary)]">{agent.name}</span>
                <span class="text-[9px] font-code px-1.5 py-0.5 rounded uppercase {agent.node_type === 'reviewer' ? 'bg-[var(--status-warning)]/20 text-[var(--status-warning)]' : 'bg-[var(--accent-primary)]/20 text-[var(--accent-primary)]'}">
                  {agent.node_type}
                </span>
              </div>
              <p class="text-[11px] text-[var(--text-muted)] line-clamp-2">{agent.role}</p>
              <div class="flex items-center justify-between text-[10px] font-code text-[var(--text-muted)] pt-1 border-t border-[var(--border-color)]/30">
                <span class="truncate max-w-[130px]">{agent.model_name}</span>
                <span>{agent.tools_config?.length || 0} Tools</span>
              </div>
            </div>
          {/each}
        </div>
      </CyberCard>
    </div>

    <!-- Recent Executions Stream -->
    <div>
      <CyberCard code="TELEMETRY.02" title="RECENT EXECUTIONS">
        <div class="space-y-3">
          {#if executions.length === 0}
            <div class="text-xs text-[var(--text-muted)] italic py-6 text-center">
              No executions yet. Run quick launch above!
            </div>
          {/if}

          {#each executions.slice(0, 5) as exec}
            <a
              href={`/playground?execution_id=${exec.id}`}
              class="block border border-[var(--border-color)] bg-[var(--bg-elevated)]/40 p-2.5 rounded-sm hover:border-[var(--accent-primary)] transition-colors group"
            >
              <div class="flex items-center justify-between text-[11px] font-code">
                <span class="font-bold text-[var(--accent-primary)] group-hover:underline">
                  EXEC // {exec.id.slice(0, 8)}
                </span>
                <span class="px-1.5 py-0.2 rounded text-[10px] uppercase font-bold {exec.status === 'completed' ? 'text-[var(--status-success)]' : exec.status === 'running' ? 'text-[var(--status-warning)] animate-pulse' : 'text-[var(--status-danger)]'}">
                  {exec.status}
                </span>
              </div>
              <p class="text-[11px] text-[var(--text-primary)] mt-1 line-clamp-1">
                {exec.task_prompt}
              </p>
              <div class="flex items-center gap-3 text-[10px] text-[var(--text-muted)] mt-1.5">
                <span>{exec.generated_files?.length || 0} Files Generated</span>
                <span>•</span>
                <span>{exec.total_tokens || 0} Tokens</span>
              </div>
            </a>
          {/each}
        </div>
      </CyberCard>
    </div>
  </div>
</div>
