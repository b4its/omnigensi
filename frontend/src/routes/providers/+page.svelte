<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api';
  import { notify } from '$lib/stores/notify.svelte';
  import CyberCard from '$lib/components/ui/CyberCard.svelte';
  import CyberButton from '$lib/components/ui/CyberButton.svelte';
  import ProviderModelPanel from '$lib/components/providers/ProviderModelPanel.svelte';
  import {
    Server,
    Plus,
    RefreshCw,
    Key,
    Trash2,
    CheckCircle,
    XCircle,
    ExternalLink,
    Search,
    Cpu,
    Network,
    FolderTree,
    Terminal,
    Pencil,
    Power,
    Activity,
    Loader2,
    Play,
  } from 'lucide-svelte';

  let providers = $state<any[]>([]);
  let mcpServers = $state<any[]>([]);
  let loading = $state<boolean>(true);
  let showCreateModal = $state<boolean>(false);
  let editingProviderId = $state<string | null>(null);
  let syncLoading = $state<Record<string, boolean>>({});
  let testLoading = $state<Record<string, boolean>>({});
  let providerHealth = $state<
    Record<string, { ok: boolean; latency_ms: number; model_count: number; error?: string | null }>
  >({});
  let selectedProviderModels = $state<{ providerName: string; models: any[] } | null>(null);
  let selectedMcpTools = $state<{ serverName: string; tools: any[] } | null>(null);
  let mcpLoading = $state<Record<string, boolean>>({});
  let mcpToolRunning = $state<string | null>(null);
  let mcpToolResult = $state<{
    tool: string;
    ok: boolean;
    result?: any;
    error?: string | null;
  } | null>(null);
  let modelSearch = $state<string>('');
  let showMcpModal = $state<boolean>(false);
  let editingMcpName = $state<string | null>(null);
  let mcpBusy = $state<Record<string, boolean>>({});
  let mcpFormName = $state<string>('');
  let mcpFormType = $state<string>('stdio');
  let mcpFormCommand = $state<string>('');
  let mcpFormArgs = $state<string>('');
  let mcpFormUrl = $state<string>('');
  let mcpFormDescription = $state<string>('');
  let mcpFormError = $state<string>('');
  let mcpFormSubmitting = $state<boolean>(false);

  // Form State
  let formName = $state<string>('');
  let formType = $state<string>('openrouter');
  let formBaseUrl = $state<string>('https://openrouter.ai/api/v1');
  let formApiKey = $state<string>('');
  let formApiKeyTouched = $state<boolean>(false);
  let formIsActive = $state<boolean>(true);
  let formDefaultModel = $state<string | null>(null);
  let autoSyncOnSave = $state<boolean>(true);
  let formError = $state<string>('');
  let formSubmitting = $state<boolean>(false);

  async function loadProviders() {
    try {
      loading = true;
      const [pr, mcp] = await Promise.all([
        api.getProviders(),
        api.getMCPServers().catch(() => []),
      ]);
      providers = pr;
      mcpServers = mcp;
    } catch (e: any) {
      console.error(e);
    } finally {
      loading = false;
    }
  }

  /** Executes one discovered MCP tool with JSON arguments to prove it works. */
  async function handleRunMcpTool(serverName: string, tool: any) {
    let args: Record<string, any> = {};
    const props = tool.input_schema?.properties;
    if (props && Object.keys(props).length > 0) {
      const entered = prompt(
        `Arguments for ${tool.name} as JSON:`,
        JSON.stringify(Object.fromEntries(Object.keys(props).map((k) => [k, ''])), null, 2)
      );
      if (entered === null) return;
      try {
        args = JSON.parse(entered);
      } catch {
        notify.error('Arguments must be valid JSON');
        return;
      }
    }

    mcpToolRunning = tool.name;
    mcpToolResult = null;
    try {
      const res = await api.executeMCPTool(serverName, tool.name, args);
      mcpToolResult = {
        tool: tool.name,
        ok: res.status === 'success',
        result: res.result,
        error: res.message
      };
      if (res.status === 'success') notify.success(`${tool.name} executed`);
      else notify.error(`${tool.name} failed: ${res.message ?? 'unknown error'}`);
    } catch (err) {
      notify.fromError(err, 'MCP tool execution failed');
    } finally {
      mcpToolRunning = null;
    }
  }

  async function handleInspectMcpTools(server: any) {
    mcpLoading[server.name] = true;
    try {
      const res = await api.getMCPServerTools(server.name);
      selectedMcpTools = {
        serverName: server.name,
        tools: res.tools || [],
      };
    } catch (e: any) {
      notify.fromError(e, "Failed to fetch MCP tools");
    } finally {
      mcpLoading[server.name] = false;
    }
  }

  function openMcpModal() {
    editingMcpName = null;
    mcpFormName = '';
    mcpFormType = 'stdio';
    mcpFormCommand = '';
    mcpFormArgs = '';
    mcpFormUrl = '';
    mcpFormDescription = '';
    mcpFormError = '';
    showMcpModal = true;
  }

  function openMcpEditModal(server: any) {
    editingMcpName = server.name;
    mcpFormName = server.name;
    mcpFormType = server.server_type ?? 'stdio';
    mcpFormCommand = server.command ?? '';
    mcpFormArgs = (server.args || []).join(' ');
    mcpFormUrl = server.url ?? '';
    mcpFormDescription = server.description ?? '';
    mcpFormError = '';
    showMcpModal = true;
  }

  async function handleSaveMcp(e: SubmitEvent) {
    e.preventDefault();
    if (!editingMcpName && !mcpFormName.trim()) {
      mcpFormError = 'Server name is required.';
      return;
    }
    if (mcpFormType === 'stdio' && !mcpFormCommand.trim()) {
      mcpFormError = 'A command is required for stdio transport.';
      return;
    }
    if (mcpFormType === 'sse' && !mcpFormUrl.trim()) {
      mcpFormError = 'A URL is required for SSE transport.';
      return;
    }
    mcpFormSubmitting = true;
    mcpFormError = '';
    try {
      const shared = {
        server_type: mcpFormType,
        command: mcpFormType === 'stdio' ? mcpFormCommand.trim() : null,
        args: mcpFormArgs.trim() ? mcpFormArgs.trim().split(/\s+/) : [],
        url: mcpFormType === 'sse' ? mcpFormUrl.trim() : null,
        description: mcpFormDescription.trim() || 'Model Context Protocol Server Bridge',
      };
      if (editingMcpName) {
        await api.updateMCPServer(editingMcpName, shared);
      } else {
        await api.registerMCPServer({
          name: mcpFormName.trim(),
          ...shared,
          enabled: true,
        });
      }
      showMcpModal = false;
      editingMcpName = null;
      await loadProviders();
    } catch (err: any) {
      mcpFormError = err.message || 'Failed to save MCP server';
    } finally {
      mcpFormSubmitting = false;
    }
  }

  async function handleToggleMcp(server: any) {
    mcpBusy[server.name] = true;
    try {
      await api.toggleMCPServer(server.name, !server.enabled);
      await loadProviders();
    } catch (err: any) {
      notify.fromError(err, "Toggle failed");
    } finally {
      mcpBusy[server.name] = false;
    }
  }

  async function handleDeleteMcp(server: any) {
    const confirmed = await notify.confirm({
      title: 'REMOVE MCP SERVER',
      message: `Remove MCP server '${server.name}'? Its configuration and cached tools will be dropped.`,
      confirmLabel: 'REMOVE',
    });
    if (!confirmed) return;
    mcpBusy[server.name] = true;
    try {
      await api.deleteMCPServer(server.name);
      await loadProviders();
    } catch (err: any) {
      notify.fromError(err, "Delete failed");
    } finally {
      mcpBusy[server.name] = false;
    }
  }

  onMount(loadProviders);

  function resetProviderForm() {
    editingProviderId = null;
    formName = '';
    formType = 'openrouter';
    formBaseUrl = 'https://openrouter.ai/api/v1';
    formApiKey = '';
    formApiKeyTouched = false;
    formIsActive = true;
    formDefaultModel = null;
    formError = '';
  }

  function openCreateModal() {
    resetProviderForm();
    showCreateModal = true;
  }

  function openEditModal(provider: any) {
    editingProviderId = provider.id;
    formName = provider.name ?? '';
    formType = provider.provider_type ?? 'custom';
    formBaseUrl = provider.base_url ?? '';
    formApiKey = '';
    formApiKeyTouched = false;
    formIsActive = provider.is_active ?? true;
    formDefaultModel = provider.default_model ?? null;
    formError = '';
    showCreateModal = true;
  }

  async function handleSaveProvider(e: SubmitEvent) {
    e.preventDefault();
    if (!formName.trim() || !formBaseUrl.trim()) {
      formError = 'Please fill in Name and Base URL.';
      return;
    }

    formSubmitting = true;
    formError = '';
    try {
      if (editingProviderId) {
        // Only send the API key when the operator actually typed a new one,
        // otherwise the existing encrypted key would be overwritten.
        const payload: Record<string, any> = {
          name: formName,
          provider_type: formType,
          base_url: formBaseUrl,
          is_active: formIsActive,
        };
        if (formApiKeyTouched && formApiKey.trim()) {
          payload.api_key = formApiKey;
        }
        if (formDefaultModel) {
          payload.default_model = formDefaultModel;
        }
        await api.updateProvider(editingProviderId, payload);
        notify.success('Provider updated');
      } else {
        const created = await api.createProvider(
          {
            name: formName,
            provider_type: formType,
            base_url: formBaseUrl,
            api_key: formApiKey,
            default_headers: {},
            is_active: formIsActive,
            default_model: formDefaultModel,
          },
          autoSyncOnSave
        );
        if (autoSyncOnSave) {
          const count = created?.default_model ? ' with a default model' : '';
          notify.success(`Provider registered${count}`);
        } else {
          notify.success('Provider registered');
        }
      }
      showCreateModal = false;
      resetProviderForm();
      await loadProviders();
    } catch (err: any) {
      formError = err.message || 'Failed to save provider';
    } finally {
      formSubmitting = false;
    }
  }

  async function handleToggleProviderActive(provider: any) {
    try {
      await api.updateProvider(provider.id, { is_active: !provider.is_active });
      await loadProviders();
    } catch (err: any) {
      notify.fromError(err, "Toggle failed");
    }
  }

  async function handleDeleteProvider(id: string, name: string) {
    const confirmed = await notify.confirm({
      title: 'DELETE PROVIDER',
      message: `Delete provider '${name}'? Agents using it will lose their model source.`,
      confirmLabel: 'DELETE',
    });
    if (!confirmed) return;
    try {
      await api.deleteProvider(id);
      await loadProviders();
    } catch (err: any) {
      notify.fromError(err, "Delete failed");
    }
  }

  /** Actively probe the provider; /models cannot be trusted for this. */
  async function handleTestProvider(provider: any) {
    testLoading[provider.id] = true;
    try {
      const res = await api.testProvider(provider.id);
      providerHealth[provider.id] = {
        ok: res.ok,
        latency_ms: res.latency_ms,
        model_count: res.model_count,
        error: res.error,
      };
      if (res.ok) {
        notify.success(
          `${provider.name}: OK - ${res.model_count} models in ${res.latency_ms}ms`
        );
      } else {
        notify.error(`${provider.name}: ${res.error ?? 'Connection failed'}`);
      }
    } catch (err) {
      notify.fromError(err, 'Connection test failed');
    } finally {
      testLoading[provider.id] = false;
    }
  }

  async function handleSyncModels(provider: any) {
    syncLoading[provider.id] = true;
    try {
      const models = await api.getProviderModels(provider.id);
      selectedProviderModels = {
        providerName: provider.name,
        models,
      };
    } catch (err: any) {
      notify.fromError(err, "Failed to fetch models");
    } finally {
      syncLoading[provider.id] = false;
    }
  }

  const filteredModels = $derived(
    selectedProviderModels?.models.filter(m =>
      m.id.toLowerCase().includes(modelSearch.toLowerCase()) ||
      (m.name && m.name.toLowerCase().includes(modelSearch.toLowerCase()))
    ) || []
  );
