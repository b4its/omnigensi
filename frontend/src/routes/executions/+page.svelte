<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { api } from '$lib/api';
  import { notify } from '$lib/stores/notify.svelte';
  import CyberCard from '$lib/components/ui/CyberCard.svelte';
  import CyberButton from '$lib/components/ui/CyberButton.svelte';
  import {
    History,
    RotateCcw,
    Trash2,
    Play,
    Filter,
    RefreshCw,
    AlertTriangle,
    Cpu,
    FileText,
    Clock
  } from 'lucide-svelte';

  const PAGE_SIZE = 20;
  const STATUSES = [
    { value: '', label: 'ALL STATUSES' },
    { value: 'running', label: 'RUNNING' },
    { value: 'completed', label: 'COMPLETED' },
    { value: 'failed', label: 'FAILED' },
    { value: 'cancelled', label: 'CANCELLED' },
    { value: 'waiting_approval', label: 'AWAITING APPROVAL' },
    { value: 'pending', label: 'PENDING' }
  ];

  let executions = $state<any[]>([]);
  let workflows = $state<any[]>([]);
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let statusFilter = $state('');
  let workflowFilter = $state('');
  let offset = $state(0);
  let total = $state(0);
  let busy = $state<Record<string, boolean>>({});

  const hasMore = $derived(offset + executions.length < total);

  async function load(reset = true) {
    loading = true;
    loadError = null;
    try {
      if (reset) offset = 0;
      const params: Record<string, string | number> = {
        limit: PAGE_SIZE,
        offset
      };
      if (statusFilter) params.status = statusFilter;
      if (workflowFilter) params.workflow_id = workflowFilter;

      const rows = await api.getExecutions(params as any);
      executions = reset ? rows : [...executions, ...rows];
      // The list endpoint reports totals via headers the client cannot read,
      // so infer "more pages" from a full page instead.
      total = reset ? rows.length : Math.max(total, offset + rows.length);
      if (rows.length < PAGE_SIZE) total = offset + rows.length;
    } catch (err) {
      loadError = err instanceof Error ? err.message : 'Unable to load executions';
      if (reset) executions = [];
    } finally {
      loading = false;
    }
  }

  async function loadWorkflows() {
    try {
      workflows = await api.getWorkflows({ limit: 100 });
    } catch {
      workflows = [];
    }
  }

  function workflowName(id: string): string {
    return workflows.find((w) => w.id === id)?.name ?? id.slice(0, 8);
  }

  async function applyFilters() {
    await load(true);
  }

  async function retry(exec: any) {
    busy[exec.id] = true;
    try {
      const created = await api.retryExecution(exec.id);
      notify.success('Execution re-dispatched');
      goto(`/playground?execution_id=${created.id}`);
    } catch (err) {
      notify.fromError(err, 'Retry failed');
    } finally {
      busy[exec.id] = false;
    }
  }

  async function remove(exec: any) {
    const confirmed = await notify.confirm({
      title: 'DELETE EXECUTION',
      message: `Remove run ${exec.id.slice(0, 8)} from history? This cannot be undone.`,
      confirmLabel: 'DELETE'
    });
    if (!confirmed) return;

    busy[exec.id] = true;
    try {
      await api.deleteExecution(exec.id);
      executions = executions.filter((e) => e.id !== exec.id);
      total = Math.max(0, total - 1);
      notify.success('Execution deleted');
    } catch (err) {
      notify.fromError(err, 'Delete failed');
    } finally {
      busy[exec.id] = false;
    }
  }

  function statusClass(status: string): string {
    if (status === 'completed') return 'text-[var(--status-success)] border-[var(--status-success)]/40';
    if (status === 'running') return 'text-[var(--status-warning)] border-[var(--status-warning)]/40';
    if (status === 'cancelled') return 'text-[var(--text-muted)] border-[var(--border-color)]';
    return 'text-[var(--status-danger)] border-[var(--status-danger)]/40';
  }

  const isActive = (status: string) =>
    status === 'running' || status === 'pending' || status === 'waiting_approval';

  onMount(async () => {
    await Promise.all([loadWorkflows(), load(true)]);
  });
</script>

