<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api';
  import CyberCard from '$lib/components/ui/CyberCard.svelte';
  import CyberButton from '$lib/components/ui/CyberButton.svelte';
  import {
    Bot,
    Plus,
    Edit3,
    Trash2,
    Shield,
    HardDrive,
    FileText,
    FileCode,
    Cpu,
    Search,
    Sliders,
    Sparkles,
    Check,
  } from 'lucide-svelte';

  let agents = $state<any[]>([]);
  let providers = $state<any[]>([]);
  let availableTools = $state<any[]>([]);
  let loading = $state<boolean>(true);

  // Modal / Drawer state
  let showModal = $state<boolean>(false);
  let isEditing = $state<boolean>(false);
  let editId = $state<string | null>(null);

  // Form state
  let formName = $state<string>('');
  let formAvatar = $state<string>('cyber-bot-01');
  let formRole = $state<string>('');
  let formGoal = $state<string>('');
  let formBackstory = $state<string>('');
  let formNodeType = $state<'worker' | 'reviewer' | 'supervisor'>('worker');
  let formProviderId = $state<string>('');
  let formModelName = $state<string>('meta-llama/llama-3.3-70b-instruct');
  let formTemperature = $state<number>(0.7);
  let formMaxTokens = $state<number>(4096);
  let formTools = $state<string[]>([]);
  let formApproval = $state<boolean>(false);
  let formError = $state<string>('');
  let formSubmitting = $state<boolean>(false);

  // Dynamic models for selected provider in form
  let providerModels = $state<any[]>([]);
  let loadingModels = $state<boolean>(false);

  async function loadData() {
    try {
      loading = true;
      const [ag, pr, tl] = await Promise.all([
        api.getAgents(),
        api.getProviders(),
        api.getTools(),
      ]);
      agents = ag;
      providers = pr;
      availableTools = tl;
      if (providers.length > 0 && !formProviderId) {
        formProviderId = providers[0].id;
      }
    } catch (err: any) {
      console.error("Failed to load studio data:", err);
    } finally {
      loading = false;
    }
  }

  onMount(loadData);

  async function fetchModelsForProvider(pId: string) {
    if (!pId) return;
    loadingModels = true;
    try {
      providerModels = await api.getProviderModels(pId);
      if (providerModels.length > 0 && !isEditing) {
        formModelName = providerModels[0].id;
      }
    } catch (e) {
      providerModels = [];
    } finally {
      loadingModels = false;
    }
  }

  function openCreateModal() {
    isEditing = false;
    editId = null;
    formName = '';
    formAvatar = 'cyber-bot-01';
    formRole = '';
    formGoal = '';
    formBackstory = '';
    formNodeType = 'worker';
    formTemperature = 0.7;
    formMaxTokens = 4096;
    formTools = [];
    formApproval = false;
    formError = '';
    if (providers.length > 0) {
      formProviderId = providers[0].id;
      fetchModelsForProvider(formProviderId);
    }
    showModal = true;
  }

  function openEditModal(agent: any) {
    isEditing = true;
    editId = agent.id;
    formName = agent.name;
    formAvatar = agent.avatar_code || 'cyber-bot-01';
    formRole = agent.role;
    formGoal = agent.goal;
    formBackstory = agent.backstory;
    formNodeType = agent.node_type;
    formProviderId = agent.provider_id;
    formModelName = agent.model_name;
    formTemperature = agent.temperature;
    formMaxTokens = agent.max_tokens;
    formTools = [...(agent.tools_config || [])];
    formApproval = Boolean(agent.require_device_approval);
    formError = '';
    fetchModelsForProvider(agent.provider_id);
    showModal = true;
  }

  function toggleTool(toolId: string) {
    if (formTools.includes(toolId)) {
      formTools = formTools.filter(t => t !== toolId);
    } else {
      formTools = [...formTools, toolId];
    }
  }

  async function handleSaveAgent(e: SubmitEvent) {
    e.preventDefault();
    if (!formName.trim() || !formRole.trim() || !formGoal.trim() || !formProviderId) {
      formError = 'Please fill out all required fields and select a provider.';
      return;
    }

    formSubmitting = true;
    formError = '';
    try {
      const payload = {
        name: formName,
        avatar_code: formAvatar,
        role: formRole,
        goal: formGoal,
        backstory: formBackstory,
        node_type: formNodeType,
        provider_id: formProviderId,
        model_name: formModelName,
        temperature: formTemperature,
        max_tokens: formMaxTokens,
        tools_config: formTools,
        require_device_approval: formApproval,
      };

      if (isEditing && editId) {
        await api.updateAgent(editId, payload);
      } else {
        await api.createAgent(payload);
      }

      showModal = false;
      await loadData();
    } catch (err: any) {
      formError = err.message || 'Failed to save agent template';
    } finally {
      formSubmitting = false;
    }
  }

  async function handleDeleteAgent(id: string, name: string) {
    if (!confirm(`Are you sure you want to delete agent '${name}'?`)) return;
    try {
      await api.deleteAgent(id);
      await loadData();
    } catch (err: any) {
      alert(`Delete error: ${err.message}`);
    }
  }