</script>

<div class="space-y-6">
  <!-- Header Bar -->
  <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-[var(--border-color)] pb-4">
    <div>
      <div class="text-[11px] font-code text-[var(--accent-primary)] uppercase tracking-wider">
        MODULE // 02
      </div>
      <h1 class="text-xl md:text-2xl font-hud font-black text-[var(--text-primary)]">
        OMNIROUTER & LLM PROVIDER VAULT
      </h1>
      <p class="text-xs text-[var(--text-muted)] mt-1">
        Manage unified LLM gateways with hardware AES API key encryption and dynamic model discovery.
      </p>
    </div>

    <CyberButton variant="primary" onclick={openCreateModal}>
      <Plus class="w-4 h-4" />
      <span>REGISTER PROVIDER</span>
    </CyberButton>
  </div>

  <!-- Provider List -->
  {#if loading}
    <div class="text-center py-12 font-code text-xs text-[var(--text-muted)] animate-pulse">
      SCANNING LLM GATEWAY VAULTS...
    </div>
  {:else if providers.length === 0}
    <div class="border border-dashed border-[var(--border-color)] p-8 text-center chamfer space-y-3">
      <Server class="w-10 h-10 mx-auto text-[var(--text-muted)] opacity-50" />
      <div class="font-hud font-bold text-sm text-[var(--text-primary)]">NO PROVIDERS REGISTERED</div>
      <p class="text-xs text-[var(--text-muted)] max-w-md mx-auto">
        Add your first provider (OpenRouter, LiteLLM, OpenAI, or local Ollama) to start powering dynamic agents.
      </p>
      <CyberButton variant="primary" size="sm" onclick={openCreateModal}>
        REGISTER NEW PROVIDER
      </CyberButton>
    </div>
  {:else}
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      {#each providers as prov (prov.id)}
        <CyberCard code={`VAULT.${prov.provider_type.toUpperCase()}`} title={prov.name}>
          <div class="space-y-3">
            <div class="flex items-center justify-between text-xs">
              <span class="text-[var(--text-muted)]">Type:</span>
              <span class="font-code font-bold uppercase text-[var(--accent-primary)]">
                {prov.provider_type}
              </span>
            </div>

            <div class="flex items-center justify-between text-xs">
              <span class="text-[var(--text-muted)]">Base URL:</span>
              <span class="font-code text-[var(--text-primary)] truncate max-w-[220px]" title={prov.base_url}>
                {prov.base_url}
              </span>
            </div>

            <div class="flex items-center justify-between text-xs">
              <span class="text-[var(--text-muted)]">Key Status:</span>
              <span class="flex items-center gap-1 font-code {prov.has_api_key ? 'text-[var(--status-success)]' : 'text-[var(--text-muted)]'}">
                <Key class="w-3.5 h-3.5" />
                {prov.has_api_key ? 'ENCRYPTED (AES-256)' : 'EMPTY / LOCAL'}
              </span>
            </div>

            <div class="flex items-center justify-between text-xs">
              <span class="text-[var(--text-muted)]">Status:</span>
              <span class="font-code font-bold px-1.5 py-0.5 rounded uppercase text-[10px] {prov.is_active ? 'bg-[var(--status-success)]/20 text-[var(--status-success)]' : 'bg-[var(--text-muted)]/20 text-[var(--text-muted)]'}">
                {prov.is_active ? 'ACTIVE' : 'INACTIVE'}
              </span>
            </div>

            {#if providerHealth[prov.id]}
              <div class="flex items-center justify-between text-xs">
                <span class="text-[var(--text-muted)]">Connectivity:</span>
                <span
                  class="font-code font-bold text-[10px] {providerHealth[prov.id].ok
                    ? 'text-[var(--status-success)]'
                    : 'text-[var(--status-danger)]'}"
                  title={providerHealth[prov.id].error ?? ''}
                >
                  {providerHealth[prov.id].ok
                    ? `REACHABLE · ${providerHealth[prov.id].latency_ms}ms`
                    : 'UNREACHABLE'}
                </span>
              </div>
            {/if}

            <div class="pt-3 border-t border-[var(--border-color)]/40 flex items-center justify-between gap-2">
              <div class="flex items-center gap-1.5">
                <button
                  type="button"
                  disabled={syncLoading[prov.id]}
                  onclick={() => handleSyncModels(prov)}
                  class="inline-flex items-center gap-1.5 px-3 py-2 text-[11px] font-hud text-[var(--accent-primary)] border border-[var(--accent-primary)]/40 hover:bg-[var(--accent-primary)]/10 chamfer-sm transition-colors cursor-pointer disabled:opacity-50"
                >
                  <RefreshCw class="w-3.5 h-3.5 {syncLoading[prov.id] ? 'animate-spin' : ''}" />
                  <span>{syncLoading[prov.id] ? 'SYNCING...' : 'SYNC MODELS'}</span>
                </button>

                <button
                  type="button"
                  disabled={testLoading[prov.id]}
                  onclick={() => handleTestProvider(prov)}
                  title="Actively verify credentials and reachability"
                  class="inline-flex items-center gap-1.5 px-3 py-2 text-[11px] font-hud border chamfer-sm transition-colors cursor-pointer disabled:opacity-50 {providerHealth[prov.id]?.ok === true
                    ? 'border-[var(--status-success)]/50 text-[var(--status-success)]'
                    : providerHealth[prov.id]?.ok === false
                      ? 'border-[var(--status-danger)]/50 text-[var(--status-danger)]'
                      : 'border-[var(--border-color)] text-[var(--text-muted)] hover:text-[var(--text-primary)]'}"
                >
                  <Activity class="w-3.5 h-3.5 {testLoading[prov.id] ? 'animate-pulse' : ''}" />
                  <span>{testLoading[prov.id] ? 'TESTING...' : 'TEST'}</span>
                </button>
              </div>

              <div class="flex items-center gap-1">
                <button
                  type="button"
                  onclick={() => handleToggleProviderActive(prov)}
                  class="p-2 rounded transition-colors cursor-pointer {prov.is_active ? 'text-[var(--status-success)] hover:bg-[var(--status-success)]/10' : 'text-[var(--text-muted)] hover:bg-[var(--bg-elevated)]'}"
                  title={prov.is_active ? 'Deactivate provider' : 'Activate provider'}
                  aria-label={prov.is_active ? 'Deactivate provider' : 'Activate provider'}
                >
                  <Power class="w-4 h-4" />
                </button>

                <button
                  type="button"
                  onclick={() => openEditModal(prov)}
                  class="p-2 text-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/10 rounded transition-colors cursor-pointer"
                  title="Edit provider"
                  aria-label="Edit provider"
                >
                  <Pencil class="w-4 h-4" />
                </button>

                <button
                  type="button"
                  onclick={() => handleDeleteProvider(prov.id, prov.name)}
                  class="p-2 text-[var(--status-danger)] hover:bg-[var(--status-danger)]/10 rounded transition-colors cursor-pointer"
                  title="Delete provider"
                  aria-label="Delete provider"
                >
                  <Trash2 class="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </CyberCard>
      {/each}
    </div>
  {/if}

  <!-- MCP (Model Context Protocol) Servers Section -->
  <div class="mt-8 space-y-4">
    <div class="flex items-center justify-between border-b border-[var(--border-color)] pb-3">
      <div>
        <div class="text-[11px] font-code text-[var(--accent-primary)] uppercase tracking-wider">
          SUB-PROTOCOL // 02
        </div>
        <h2 class="text-lg font-hud font-bold text-[var(--text-primary)] flex items-center gap-2">
          <Network class="w-5 h-5 text-[var(--accent-primary)]" />
          MODEL CONTEXT PROTOCOL (MCP) // HOST BRIDGES
        </h2>
        <p class="text-xs text-[var(--text-muted)] mt-0.5">
          Connect local MCP servers over stdio or SSE to grant agents access to host tools and graph memory.
        </p>
      </div>

      <div class="flex flex-col sm:flex-row items-start sm:items-center gap-2">
        <span class="text-xs font-code px-2.5 py-1 rounded border border-[var(--status-success)]/40 bg-[var(--status-success)]/10 text-[var(--status-success)] font-bold">
          MCP SDK v2.3 ACTIVE
        </span>
        <CyberButton variant="outline" size="sm" onclick={openMcpModal}>
          <Plus class="w-3.5 h-3.5" />
          <span>REGISTER MCP SERVER</span>
        </CyberButton>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      {#each mcpServers as server}
        <CyberCard code="MCP.BRIDGE" title={server.name.toUpperCase()}>
          <div class="space-y-3 font-code text-xs">
            <div class="flex items-center justify-between">
              <span class="text-[var(--text-muted)]">Transport:</span>
              <span class="px-2 py-0.5 rounded uppercase font-bold text-[10px] bg-[var(--accent-primary)]/20 text-[var(--accent-primary)] border border-[var(--accent-primary)]/30">
                {server.server_type}
              </span>
            </div>

            <div class="p-2.5 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm space-y-1">
              <div class="text-[10px] text-[var(--text-muted)] flex items-center gap-1 font-bold">
                <Terminal class="w-3 h-3 text-[var(--accent-primary)]" />
                EXECUTION COMMAND:
              </div>
              <div class="text-[11px] text-[var(--text-primary)] font-mono truncate">
                {server.command} {(server.args || []).join(' ')}
              </div>
            </div>

            <p class="text-[11px] text-[var(--text-muted)] line-clamp-2">
              {server.description || 'Model Context Protocol Server Adapter'}
            </p>

            <div class="pt-2 border-t border-[var(--border-color)]/50 flex flex-wrap items-center justify-between gap-2">
              <span class="text-[10px] font-bold flex items-center gap-1 {server.enabled ? 'text-[var(--status-success)]' : 'text-[var(--text-muted)]'}">
                <span class="w-2 h-2 rounded-full inline-block {server.enabled ? 'bg-[var(--status-success)]' : 'bg-[var(--text-muted)]'}"></span>
                {server.enabled ? 'ACTIVE PROTOCOL' : 'DISABLED'}
              </span>

              <div class="flex items-center gap-1">
                <button
                  type="button"
                  onclick={() => handleInspectMcpTools(server)}
                  disabled={mcpLoading[server.name] || !server.enabled}
                  title={server.enabled ? 'Discover tools' : 'Enable the server to discover tools'}
                  class="px-2.5 py-1.5 text-xs font-hud border border-[var(--accent-primary)] text-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/10 rounded-none transition-colors flex items-center gap-1 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <RefreshCw class="w-3 h-3 {mcpLoading[server.name] ? 'animate-spin' : ''}" />
                  <span>{mcpLoading[server.name] ? 'INSPECTING...' : 'DISCOVER TOOLS'}</span>
                </button>

                <button
                  type="button"
                  onclick={() => handleToggleMcp(server)}
                  disabled={mcpBusy[server.name]}
                  class="p-2 rounded transition-colors cursor-pointer disabled:opacity-50 {server.enabled ? 'text-[var(--status-success)] hover:bg-[var(--status-success)]/10' : 'text-[var(--text-muted)] hover:bg-[var(--bg-elevated)]'}"
                  title={server.enabled ? 'Disable server' : 'Enable server'}
                  aria-label={server.enabled ? `Disable ${server.name}` : `Enable ${server.name}`}
                >
                  <Power class="w-4 h-4" />
                </button>

                <button
                  type="button"
                  onclick={() => openMcpEditModal(server)}
                  disabled={mcpBusy[server.name]}
                  class="p-2 text-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/10 rounded transition-colors cursor-pointer disabled:opacity-50"
                  title="Edit server configuration"
                  aria-label={`Edit ${server.name}`}
                >
                  <Pencil class="w-4 h-4" />
                </button>

                <button
                  type="button"
                  onclick={() => handleDeleteMcp(server)}
                  disabled={mcpBusy[server.name]}
                  class="p-2 text-[var(--status-danger)] hover:bg-[var(--status-danger)]/10 rounded transition-colors cursor-pointer disabled:opacity-50"
                  title="Remove server"
                  aria-label={`Remove ${server.name}`}
                >
                  <Trash2 class="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </CyberCard>
      {/each}
    </div>
  </div>

  <!-- Create Modal -->
  {#if showCreateModal}
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div class="w-full max-w-lg max-h-[92dvh] overflow-y-auto border border-[var(--accent-primary)] bg-[var(--bg-surface)] p-4 sm:p-6 chamfer shadow-[var(--border-glow)] space-y-4">
        <div class="flex items-center justify-between border-b border-[var(--border-color)] pb-3">
          <div class="font-hud font-bold text-sm text-[var(--text-primary)]">
            {editingProviderId ? 'EDIT LLM GATEWAY' : 'REGISTER NEW LLM GATEWAY'}
          </div>
          <button
            type="button"
            onclick={() => showCreateModal = false}
            class="p-2 text-[var(--text-muted)] hover:text-[var(--text-primary)] text-xs font-hud"
          >
            [CLOSE]
          </button>
        </div>

        {#if formError}
          <div class="p-2.5 text-xs font-code text-[var(--status-danger)] bg-[var(--status-danger)]/10 border border-[var(--status-danger)]">
            {formError}
          </div>
        {/if}

        <form onsubmit={handleSaveProvider} class="space-y-4 text-xs font-code">
          <div>
            <label class="block text-[var(--text-muted)] mb-1">
              <span>Provider Label / Name</span>
              <input
                type="text"
                bind:value={formName}
                placeholder="e.g. OpenRouter Gateway"
                class="w-full mt-1 px-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
                required
              />
            </label>
          </div>

          <div>
            <label class="block text-[var(--text-muted)] mb-1">
              <span>Provider Type</span>
              <select
                bind:value={formType}
                onchange={() => {
                  if (formType === 'openrouter') formBaseUrl = 'https://openrouter.ai/api/v1';
                  else if (formType === 'ollama') formBaseUrl = 'http://localhost:11434';
                  else if (formType === 'openai') formBaseUrl = 'https://api.openai.com/v1';
                }}
                class="w-full mt-1 px-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
              >
                <option value="openrouter">OpenRouter (Omnigateway)</option>
                <option value="litellm">LiteLLM Proxy</option>
                <option value="openai">OpenAI Official</option>
                <option value="ollama">Local Ollama / vLLM</option>
                <option value="custom">Custom Compatible API</option>
              </select>
            </label>
          </div>

          <div>
            <label class="block text-[var(--text-muted)] mb-1">
              <span>Base URL</span>
              <input
                type="text"
                bind:value={formBaseUrl}
                placeholder="e.g. https://openrouter.ai/api/v1"
                class="w-full mt-1 px-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
                required
              />
            </label>
          </div>

          <div>
            <label class="block text-[var(--text-muted)] mb-1">
              <span>API Key (Encrypted in DB)</span>
              <input
                type="password"
                bind:value={formApiKey}
                oninput={() => (formApiKeyTouched = true)}
                placeholder={editingProviderId ? '•••••••• (leave blank to keep current)' : 'sk-...'}
                class="w-full mt-1 px-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
              />
            </label>
            <span class="text-[10px] text-[var(--text-muted)] mt-1 block">
              {#if editingProviderId}
                Leave blank to keep the existing encrypted key.
              {:else}
                Leave blank if running local Ollama without auth.
              {/if}
            </span>
          </div>

          <div>
            <label class="flex items-center gap-2 text-[var(--text-muted)] cursor-pointer select-none">
              <input type="checkbox" bind:checked={formIsActive} class="accent-[var(--accent-primary)] w-4 h-4" />
              <span>Provider active (available to agents)</span>
            </label>
          </div>

          <!-- Model workspace: auto-add models, pick one, test a real reply -->
          <div class="pt-3 border-t border-[var(--border-color)]">
            <ProviderModelPanel
              providerId={editingProviderId}
              draftBaseUrl={formBaseUrl}
              draftApiKey={formApiKey}
              draftProviderType={formType}
              selectedModelId={formDefaultModel}
              onDefaultModelChange={(id) => (formDefaultModel = id)}
            />
          </div>

          {#if !editingProviderId}
            <div>
              <label class="flex items-start gap-2 text-[var(--text-muted)] cursor-pointer select-none">
                <input type="checkbox" bind:checked={autoSyncOnSave} class="accent-[var(--accent-primary)] w-4 h-4 mt-0.5" />
                <span>
                  Auto-add models on save
                  <span class="block text-[10px] opacity-75">
                    Discovers and stores the provider's model list immediately after registering.
                  </span>
                </span>
              </label>
            </div>
          {/if}

          <div class="pt-3 border-t border-[var(--border-color)] flex items-center justify-between gap-2">
            <span class="text-[10px] text-[var(--text-muted)] truncate">
              {#if formDefaultModel}
                Model: <span class="text-[var(--accent-primary)]">{formDefaultModel}</span>
              {:else}
                No model selected
              {/if}
            </span>
            <div class="flex gap-2 shrink-0">
              <CyberButton variant="ghost" size="sm" type="button" onclick={() => showCreateModal = false}>
                CANCEL
              </CyberButton>
              <CyberButton variant="primary" size="sm" type="submit" disabled={formSubmitting}>
                {formSubmitting ? 'SAVING...' : editingProviderId ? 'SAVE CHANGES' : 'ENCRYPT & SAVE'}
              </CyberButton>
            </div>
          </div>
        </form>
      </div>
    </div>
  {/if}

  <!-- Models List Modal / Drawer -->
  {#if selectedProviderModels}
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
      <div class="w-full max-w-2xl max-h-[80vh] flex flex-col border border-[var(--accent-primary)] bg-[var(--bg-surface)] chamfer shadow-[var(--border-glow)] overflow-hidden">
        <div class="flex items-center justify-between p-4 border-b border-[var(--border-color)] bg-[var(--bg-elevated)]/60">
          <div>
            <div class="font-hud font-bold text-sm text-[var(--text-primary)]">
              AVAILABLE MODELS // {selectedProviderModels.providerName}
            </div>
            <div class="text-[10px] text-[var(--text-muted)] font-code">
              {selectedProviderModels.models.length} models discovered via /models endpoint
            </div>
          </div>
          <button
            type="button"
            onclick={() => selectedProviderModels = null}
            class="text-xs font-hud text-[var(--text-muted)] hover:text-[var(--text-primary)]"
          >
            [CLOSE]
          </button>
        </div>

        <!-- Search Bar -->
        <div class="p-3 border-b border-[var(--border-color)] bg-[var(--bg-surface)]">
          <div class="relative">
            <Search class="w-4 h-4 absolute left-3 top-2.5 text-[var(--text-muted)]" />
            <input
              type="text"
              bind:value={modelSearch}
              placeholder="Filter models by id or name..."
              class="w-full pl-9 pr-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-xs font-code text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
            />
          </div>
        </div>

        <div class="flex-1 p-4 overflow-y-auto space-y-2">
          {#each filteredModels as model}
            <div class="border border-[var(--border-color)]/60 bg-[var(--bg-elevated)]/40 p-2.5 rounded-sm flex items-center justify-between font-code text-xs">
              <div>
                <div class="font-bold text-[var(--text-primary)]">{model.id}</div>
                {#if model.name && model.name !== model.id}
                  <div class="text-[10px] text-[var(--text-muted)]">{model.name}</div>
                {/if}
              </div>
              {#if model.context_length}
                <span class="text-[10px] text-[var(--accent-primary)] px-2 py-0.5 rounded bg-[var(--accent-primary)]/10">
                  {Math.round(model.context_length / 1000)}k ctx
                </span>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    </div>
  {/if}

  <!-- MCP Tools Inspection Modal -->
  {#if selectedMcpTools}
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
      <div class="w-full max-w-2xl max-h-[80vh] flex flex-col border border-[var(--accent-primary)] bg-[var(--bg-surface)] chamfer shadow-[var(--border-glow)] overflow-hidden">
        <div class="flex items-center justify-between p-4 border-b border-[var(--border-color)] bg-[var(--bg-elevated)]/60">
          <div>
            <div class="font-hud font-bold text-sm text-[var(--text-primary)]">
              DISCOVERED MCP TOOLS // {selectedMcpTools.serverName}
            </div>
            <div class="text-[10px] text-[var(--text-muted)] font-code">
              {selectedMcpTools.tools.length} tools registered via Model Context Protocol
            </div>
          </div>
          <button
            type="button"
            onclick={() => selectedMcpTools = null}
            class="text-xs font-hud text-[var(--text-muted)] hover:text-[var(--text-primary)]"
          >
            [CLOSE]
          </button>
        </div>

        <div class="p-4 overflow-y-auto space-y-3 font-code text-xs">
          {#each selectedMcpTools.tools as tool}
            <div class="p-3 border border-[var(--border-color)] bg-[var(--bg-elevated)]/40 rounded-sm space-y-1.5">
              <div class="flex items-center justify-between gap-2">
                <span class="font-bold text-[var(--accent-primary)] text-sm break-all">{tool.name}</span>
                <button
                  type="button"
                  onclick={() => selectedMcpTools && handleRunMcpTool(selectedMcpTools.serverName, tool)}
                  disabled={mcpToolRunning === tool.name}
                  class="shrink-0 inline-flex items-center gap-1 px-2.5 py-2 text-[10px] font-hud border border-[var(--status-success)]/50 text-[var(--status-success)] hover:bg-[var(--status-success)]/10 chamfer-sm disabled:opacity-40"
                >
                  {#if mcpToolRunning === tool.name}
                    <Loader2 class="w-3 h-3 animate-spin" />
                    <span>RUNNING...</span>
                  {:else}
                    <Play class="w-3 h-3" />
                    <span>RUN</span>
                  {/if}
                </button>
              </div>
              <p class="text-[11px] text-[var(--text-muted)]">{tool.description}</p>
              {#if tool.input_schema?.properties}
                <div class="text-[10px] text-[var(--text-secondary)] mt-1 pt-1 border-t border-[var(--border-color)]/40 font-mono">
                  Args: {Object.keys(tool.input_schema.properties).join(', ')}
                </div>
              {/if}

              {#if mcpToolResult && mcpToolResult.tool === tool.name}
                <div class="mt-1 border chamfer-sm px-2 py-1.5 {mcpToolResult.ok
                  ? 'border-[var(--status-success)]/50 bg-[var(--status-success)]/10'
                  : 'border-[var(--status-danger)]/50 bg-[var(--status-danger)]/10'}">
                  <div class="text-[10px] font-bold {mcpToolResult.ok ? 'text-[var(--status-success)]' : 'text-[var(--status-danger)]'}">
                    {mcpToolResult.ok ? 'RESULT' : 'FAILED'}
                  </div>
                  <pre class="text-[10px] text-[var(--text-primary)] whitespace-pre-wrap break-words max-h-32 overflow-y-auto mt-1">{mcpToolResult.ok
                    ? JSON.stringify(mcpToolResult.result, null, 2)
                    : mcpToolResult.error}</pre>
                </div>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    </div>
  {/if}

  <!-- Register MCP Server Modal -->
  {#if showMcpModal}
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div class="w-full max-w-lg border border-[var(--accent-primary)] bg-[var(--bg-surface)] p-6 chamfer shadow-[var(--border-glow)] space-y-4">
        <div class="flex items-center justify-between border-b border-[var(--border-color)] pb-3">
          <div class="font-hud font-bold text-sm text-[var(--text-primary)]">
            {editingMcpName ? 'EDIT MCP SERVER' : 'REGISTER NEW MCP SERVER'}
          </div>
          <button
            type="button"
            onclick={() => showMcpModal = false}
            class="p-2 text-[var(--text-muted)] hover:text-[var(--text-primary)] text-xs font-hud"
          >
            [CLOSE]
          </button>
        </div>

        {#if mcpFormError}
          <div class="p-2.5 text-xs font-code text-[var(--status-danger)] bg-[var(--status-danger)]/10 border border-[var(--status-danger)]">
            {mcpFormError}
          </div>
        {/if}

        <form onsubmit={handleSaveMcp} class="space-y-4 text-xs font-code">
          <div>
            <label class="block text-[var(--text-muted)] mb-1">
              <span>Server Name</span>
              <input
                type="text"
                bind:value={mcpFormName}
                placeholder="e.g. postgres-mcp"
                disabled={!!editingMcpName}
                class="w-full mt-1 px-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)] disabled:opacity-60 disabled:cursor-not-allowed"
                required
              />
            </label>
            {#if editingMcpName}
              <span class="text-[10px] text-[var(--text-muted)] mt-1 block">
                Server name is immutable; remove and re-add to rename.
              </span>
            {/if}
          </div>

          <div>
            <label class="block text-[var(--text-muted)] mb-1">
              <span>Transport Protocol</span>
              <select
                bind:value={mcpFormType}
                class="w-full mt-1 px-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
              >
                <option value="stdio">stdio (local subprocess)</option>
                <option value="sse">SSE (remote HTTP endpoint)</option>
              </select>
            </label>
          </div>

          {#if mcpFormType === 'stdio'}
            <div>
              <label class="block text-[var(--text-muted)] mb-1">
                <span>Command</span>
                <input
                  type="text"
                  bind:value={mcpFormCommand}
                  placeholder="npx"
                  class="w-full mt-1 px-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
                />
              </label>
            </div>
            <div>
              <label class="block text-[var(--text-muted)] mb-1">
                <span>Arguments (space separated)</span>
                <input
                  type="text"
                  bind:value={mcpFormArgs}
                  placeholder="-y @modelcontextprotocol/server-postgres"
                  class="w-full mt-1 px-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
                />
              </label>
            </div>
          {:else}
            <div>
              <label class="block text-[var(--text-muted)] mb-1">
                <span>SSE URL</span>
                <input
                  type="url"
                  bind:value={mcpFormUrl}
                  placeholder="http://localhost:9000/sse"
                  class="w-full mt-1 px-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
                />
              </label>
            </div>
          {/if}

          <div>
            <label class="block text-[var(--text-muted)] mb-1">
              <span>Description (optional)</span>
              <input
                type="text"
                bind:value={mcpFormDescription}
                placeholder="Grants agents access to the analytics database"
                class="w-full mt-1 px-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
              />
            </label>
          </div>

          <div class="pt-3 border-t border-[var(--border-color)] flex justify-end gap-2">
            <CyberButton variant="ghost" size="sm" type="button" onclick={() => showMcpModal = false}>
              CANCEL
            </CyberButton>
            <CyberButton variant="primary" size="sm" type="submit" disabled={mcpFormSubmitting}>
              {mcpFormSubmitting ? 'SAVING...' : editingMcpName ? 'SAVE CHANGES' : 'REGISTER SERVER'}
            </CyberButton>
          </div>
        </form>
      </div>
    </div>
  {/if}
</div>
