<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { page } from '$app/state';
  import { marked } from 'marked';
  import { api } from '$lib/api';
  import { deviceBridge } from '$lib/stores/deviceBridge.svelte';
  import CyberCard from '$lib/components/ui/CyberCard.svelte';
  import CyberButton from '$lib/components/ui/CyberButton.svelte';
  import TerminalLog, { type TerminalEntry } from '$lib/components/ui/TerminalLog.svelte';
  import {
    Play,
    HardDrive,
    Terminal,
    CheckCircle,
    AlertTriangle,
    RotateCcw,
    FileText,
    FileCode,
    Download,
    FolderCheck,
    Cpu,
    Sparkles,
    ShieldAlert,
  } from 'lucide-svelte';

  let workflows = $state<any[]>([]);
  let selectedWorkflowId = $state<string>('');
  let taskPrompt = $state<string>(
    'Architect and implement a secure, low-latency microservices API gateway with distributed token-bucket rate limiting and comprehensive audit logging.'
  );

  let isExecuting = $state<boolean>(false);
  let activeExecutionId = $state<string | null>(null);
  let activeNodeId = $state<string | null>(null);
  let activeAgentName = $state<string>('');
  let streamBuffer = $state<string>('');
  let terminalLogs = $state<TerminalEntry[]>([]);

  // Telemetry Metrics
  let totalTokens = $state<number>(0);
  let estimatedCost = $state<number>(0);
  let revisionCount = $state<number>(0);
  let reviewerDecision = $state<{ is_approved: boolean; feedback: string } | null>(null);

  // Right Panel Tabs
  let activeTab = $state<'output' | 'artifacts'>('output');
  let finalMarkdown = $state<string>('');
  let generatedFiles = $state<any[]>([]);

  // Human-in-the-Loop Device Approval
  let pendingApproval = $state<{
    execution_id: string;
    node_id: string;
    agent_name: string;
    tool_call_id: string;
    tool_name: string;
    tool_args: any;
  } | null>(null);

  let eventSource: EventSource | null = null;

  onMount(async () => {
    try {
      workflows = await api.getWorkflows();
      const queryWf = page.url.searchParams.get('workflow_id');
      const queryExec = page.url.searchParams.get('execution_id');

      if (queryWf) {
        selectedWorkflowId = queryWf;
      } else if (workflows.length > 0) {
        selectedWorkflowId = workflows[0].id;
      }

      if (queryExec) {
        attachToExecution(queryExec);
      }
    } catch (e) {
      console.error(e);
    }
  });

  onDestroy(() => {
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
  });

  function attachToExecution(execId: string) {
    activeExecutionId = execId;
    isExecuting = true;
    terminalLogs = [
      {
        type: 'info',
        message: `Subscribing to telemetry stream execution:${execId}`,
        timestamp: new Date().toLocaleTimeString(),
      },
    ];

    if (eventSource) {
      eventSource.close();
    }

    const streamUrl = api.getExecutionStreamUrl(execId);
    eventSource = new EventSource(streamUrl);

    eventSource.addEventListener('connected', (e: MessageEvent) => {
      terminalLogs = [
        ...terminalLogs,
        {
          type: 'info',
          message: 'SSE Stream uplink established with core orchestrator.',
          timestamp: new Date().toLocaleTimeString(),
        },
      ];
    });

    eventSource.addEventListener('agent_start', (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      activeNodeId = data.node_id;
      activeAgentName = data.agent_name;
      streamBuffer = '';

      terminalLogs = [
        ...terminalLogs,
        {
          type: 'agent_start',
          agent_name: data.agent_name,
          node_id: data.node_id,
          payload: data,
          timestamp: new Date().toLocaleTimeString(),
        },
      ];
    });

    eventSource.addEventListener('token_chunk', (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      if (data.chunk) {
        streamBuffer += data.chunk;
      }
    });

    eventSource.addEventListener('review_result', (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      reviewerDecision = {
        is_approved: data.is_approved,
        feedback: data.feedback,
      };
      revisionCount = data.revision_count;

      terminalLogs = [
        ...terminalLogs,
        {
          type: 'review_result',
          payload: data,
          timestamp: new Date().toLocaleTimeString(),
        },
      ];
    });

    eventSource.addEventListener('device_approval_required', (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      pendingApproval = data;
      terminalLogs = [
        ...terminalLogs,
        {
          type: 'warning',
          message: `[SECURITY AUDIT] Write approval requested by ${data.agent_name} for tool '${data.tool_name}'. Operator signature required.`,
          timestamp: new Date().toLocaleTimeString(),
        },
      ];
    });

    eventSource.addEventListener('supervisor_directive', (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      terminalLogs = [
        ...terminalLogs,
        {
          type: 'info',
          message: `[SUPERVISOR DIRECTIVE] ${data.agent_name}: Strategic synthesis issued.`,
          timestamp: new Date().toLocaleTimeString(),
        },
      ];
    });

    eventSource.addEventListener('device_file_write', async (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      generatedFiles = [...generatedFiles, data];

      terminalLogs = [
        ...terminalLogs,
        {
          type: 'device_file_write',
          payload: data,
          timestamp: new Date().toLocaleTimeString(),
        },
      ];

      // Auto-sync file to local workstation disk via File System Access API
      if (data.filename && data.content_base64) {
        await deviceBridge.saveAgentFileToDevice(
          data.filename,
          data.content_base64,
          data.mime_type || 'application/octet-stream'
        );
      }
    });

    eventSource.addEventListener('workflow_complete', (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      isExecuting = false;
      finalMarkdown = data.final_output || '';
      generatedFiles = data.generated_files || generatedFiles;
      totalTokens = data.total_tokens || 0;
      estimatedCost = data.estimated_cost_usd || 0;

      terminalLogs = [
        ...terminalLogs,
        {
          type: 'success',
          message: 'Multi-Agent Workflow completed successfully. Local disk artifacts synchronized.',
          timestamp: new Date().toLocaleTimeString(),
        },
      ];

      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }
    });

    eventSource.addEventListener('workflow_failed', (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      isExecuting = false;
      terminalLogs = [
        ...terminalLogs,
        {
          type: 'error',
          message: `Execution failed: ${data.error}`,
          timestamp: new Date().toLocaleTimeString(),
        },
      ];

      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }
    });

    eventSource.onerror = () => {
      // Reconnection or close
    };
  }

  async function handleApproval(approved: boolean) {
    if (!pendingApproval || !activeExecutionId) return;
    const approvalData = pendingApproval;
    try {
      await api.approveTool(activeExecutionId, approvalData.tool_call_id, approved);
      terminalLogs = [
        ...terminalLogs,
        {
          type: approved ? 'success' : 'error',
          message: `[OPERATOR DECISION]: Write authorization ${approved ? 'GRANTED' : 'REJECTED'} for ${approvalData.tool_name}.`,
          timestamp: new Date().toLocaleTimeString(),
        },
      ];
    } catch (e: any) {
      console.error('Failed to submit approval:', e);
    } finally {
      pendingApproval = null;
    }
  }

  async function handleExecute() {
    if (!selectedWorkflowId || !taskPrompt.trim()) return;

    isExecuting = true;
    finalMarkdown = '';
    generatedFiles = [];
    terminalLogs = [];
    streamBuffer = '';
    reviewerDecision = null;
    revisionCount = 0;

    try {
      const res = await api.executeWorkflow(selectedWorkflowId, taskPrompt);
      attachToExecution(res.id);
    } catch (err: any) {
      isExecuting = false;
      alert(`Launch error: ${err.message}`);
    }
  }

  const renderedHtml = $derived(marked.parse(finalMarkdown || streamBuffer || ''));
