<script lang="ts">
  import { Handle, Position } from '@xyflow/svelte';
  import { Bot, CheckCircle, RotateCcw, Cpu, HardDrive } from 'lucide-svelte';

  interface Props {
    data: {
      label?: string;
      agent_name?: string;
      role?: string;
      node_type?: 'worker' | 'reviewer' | 'supervisor';
      model_name?: string;
      tools_config?: string[];
      is_active?: boolean;
      status?: 'idle' | 'running' | 'completed' | 'rejected';
      [key: string]: any;
    };
    isConnectable?: boolean;
  }

  let { data, isConnectable = true }: Props = $props();

  const isReviewer = $derived(data.node_type === 'reviewer');
</script>

<!-- Custom Cyberpunk Agent Node for Xyflow Canvas -->
<div
  class="relative min-w-[220px] max-w-[280px] p-3 border chamfer transition-all duration-200 select-none {data.is_active ? 'border-[var(--accent-primary)] bg-[var(--bg-surface)] shadow-[var(--border-glow)] animate-neon' : isReviewer ? 'border-[var(--status-warning)]/70 bg-[var(--bg-surface)]' : 'border-[var(--border-color)] bg-[var(--bg-surface)]'}"
>
  <!-- Target Handle (Inputs) -->
  <Handle
    type="target"
    position={Position.Top}
    {isConnectable}
    class="!w-3 !h-3 !bg-[var(--accent-primary)] !border-2 !border-[var(--bg-primary)] !rounded-none"
  />

  <!-- Node Header -->
  <div class="flex items-center justify-between gap-2 border-b border-[var(--border-color)]/60 pb-1.5 mb-2">
    <div class="flex items-center gap-1.5">
      <Bot class="w-3.5 h-3.5 text-[var(--accent-primary)]" />
      <span class="font-hud font-bold text-xs text-[var(--text-primary)] truncate">
        {data.agent_name || data.label || 'AGENT NODE'}
      </span>
    </div>

    <span
      class="text-[9px] font-code px-1.5 py-0.2 rounded uppercase font-bold {isReviewer ? 'bg-[var(--status-warning)]/20 text-[var(--status-warning)] border border-[var(--status-warning)]/30' : 'bg-[var(--accent-primary)]/20 text-[var(--accent-primary)] border border-[var(--accent-primary)]/30'}"
    >
      {data.node_type || 'worker'}
    </span>
  </div>

  <!-- Role and Model -->
  <div class="space-y-1 font-code text-[10px]">
    {#if data.role}
      <div class="text-[var(--text-primary)] font-medium line-clamp-1">{data.role}</div>
    {/if}
    {#if data.model_name}
      <div class="text-[var(--text-muted)] truncate flex items-center gap-1">
        <Cpu class="w-3 h-3 text-[var(--accent-secondary)]" />
        {data.model_name}
      </div>
    {/if}
    {#if data.tools_config && data.tools_config.length > 0}
      <div class="text-[var(--accent-primary)] flex items-center gap-1 mt-1">
        <HardDrive class="w-3 h-3" />
        {data.tools_config.length} Hardware Tool{data.tools_config.length > 1 ? 's' : ''}
      </div>
    {/if}
  </div>

  <!-- Source Handle (Outputs) -->
  <Handle
    type="source"
    position={Position.Bottom}
    {isConnectable}
    class="!w-3 !h-3 !bg-[var(--accent-secondary)] !border-2 !border-[var(--bg-primary)] !rounded-none"
  />

  {#if isReviewer}
    <!-- Secondary Handle for Conditional Loop-back -->
    <Handle
      id="reject"
      type="source"
      position={Position.Left}
      {isConnectable}
      class="!w-3 !h-3 !bg-[var(--status-warning)] !border-2 !border-[var(--bg-primary)] !rounded-none"
    />
  {/if}
</div>