</script>

<div class="space-y-6">
  <!-- Header Bar -->
  <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-[var(--border-color)] pb-4">
    <div>
      <div class="text-[11px] font-code text-[var(--accent-primary)] uppercase tracking-wider">
        MODULE // 03
      </div>
      <h1 class="text-xl md:text-2xl font-hud font-black text-[var(--text-primary)]">
        DYNAMIC AGENT STUDIO
      </h1>
      <p class="text-xs text-[var(--text-muted)] mt-1">
        Construct unlimited custom agents with CrewAI Role/Goal/Backstory personas and hardware device capabilities.
      </p>
    </div>

    <CyberButton variant="primary" onclick={openCreateModal}>
      <Plus class="w-4 h-4" />
      <span>CREATE AGENT PERSONA</span>
    </CyberButton>
  </div>

  <!-- Agent Cards Grid -->
  {#if loading}
    <div class="text-center py-12 font-code text-xs text-[var(--text-muted)] animate-pulse">
      INDEXING AGENT DIRECTORY...
    </div>
  {:else if agents.length === 0}
    <div class="border border-dashed border-[var(--border-color)] p-8 text-center chamfer space-y-3">
      <Bot class="w-10 h-10 mx-auto text-[var(--text-muted)] opacity-50" />
      <div class="font-hud font-bold text-sm text-[var(--text-primary)]">NO AGENTS ASSEMBLED</div>
      <p class="text-xs text-[var(--text-muted)] max-w-md mx-auto">
        Create your first dynamic worker or reviewer agent to build cyclic graph pipelines.
      </p>
      <CyberButton variant="primary" size="sm" onclick={openCreateModal}>
        BUILD AGENT
      </CyberButton>
    </div>
  {:else}
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-4">
      {#each agents as agent (agent.id)}
        <CyberCard
          code={agent.avatar_code?.toUpperCase() || 'AGENT.01'}
          title={agent.name}
          variant={agent.node_type === 'reviewer' ? 'elevated' : 'default'}
        >
          <div class="space-y-3">
            <!-- Node Type & Model Badge -->
            <div class="flex items-center justify-between gap-2">
              <span class="px-2 py-0.5 rounded text-[10px] font-hud font-bold uppercase {agent.node_type === 'reviewer' ? 'bg-[var(--status-warning)]/20 text-[var(--status-warning)] border border-[var(--status-warning)]/30' : agent.node_type === 'supervisor' ? 'bg-[var(--status-success)]/20 text-[var(--status-success)]' : 'bg-[var(--accent-primary)]/20 text-[var(--accent-primary)] border border-[var(--accent-primary)]/30'}">
                TYPE: {agent.node_type}
              </span>

              <span class="text-[10px] font-code text-[var(--text-muted)] truncate max-w-[180px]">
                {agent.model_name}
              </span>
            </div>

            <!-- Role & Goal -->
            <div>
              <div class="text-[10px] font-code text-[var(--text-muted)] uppercase">ROLE & RESPONSIBILITY</div>
              <div class="text-xs font-semibold text-[var(--text-primary)] mt-0.5">{agent.role}</div>
            </div>

            <div>
              <div class="text-[10px] font-code text-[var(--text-muted)] uppercase">MISSION GOAL</div>
              <div class="text-[11px] text-[var(--text-primary)] mt-0.5 line-clamp-2">{agent.goal}</div>
            </div>

            <!-- Hardware & Device Capabilities Badges -->
            <div class="pt-2 border-t border-[var(--border-color)]/30">
              <div class="text-[10px] font-code text-[var(--text-muted)] uppercase mb-1.5 flex items-center gap-1">
                <HardDrive class="w-3 h-3 text-[var(--accent-primary)]" />
                HARDWARE & DOCUMENT CAPABILITIES:
              </div>

              {#if agent.tools_config && agent.tools_config.length > 0}
                <div class="flex flex-wrap gap-1.5">
                  {#each agent.tools_config as tool}
                    <span class="px-2 py-0.5 text-[10px] font-code rounded bg-[var(--bg-elevated)] border border-[var(--accent-primary)]/30 text-[var(--accent-primary)]">
                      {tool.replace('create_', '').replace('_document', '').toUpperCase()}
                    </span>
                  {/each}
                </div>
              {:else}
                <span class="text-[10px] font-code text-[var(--text-muted)] italic">
                  Pure reasoning / No direct device write access
                </span>
              {/if}
            </div>

            <!-- Actions -->
            <div class="pt-2 border-t border-[var(--border-color)]/30 flex items-center justify-between">
              <div class="text-[10px] font-code text-[var(--text-muted)]">
                Temp: {agent.temperature} | MaxTok: {agent.max_tokens}
              </div>

              <div class="flex items-center gap-1">
                <button
                  type="button"
                  onclick={() => openEditModal(agent)}
                  class="p-1.5 text-[var(--text-muted)] hover:text-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/10 rounded transition-colors"
                  title="Edit agent"
                >
                  <Edit3 class="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  onclick={() => handleDeleteAgent(agent.id, agent.name)}
                  class="p-1.5 text-[var(--status-danger)] hover:bg-[var(--status-danger)]/10 rounded transition-colors"
                  title="Delete agent"
                >
                  <Trash2 class="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
        </CyberCard>
      {/each}
    </div>
  {/if}

  <!-- Create / Edit Drawer Modal -->
  {#if showModal}
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 overflow-y-auto">
      <div class="w-full max-w-2xl border border-[var(--accent-primary)] bg-[var(--bg-surface)] p-6 chamfer shadow-[var(--border-glow)] my-8 space-y-4">
        <div class="flex items-center justify-between border-b border-[var(--border-color)] pb-3">
          <div class="font-hud font-bold text-sm text-[var(--text-primary)]">
            {isEditing ? 'RECONFIGURE AGENT PERSONA' : 'ASSEMBLE NEW AGENT PERSONA'}
          </div>
          <button
            type="button"
            onclick={() => showModal = false}
            class="text-xs font-hud text-[var(--text-muted)] hover:text-white"
          >
            [CLOSE]
          </button>
        </div>

        {#if formError}
          <div class="p-2.5 text-xs font-code text-[var(--status-danger)] bg-[var(--status-danger)]/10 border border-[var(--status-danger)]">
            {formError}
          </div>
        {/if}

        <form onsubmit={handleSaveAgent} class="space-y-4 text-xs font-code">
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label class="block text-[var(--text-muted)] mb-1">
                <span>Agent Name *</span>
                <input
                  type="text"
                  bind:value={formName}
                  placeholder="e.g. CYPHER-01 // Deep Researcher"
                  class="w-full mt-1 px-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
                  required
                />
              </label>
            </div>

            <div>
              <label class="block text-[var(--text-muted)] mb-1">
                <span>Avatar Code</span>
                <input
                  type="text"
                  bind:value={formAvatar}
                  placeholder="cyber-bot-01"
                  class="w-full mt-1 px-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
                />
              </label>
            </div>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label class="block text-[var(--text-muted)] mb-1">
                <span>Node Behavior Type *</span>
                <select
                  bind:value={formNodeType}
                  class="w-full mt-1 px-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
                >
                  <option value="worker">Worker (Executes tasks & generates drafts)</option>
                  <option value="reviewer">Reviewer (Audits drafts with is_approved & loops)</option>
                  <option value="supervisor">Supervisor (Delegates to sub-agents)</option>
                </select>
              </label>
            </div>

            <div>
              <label class="block text-[var(--text-muted)] mb-1">
                <span>Provider Vault *</span>
                <select
                  bind:value={formProviderId}
                  onchange={() => fetchModelsForProvider(formProviderId)}
                  class="w-full mt-1 px-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
                >
                  {#each providers as prov}
                    <option value={prov.id}>{prov.name} ({prov.provider_type})</option>
                  {/each}
                </select>
              </label>
            </div>
          </div>

          <div>
            <label class="block text-[var(--text-muted)] mb-1">
              <span>Model Name *</span>
              {#if providerModels.length > 0}
                <select
                  bind:value={formModelName}
                  class="w-full mt-1 px-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
                >
                  {#each providerModels as m}
                    <option value={m.id}>{m.id} {m.name ? `(${m.name})` : ''}</option>
                  {/each}
                </select>
              {:else}
                <input
                  type="text"
                  bind:value={formModelName}
                  placeholder="e.g. meta-llama/llama-3.3-70b-instruct"
                  class="w-full mt-1 px-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
                  required
                />
              {/if}
            </label>
          </div>

          <div>
            <label class="block text-[var(--text-muted)] mb-1">
              <span>Role (CrewAI Persona) *</span>
              <input
                type="text"
                bind:value={formRole}
                placeholder="e.g. Lead Systems Architect & Technical Writer"
                class="w-full mt-1 px-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
                required
              />
            </label>
          </div>

          <div>
            <label class="block text-[var(--text-muted)] mb-1">
              <span>Mission Goal *</span>
              <textarea
                bind:value={formGoal}
                rows="2"
                placeholder="Specific objective and standard of excellence for this agent..."
                class="w-full mt-1 px-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
                required
              ></textarea>
            </label>
          </div>

          <div>
            <label class="block text-[var(--text-muted)] mb-1">
              <span>Backstory & Domain Expertise *</span>
              <textarea
                bind:value={formBackstory}
                rows="2"
                placeholder="Contextual background and technical mindset..."
                class="w-full mt-1 px-3 py-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
                required
              ></textarea>
            </label>
          </div>

          <!-- Hardware Device & Document Tools -->
          <div class="border border-[var(--border-color)] bg-[var(--bg-elevated)]/40 p-3 chamfer-sm space-y-2">
            <div class="flex items-center gap-2 font-hud text-[11px] text-[var(--accent-primary)] font-bold">
              <HardDrive class="w-4 h-4" />
              HARDWARE & DOCUMENT CAPABILITY ACCESS
            </div>
            <p class="text-[10px] text-[var(--text-muted)]">
              Select device actions this agent is authorized to execute on local workstation storage:
            </p>

            <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
              {#each availableTools as tool}
                {@const isChecked = formTools.includes(tool.id)}
                <button
                  type="button"
                  onclick={() => toggleTool(tool.id)}
                  class="flex items-start gap-2 p-2 border rounded-sm text-left transition-colors cursor-pointer {isChecked ? 'border-[var(--accent-primary)] bg-[var(--accent-primary)]/10 text-[var(--text-primary)]' : 'border-[var(--border-color)]/60 bg-[var(--bg-surface)] text-[var(--text-muted)]'}"
                >
                  <div class="w-4 h-4 rounded border flex items-center justify-center mt-0.5 {isChecked ? 'border-[var(--accent-primary)] bg-[var(--accent-primary)] text-black' : 'border-[var(--text-muted)]'}">
                    {#if isChecked}<Check class="w-3 h-3 stroke-[3]" />{/if}
                  </div>
                  <div>
                    <div class="font-bold text-[11px]">{tool.name}</div>
                    <div class="text-[9px] opacity-75 line-clamp-1">{tool.description}</div>
                  </div>
                </button>
              {/each}
            </div>
          </div>

          <div class="pt-3 border-t border-[var(--border-color)] flex justify-end gap-2">
            <CyberButton variant="ghost" size="sm" type="button" onclick={() => showModal = false}>
              CANCEL
            </CyberButton>
            <CyberButton variant="primary" size="sm" type="submit" disabled={formSubmitting}>
              {formSubmitting ? 'PERSISTING...' : isEditing ? 'SAVE CHANGES' : 'CREATE AGENT'}
            </CyberButton>
          </div>
        </form>
      </div>
    </div>
  {/if}
</div>