</script>

<div class="space-y-6">
  <!-- Header Bar -->
  <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-[var(--border-color)] pb-4">
    <div>
      <div class="text-[11px] font-code text-[var(--accent-primary)] uppercase tracking-wider">
        MODULE // 05
      </div>
      <h1 class="text-xl md:text-2xl font-hud font-black text-[var(--text-primary)]">
        LIVE EXECUTION DECK // LOCAL HARDWARE BRIDGE
      </h1>
      <p class="text-xs text-[var(--text-muted)] mt-1">
        Real-time telemetry stream, cyclic reviewer looping, and autonomous local disk file creation.
      </p>
    </div>

    <!-- Active Status HUD Badge -->
    <div class="flex items-center gap-2">
      <div class="px-3 py-1.5 rounded-sm border border-[var(--border-color)] bg-[var(--bg-surface)] text-xs font-code flex items-center gap-2">
        <span class="w-2.5 h-2.5 rounded-full {isExecuting ? 'bg-[var(--accent-primary)] animate-ping' : 'bg-[var(--text-muted)]'}"></span>
        <span class="font-bold {isExecuting ? 'text-[var(--accent-primary)]' : 'text-[var(--text-muted)]'}">
          {isExecuting ? 'STREAMING ACTIVE' : 'SYSTEM IDLE'}
        </span>
      </div>
    </div>
  </div>

  <!-- 3-Column Execution Console -->
  <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
    <!-- LEFT PANEL (4 Cols): Launch Controls & Local Hardware Bridge -->
    <div class="lg:col-span-4 space-y-4">
      <CyberCard code="CONTROL.01" title="WORKFLOW DISPATCHER">
        <div class="space-y-4 font-code text-xs">
          <!-- Workflow Selector -->
          <div>
            <label class="block text-[var(--text-muted)] mb-1 uppercase font-bold">
              <span>Select Multi-Agent Pipeline</span>
              <select
                bind:value={selectedWorkflowId}
                disabled={isExecuting}
                class="w-full mt-1 px-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
              >
                {#each workflows as wf}
                  <option value={wf.id}>{wf.name}</option>
                {/each}
              </select>
            </label>
          </div>

          <!-- Task Prompt Input -->
          <div>
            <label class="block text-[var(--text-muted)] mb-1 uppercase font-bold">
              <span>Mission / Task Objective</span>
              <textarea
                bind:value={taskPrompt}
                rows="4"
                disabled={isExecuting}
                placeholder="Describe the software architecture or technical problem..."
                class="w-full mt-1 px-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
              ></textarea>
            </label>
          </div>

          <!-- Local Hardware Bridge Control Panel -->
          <div class="border border-[var(--border-color)] bg-[var(--bg-surface)] p-3 chamfer-sm space-y-2">
            <div class="flex items-center justify-between">
              <span class="font-hud font-bold text-[11px] text-[var(--accent-primary)] flex items-center gap-1.5">
                <HardDrive class="w-4 h-4" />
                LOCAL HARDWARE BRIDGE
              </span>
              <span class="text-[9px] font-bold px-1.5 py-0.5 rounded uppercase {deviceBridge.directoryHandle ? 'bg-[var(--status-success)]/20 text-[var(--status-success)]' : 'bg-[var(--status-warning)]/20 text-[var(--status-warning)]'}">
                {deviceBridge.directoryHandle ? 'MOUNTED' : 'UNMOUNTED'}
              </span>
            </div>

            <p class="text-[10px] text-[var(--text-muted)] leading-tight">
              {#if deviceBridge.directoryHandle}
                Connected to folder <code class="text-[var(--text-primary)] font-bold">[{deviceBridge.mountedFolderName}]</code>. When agents invoke file generation tools, files will write straight to your local PC.
              {:else}
                Mount your workstation project folder via Web File System Access API for automatic document sync without manual downloads.
              {/if}
            </p>

            <button
              type="button"
              onclick={() => deviceBridge.directoryHandle ? deviceBridge.disconnectDirectory() : deviceBridge.mountLocalDirectory()}
              class="w-full py-2 px-3 text-xs font-hud font-bold text-center border chamfer-sm transition-all cursor-pointer {deviceBridge.directoryHandle ? 'border-[var(--status-danger)]/50 text-[var(--status-danger)] hover:bg-[var(--status-danger)]/10' : 'border-[var(--accent-primary)] text-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/15 shadow-[0_0_8px_rgba(0,240,255,0.25)]'}"
            >
              {deviceBridge.directoryHandle ? 'DISCONNECT LOCAL DRIVE' : '⚡ MOUNT LOCAL HARD DRIVE'}
            </button>
          </div>

          <!-- Launch Button -->
          <CyberButton
            variant="primary"
            class="w-full py-3"
            disabled={isExecuting || !selectedWorkflowId || !taskPrompt.trim()}
            onclick={handleExecute}
          >
            <Play class="w-4 h-4 fill-current" />
            <span>{isExecuting ? 'EXECUTION IN PROGRESS...' : 'DISPATCH AGENT PIPELINE'}</span>
          </CyberButton>

          <!-- Telemetry Quick Numbers -->
          {#if activeExecutionId}
            <div class="pt-2 border-t border-[var(--border-color)]/40 grid grid-cols-2 gap-2 text-[10px]">
              <div>
                <span class="text-[var(--text-muted)]">Tokens Streamed:</span>
                <span class="font-bold text-[var(--accent-primary)] ml-1">{totalTokens}</span>
              </div>
              <div>
                <span class="text-[var(--text-muted)]">Revisions:</span>
                <span class="font-bold text-[var(--status-warning)] ml-1">#{revisionCount}</span>
              </div>
            </div>
          {/if}
        </div>
      </CyberCard>
    </div>

    <!-- CENTER PANEL (5 Cols): Live Telemetry Terminal & Stepper -->
    <div class="lg:col-span-5 space-y-4">
      <!-- Reviewer Loop Status Alert -->
      {#if reviewerDecision}
        <div class="p-3 border chamfer-sm font-code text-xs transition-all {reviewerDecision.is_approved ? 'border-[var(--status-success)] bg-[var(--status-success)]/10 text-[var(--status-success)]' : 'border-[var(--status-warning)] bg-[var(--status-warning)]/10 text-[var(--status-warning)]'}">
          <div class="flex items-center gap-2 font-hud font-bold">
            {#if reviewerDecision.is_approved}
              <CheckCircle class="w-4 h-4" />
              <span>QA AUDIT PASSED // SPECIFICATION APPROVED</span>
            {:else}
              <RotateCcw class="w-4 h-4 animate-spin-slow" />
              <span>QA AUDIT REVISION TRIGGERED // LOOPING BACK</span>
            {/if}
          </div>
          <div class="mt-1 text-[11px] opacity-90 leading-tight">
            {reviewerDecision.feedback}
          </div>
        </div>
      {/if}

      <!-- Terminal Component -->
      <TerminalLog
        entries={terminalLogs}
        currentStreamText={streamBuffer}
        activeAgent={activeAgentName}
      />
    </div>

    <!-- RIGHT PANEL (3 Cols): Output & Device Artifacts -->
    <div class="lg:col-span-3 space-y-4">
      <CyberCard code="OUTPUT.03" title="ARTIFACTS & OUTPUT">
        <!-- Tab Switcher -->
        <div class="flex border-b border-[var(--border-color)] mb-3 text-xs font-hud">
          <button
            type="button"
            onclick={() => activeTab = 'output'}
            class="flex-1 py-1.5 text-center transition-colors {activeTab === 'output' ? 'text-[var(--accent-primary)] border-b-2 border-[var(--accent-primary)] font-bold' : 'text-[var(--text-muted)] hover:text-white'}"
          >
            FINAL DRAFT
          </button>
          <button
            type="button"
            onclick={() => activeTab = 'artifacts'}
            class="flex-1 py-1.5 text-center transition-colors flex items-center justify-center gap-1 {activeTab === 'artifacts' ? 'text-[var(--accent-primary)] border-b-2 border-[var(--accent-primary)] font-bold' : 'text-[var(--text-muted)] hover:text-white'}"
          >
            <span>HARDWARE FILES</span>
            {#if generatedFiles.length > 0}
              <span class="w-4 h-4 rounded-full bg-[var(--accent-primary)] text-black text-[9px] font-bold flex items-center justify-center">
                {generatedFiles.length}
              </span>
            {/if}
          </button>
        </div>

        {#if activeTab === 'output'}
          <div class="prose prose-invert prose-xs max-h-[460px] overflow-y-auto font-code text-xs leading-relaxed text-[var(--text-primary)]">
            {#if renderedHtml}
              {@html renderedHtml}
            {:else}
              <div class="text-[var(--text-muted)] italic py-8 text-center">
                Output will render here once agents synthesize the blueprint...
              </div>
            {/if}
          </div>
        {:else}
          <!-- Hardware Artifacts Tab -->
          <div class="space-y-2 max-h-[460px] overflow-y-auto font-code text-xs">
            {#if generatedFiles.length === 0}
              <div class="text-[var(--text-muted)] italic py-8 text-center">
                No files materialized yet. Run pipeline with Document Fabricator tools enabled.
              </div>
            {/if}

            {#each generatedFiles as file}
              <div class="p-2.5 border border-[var(--accent-primary)]/40 bg-[var(--bg-elevated)]/50 rounded-sm space-y-1.5">
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-1.5 font-bold text-[var(--accent-primary)]">
                    <FileText class="w-3.5 h-3.5" />
                    <span class="truncate max-w-[140px]" title={file.filename}>{file.filename}</span>
                  </div>
                  <span class="text-[9px] px-1.5 py-0.2 rounded bg-[var(--status-success)]/20 text-[var(--status-success)] font-bold">
                    SYNCED
                  </span>
                </div>

                <div class="flex items-center justify-between text-[10px] text-[var(--text-muted)]">
                  <span>{file.size_bytes} bytes</span>
                  {#if file.content_base64}
                    <button
                      type="button"
                      onclick={() => deviceBridge.saveAgentFileToDevice(file.filename, file.content_base64, file.mime_type)}
                      class="text-[var(--accent-primary)] hover:underline flex items-center gap-0.5"
                    >
                      <Download class="w-3 h-3" />
                      Save Copy
                    </button>
                  {/if}
                </div>
              </div>
            {/each}
          </div>
        {/if}
      </CyberCard>
    </div>
  </div>

  <!-- Human In The Loop (HITL) Authorization Modal -->
  {#if pendingApproval}
    <div class="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div class="bg-[var(--bg-surface)] border-2 border-[var(--accent-warning, #f59e0b)] p-6 max-w-lg w-full relative cyber-chamfer-lg shadow-2xl space-y-4">
        <div class="flex items-center gap-3 border-b border-[var(--border-color)] pb-3">
          <ShieldAlert class="w-7 h-7 text-[var(--accent-warning, #f59e0b)] animate-pulse" />
          <div>
            <div class="text-[10px] font-code text-[var(--accent-warning, #f59e0b)] uppercase tracking-wider font-bold">
              HITL SECURITY GATE // ACTION REQUIRED
            </div>
            <h3 class="text-lg font-hud font-bold text-[var(--text-primary)]">
              AUTHORIZE HARDWARE ACCESS
            </h3>
          </div>
        </div>

        <div class="text-xs font-code space-y-2 text-[var(--text-secondary)]">
          <p>
            Agent <span class="text-[var(--accent-primary)] font-bold">{pendingApproval.agent_name}</span> is requesting permission to execute tool:
          </p>
          <div class="bg-[var(--bg-elevated)] p-3 border border-[var(--border-color)] rounded-sm space-y-1">
            <div class="text-[var(--accent-primary)] font-bold">{pendingApproval.tool_name}</div>
            <div class="text-[11px] text-[var(--text-muted)] break-all font-mono">
              {JSON.stringify(pendingApproval.tool_args, null, 2)}
            </div>
          </div>
          <p class="text-[11px] text-[var(--text-muted)] italic">
            Authorizing will grant write permission to persist the file onto your local disk / workspace.
          </p>
        </div>

        <div class="flex items-center justify-end gap-3 pt-3 border-t border-[var(--border-color)]">
          <CyberButton variant="danger" onclick={() => handleApproval(false)}>
            [REJECT & ABORT]
          </CyberButton>
          <CyberButton variant="primary" onclick={() => handleApproval(true)}>
            [AUTHORIZE WRITE]
          </CyberButton>
        </div>
      </div>
    </div>
  {/if}
</div>
