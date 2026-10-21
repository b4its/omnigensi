<script lang="ts">
  import { Terminal, ShieldAlert, CheckCircle, FileText, Cpu } from 'lucide-svelte';

  export interface TerminalEntry {
    type: 'agent_start' | 'token_chunk' | 'review_result' | 'device_file_write' | 'info' | 'error' | 'success';
    message?: string;
    agent_name?: string;
    node_id?: string;
    payload?: any;
    timestamp: string;
  }

  interface Props {
    entries: TerminalEntry[];
    currentStreamText?: string;
    activeAgent?: string;
    class?: string;
  }

  let {
    entries = [],
    currentStreamText = '',
    activeAgent = '',
    class: customClass = '',
  }: Props = $props();

  let scrollContainer: HTMLDivElement | null = $state(null);

  $effect(() => {
    // Auto-scroll when new entries or streamed tokens arrive
    if (entries.length || currentStreamText) {
      if (scrollContainer) {
        scrollContainer.scrollTop = scrollContainer.scrollHeight;
      }
    }
  });
</script>

<div class="flex flex-col border border-[var(--border-color)] bg-[#030712] text-[#E0F2FE] chamfer overflow-hidden font-code text-xs {customClass}">
  <!-- Terminal Titlebar -->
  <div class="flex items-center justify-between px-3 py-2 bg-[#081024] border-b border-[var(--border-color)] select-none">
    <div class="flex items-center gap-2">
      <div class="flex gap-1.5">
        <span class="w-2.5 h-2.5 rounded-full bg-[var(--status-danger)]/80 inline-block"></span>
        <span class="w-2.5 h-2.5 rounded-full bg-[var(--status-warning)]/80 inline-block"></span>
        <span class="w-2.5 h-2.5 rounded-full bg-[var(--status-success)]/80 inline-block"></span>
      </div>
      <span class="font-hud text-[11px] text-[var(--accent-primary)] font-bold ml-2">
        TELEMETRY FEED // {activeAgent ? `ACTIVE: ${activeAgent}` : 'IDLE'}
      </span>
    </div>
    <div class="text-[10px] text-[var(--text-muted)]">
      BUFFER: {entries.length} EVENTS
    </div>
  </div>

  <!-- Terminal Content -->
  <div
    bind:this={scrollContainer}
    class="flex-1 p-3 overflow-y-auto space-y-2 max-h-[460px] min-h-[280px]"
  >
    {#if entries.length === 0 && !currentStreamText}
      <div class="text-[var(--text-muted)] italic py-8 text-center">
        &gt; SYSTEM STANDBY. AWAITING WORKFLOW EXECUTION TELEMETRY...
      </div>
    {/if}

    {#each entries as item, idx (idx)}
      <div class="leading-relaxed">
        <span class="text-[var(--text-muted)] opacity-60">[{item.timestamp}]</span>
        
        {#if item.type === 'agent_start'}
          <span class="text-[var(--accent-primary)] font-bold"> &gt;&gt; [DISPATCH]</span>
          <span class="text-[var(--text-primary)]"> Agent </span>
          <span class="text-[var(--accent-primary)] font-semibold">{item.agent_name || item.payload?.agent_name}</span>
          <span class="text-[var(--text-muted)]"> initialized (Model: {item.payload?.model_name || 'default'})</span>

        {:else if item.type === 'review_result'}
          {#if item.payload?.is_approved}
            <span class="text-[var(--status-success)] font-bold"> [AUDIT PASSED]</span>
            <span class="text-[var(--status-success)]"> Reviewer approved draft. Reason: {item.payload?.feedback}</span>
          {:else}
            <span class="text-[var(--status-warning)] font-bold animate-pulse"> [AUDIT REJECTED]</span>
            <span class="text-[var(--status-warning)]"> Rejection feedback: {item.payload?.feedback} (Cycle #{item.payload?.revision_count})</span>
          {/if}

        {:else if item.type === 'device_file_write'}
          <span class="text-[var(--status-success)] font-bold"> [HARDWARE SYNC]</span>
          <span class="text-white"> Generated file: </span>
          <span class="underline text-[var(--accent-primary)]">{item.payload?.filename}</span>
          <span class="text-[var(--text-muted)]"> ({item.payload?.size_bytes} bytes, {item.payload?.file_type})</span>

        {:else if item.type === 'error'}
          <span class="text-[var(--status-danger)] font-bold"> [ALERT CRITICAL]</span>
          <span class="text-[var(--status-danger)]"> {item.message}</span>

        {:else if item.type === 'success'}
          <span class="text-[var(--status-success)] font-bold"> [SYS COMPLETE]</span>
          <span class="text-[var(--status-success)]"> {item.message}</span>

        {:else}
          <span class="text-[var(--text-primary)]"> {item.message || JSON.stringify(item.payload)}</span>
        {/if}
      </div>
    {/each}

    <!-- Live Stream Typing Buffer -->
    {#if currentStreamText}
      <div class="mt-2 p-2.5 rounded bg-[var(--bg-elevated)]/30 border border-[var(--accent-primary)]/30 whitespace-pre-wrap font-mono text-[11px] text-[var(--text-primary)]">
        <div class="text-[10px] text-[var(--accent-primary)] font-bold mb-1 flex items-center gap-1">
          <span class="w-2 h-2 rounded-full bg-[var(--accent-primary)] animate-ping inline-block"></span>
          STREAMING THOUGHTS & GENERATION:
        </div>
        {currentStreamText}<span class="inline-block w-2 h-3.5 bg-[var(--accent-primary)] animate-pulse ml-0.5"></span>
      </div>
    {/if}
  </div>
</div>