<div class="space-y-6">
  <!-- Header -->
  <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-[var(--border-color)] pb-4">
    <div>
      <div class="text-[11px] font-code text-[var(--accent-primary)] uppercase tracking-wider">
        MODULE // 06
      </div>
      <h1 class="text-xl md:text-2xl font-hud font-black text-[var(--text-primary)]">
        EXECUTION HISTORY
      </h1>
      <p class="text-xs text-[var(--text-muted)] mt-1">
        Every workflow run, with retry and history cleanup.
      </p>
    </div>
    <CyberButton variant="outline" size="sm" onclick={() => load(true)} disabled={loading}>
      <RefreshCw class="w-3.5 h-3.5 {loading ? 'animate-spin' : ''}" />
      <span>REFRESH</span>
    </CyberButton>
  </div>

  <!-- Filters -->
  <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 font-code text-xs">
    <label class="block">
      <span class="block text-[10px] uppercase text-[var(--text-muted)] mb-1">Status</span>
      <select
        bind:value={statusFilter}
        onchange={applyFilters}
        class="w-full px-3 py-2.5 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
      >
        {#each STATUSES as s}
          <option value={s.value}>{s.label}</option>
        {/each}
      </select>
    </label>

    <label class="block">
      <span class="block text-[10px] uppercase text-[var(--text-muted)] mb-1">Workflow</span>
      <select
        bind:value={workflowFilter}
        onchange={applyFilters}
        class="w-full px-3 py-2.5 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
      >
        <option value="">ALL WORKFLOWS</option>
        {#each workflows as wf}
          <option value={wf.id}>{wf.name}</option>
        {/each}
      </select>
    </label>

    <div class="flex items-end">
      <div class="flex items-center gap-2 text-[10px] text-[var(--text-muted)] pb-2.5">
        <Filter class="w-3.5 h-3.5" />
        <span>{executions.length} shown</span>
      </div>
    </div>
  </div>

  <!-- Outage -->
  {#if loadError}
    <div
      class="flex flex-wrap items-center justify-between gap-3 border border-[var(--status-danger)]/60 bg-[var(--status-danger)]/10 chamfer-sm px-3 py-3 font-code text-xs text-[var(--status-danger)]"
      role="alert"
    >
      <span class="flex items-center gap-2 min-w-0">
        <AlertTriangle class="w-4 h-4 shrink-0" />
        <span class="break-words">{loadError}</span>
      </span>
      <button type="button" onclick={() => load(true)} class="shrink-0 px-3 py-2 font-hud font-bold border border-current chamfer-sm">
        RETRY
      </button>
    </div>
  {:else if loading && executions.length === 0}
    <div class="space-y-3">
      {#each Array(4) as _}
        <div class="border border-[var(--border-color)] bg-[var(--bg-surface)]/60 h-24 chamfer animate-pulse"></div>
      {/each}
    </div>
  {:else if executions.length === 0}
    <CyberCard code="HISTORY.00" title="NO RUNS YET">
      <div class="text-center py-8 space-y-3">
        <History class="w-10 h-10 mx-auto text-[var(--text-muted)] opacity-50" />
        <p class="text-xs text-[var(--text-muted)]">
          No executions match this filter. Dispatch a workflow from the Execution Deck.
        </p>
        <CyberButton variant="primary" size="sm" onclick={() => goto('/playground')}>
          <Play class="w-3.5 h-3.5" />
          <span>OPEN EXECUTION DECK</span>
        </CyberButton>
      </div>
    </CyberCard>
  {:else}
    <div class="space-y-3">
      {#each executions as exec (exec.id)}
        <div class="border border-[var(--border-color)] bg-[var(--bg-surface)]/70 chamfer-sm p-3 sm:p-4 space-y-3">
          <div class="flex flex-wrap items-start justify-between gap-2">
            <div class="min-w-0">
              <a
                href={`/playground?execution_id=${exec.id}`}
                class="font-code text-xs font-bold text-[var(--accent-primary)] underline underline-offset-2 break-all"
              >
                EXEC // {exec.id.slice(0, 8)}
              </a>
              <p class="text-[10px] text-[var(--text-muted)] mt-0.5">
                {workflowName(exec.workflow_id)}
              </p>
            </div>
            <span class="shrink-0 text-[10px] font-code font-bold uppercase px-2 py-1 border chamfer-sm {statusClass(exec.status)}">
              {exec.status}
            </span>
          </div>

          <p class="text-xs text-[var(--text-primary)] line-clamp-2 break-words">{exec.task_prompt}</p>

          <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] font-code text-[var(--text-muted)]">
            <span class="flex items-center gap-1"><Cpu class="w-3 h-3" />{exec.total_tokens ?? 0} tokens</span>
            <span class="flex items-center gap-1"><FileText class="w-3 h-3" />{(exec.generated_files || []).length} files</span>
            <span class="flex items-center gap-1">
              <Clock class="w-3 h-3" />
              {exec.started_at ? new Date(exec.started_at).toLocaleString() : '—'}
            </span>
          </div>

          <div class="pt-2 border-t border-[var(--border-color)]/40 flex flex-wrap items-center gap-2">
            <a
              href={`/playground?execution_id=${exec.id}`}
              class="inline-flex items-center gap-1 px-3 py-2 text-[10px] font-hud border border-[var(--border-color)] text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] chamfer-sm"
            >
              <Play class="w-3 h-3" />
              OPEN
            </a>
            <button
              type="button"
              onclick={() => retry(exec)}
              disabled={busy[exec.id] || isActive(exec.status)}
              title={isActive(exec.status) ? 'Cancel the run before retrying' : 'Re-run with the same prompt'}
              class="inline-flex items-center gap-1 px-3 py-2 text-[10px] font-hud border border-[var(--accent-primary)]/50 text-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/10 chamfer-sm disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <RotateCcw class="w-3 h-3" />
              RETRY
            </button>
            <button
              type="button"
              onclick={() => remove(exec)}
              disabled={busy[exec.id] || isActive(exec.status)}
              title={isActive(exec.status) ? 'Cancel the run before deleting' : 'Delete from history'}
              class="inline-flex items-center gap-1 px-3 py-2 text-[10px] font-hud border border-[var(--status-danger)]/50 text-[var(--status-danger)] hover:bg-[var(--status-danger)]/10 chamfer-sm disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Trash2 class="w-3 h-3" />
              DELETE
            </button>
          </div>
        </div>
      {/each}
    </div>

    {#if hasMore}
      <div class="flex justify-center pt-2">
        <CyberButton
          variant="ghost"
          size="sm"
          disabled={loading}
          onclick={() => { offset += PAGE_SIZE; load(false); }}
        >
          {loading ? 'LOADING...' : 'LOAD MORE'}
        </CyberButton>
      </div>
    {/if}
  {/if}
</div>
