<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { api, type IntegrationClient, type IntegrationProbeResult } from '$lib/api';
  import { notify } from '$lib/stores/notify.svelte';
  import CyberCard from '$lib/components/ui/CyberCard.svelte';
  import CyberButton from '$lib/components/ui/CyberButton.svelte';
  import LoadError from '$lib/components/ui/LoadError.svelte';
  import {
    Activity,
    Cable,
    Plus,
    RefreshCw,
    Play,
    Key,
    Copy,
    Check,
    Eye,
    EyeOff,
    Trash2,
    Pencil,
    ExternalLink,
    Server,
    Shield,
    CheckCircle2,
    XCircle,
    AlertTriangle,
    Clock,
    Send,
    Code2,
    Radio,
    Terminal,
    Sparkles,
    Loader2,
    Search,
    Zap,
  } from 'lucide-svelte';

  let clients = $state<IntegrationClient[]>([]);
  let loading = $state<boolean>(true);
  let loadError = $state<string | null>(null);
  let searchQuery = $state<string>('');

  // Live Auto-Monitor
  let autoMonitor = $state<boolean>(false);
  let monitorIntervalSec = $state<number>(10);
  let monitorTimer = $state<any>(null);

  // Per-client loading states
  let pingLoading = $state<Record<string, boolean>>({});
  let pingAllLoading = $state<boolean>(false);
  let revealedKeys = $state<Record<string, boolean>>({});
  let copiedKey = $state<Record<string, boolean>>({});

  // Modals
  let showClientModal = $state<boolean>(false);
  let editingClient = $state<IntegrationClient | null>(null);
  let formName = $state<string>('');
  let formDescription = $state<string>('');
  let formTargetUrl = $state<string>('http://localhost:8208/');
  let formHealthEndpoint = $state<string>('/');
  let formAllowedModels = $state<string>('*');
  let formIsActive = $state<boolean>(true);
  let formProbeImmediately = $state<boolean>(true);
  let formSubmitting = $state<boolean>(false);
  let formError = $state<string>('');

  // Code Snippets Modal
  let showCodeModal = $state<boolean>(false);
  let selectedClientForCode = $state<IntegrationClient | null>(null);
  let activeCodeTab = $state<'laravel' | 'curl' | 'python' | 'js'>('laravel');

  // Interactive Connection Tester Modal
  let showTestModal = $state<boolean>(false);
  let selectedClientForTest = $state<IntegrationClient | null>(null);
  let testType = $state<'handshake' | 'chat'>('handshake');
  let testPrompt = $state<string>('Halo Omnigensi AI dari project Laravel agen xishie!');
  let testRunning = $state<boolean>(false);
  let testResult = $state<any>(null);
  let testError = $state<string | null>(null);

  async function loadClients() {
    try {
      loading = true;
      loadError = null;
      clients = await api.getIntegrationClients();
    } catch (e: any) {
      loadError = e?.message || 'Gagal memuat daftar integrasi target';
    } finally {
      loading = false;
    }
  }

  function startAutoMonitor() {
    stopAutoMonitor();
    if (!autoMonitor) return;
    monitorTimer = setInterval(async () => {
      try {
        const results = await api.pingAllIntegrationClients();
        // Update local client list with fresh status
        const resultMap = new Map(results.map((r) => [r.client_id, r]));
        clients = clients.map((c) => {
          const r = resultMap.get(c.id);
          if (!r) return c;
          return {
            ...c,
            status: r.status,
            last_status_code: r.status_code,
            last_latency_ms: r.latency_ms,
            last_checked_at: r.checked_at,
            last_error: r.error,
            target_server: r.server_header,
            extra_metadata: { headers: r.headers },
          };
        });
      } catch {
        // silent fail during background polling
      }
    }, monitorIntervalSec * 1000);
  }

  function stopAutoMonitor() {
    if (monitorTimer) {
      clearInterval(monitorTimer);
      monitorTimer = null;
    }
  }

  $effect(() => {
    if (autoMonitor) {
      startAutoMonitor();
    } else {
      stopAutoMonitor();
    }
  });

  onMount(() => {
    loadClients();
  });

  onDestroy(() => {
    stopAutoMonitor();
  });

  // Filtered clients
  const filteredClients = $derived(
    clients.filter((c) => {
      const q = searchQuery.toLowerCase().trim();
      if (!q) return true;
      return (
        c.name.toLowerCase().includes(q) ||
        c.target_url.toLowerCase().includes(q) ||
        (c.description || '').toLowerCase().includes(q)
      );
    })
  );

  const totalClients = $derived(clients.length);
  const onlineCount = $derived(clients.filter((c) => c.status === 'online').length);
  const degradedCount = $derived(clients.filter((c) => c.status === 'degraded').length);
  const offlineCount = $derived(clients.filter((c) => c.status === 'offline' || c.status === 'unknown').length);
  const totalInbound = $derived(
    clients.reduce((acc, c) => acc + (c.inbound_requests_count || 0), 0)
  );

  async function handlePing(client: IntegrationClient) {
    pingLoading[client.id] = true;
    try {
      const res = await api.pingIntegrationClient(client.id);
      clients = clients.map((c) =>
        c.id === client.id
          ? {
              ...c,
              status: res.status,
              last_status_code: res.status_code,
              last_latency_ms: res.latency_ms,
              last_checked_at: res.checked_at,
              last_error: res.error,
              target_server: res.server_header,
              extra_metadata: { headers: res.headers },
            }
          : c
      );
      if (res.status === 'online') {
        notify.success(`Target ${client.name} TERHUBUNG (${res.latency_ms}ms, HTTP ${res.status_code})`);
      } else if (res.status === 'degraded') {
        notify.warning(`Target ${client.name} MERESPONS (${res.latency_ms}ms, HTTP ${res.status_code})`);
      } else {
        notify.error(`Target ${client.name} TIDAK TERHUBUNG: ${res.error || 'Connection failed'}`);
      }
    } catch (e: any) {
      notify.error(`Gagal ping ${client.name}: ${e.message}`);
    } finally {
      pingLoading[client.id] = false;
    }
  }

  async function handlePingAll() {
    pingAllLoading = true;
    try {
      const results = await api.pingAllIntegrationClients();
      const resultMap = new Map(results.map((r) => [r.client_id, r]));
      clients = clients.map((c) => {
        const r = resultMap.get(c.id);
        if (!r) return c;
        return {
          ...c,
          status: r.status,
          last_status_code: r.status_code,
          last_latency_ms: r.latency_ms,
          last_checked_at: r.checked_at,
          last_error: r.error,
          target_server: r.server_header,
          extra_metadata: { headers: r.headers },
        };
      });
      notify.success(`Ping selesai untuk ${results.length} target.`);
    } catch (e: any) {
      notify.error(`Gagal ping semua target: ${e.message}`);
    } finally {
      pingAllLoading = false;
    }
  }

  async function handleSeedXishie() {
    try {
      const xishie = await api.seedXishieIntegration();
      notify.success(`Target 'agen xishie' (${xishie.target_url}) berhasil disinkronkan!`);
      await loadClients();
    } catch (e: any) {
      notify.error(`Gagal menyiapkan agen xishie: ${e.message}`);
    }
  }

  function openRegisterModal() {
    editingClient = null;
    formName = '';
    formDescription = '';
    formTargetUrl = 'http://localhost:8208/';
    formHealthEndpoint = '/';
    formAllowedModels = '*';
    formIsActive = true;
    formProbeImmediately = true;
    formError = '';
    showClientModal = true;
  }

  function openEditModal(client: IntegrationClient) {
    editingClient = client;
    formName = client.name;
    formDescription = client.description || '';
    formTargetUrl = client.target_url;
    formHealthEndpoint = client.health_endpoint || '/';
    formAllowedModels = (client.allowed_models || ['*']).join(', ');
    formIsActive = client.is_active;
    formProbeImmediately = true;
    formError = '';
    showClientModal = true;
  }

  async function handleSaveClient() {
    formError = '';
    if (!formName.trim()) {
      formError = 'Nama project wajib diisi.';
      return;
    }
    if (!formTargetUrl.trim() || (!formTargetUrl.startsWith('http://') && !formTargetUrl.startsWith('https://'))) {
      formError = 'Target URL harus dimulai dengan http:// atau https://';
      return;
    }

    const modelsList = formAllowedModels
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);

    formSubmitting = true;
    try {
      if (editingClient) {
        const updated = await api.updateIntegrationClient(editingClient.id, {
          name: formName.trim(),
          description: formDescription.trim() || null,
          target_url: formTargetUrl.trim(),
          health_endpoint: formHealthEndpoint.trim() || '/',
          allowed_models: modelsList.length > 0 ? modelsList : ['*'],
          is_active: formIsActive,
        });
        clients = clients.map((c) => (c.id === updated.id ? updated : c));
        notify.success(`Project ${updated.name} berhasil diperbarui.`);
      } else {
        const created = await api.registerIntegrationClient(
          {
            name: formName.trim(),
            description: formDescription.trim() || null,
            target_url: formTargetUrl.trim(),
            health_endpoint: formHealthEndpoint.trim() || '/',
            allowed_models: modelsList.length > 0 ? modelsList : ['*'],
            is_active: formIsActive,
          },
          formProbeImmediately
        );
        clients = [created, ...clients];
        notify.success(`Project ${created.name} berhasil didaftarkan!`);
      }
      showClientModal = false;
    } catch (e: any) {
      formError = e.message || 'Gagal menyimpan data integrasi.';
    } finally {
      formSubmitting = false;
    }
  }

  async function handleDeleteClient(client: IntegrationClient) {
    const ok = await notify.confirm({
      title: 'Hapus Integrasi Project',
      message: `Hapus integrasi '${client.name}'? Akses API Key ${client.api_key.substring(0, 14)}... akan langsung dicabut.`,
      destructive: true,
    });
    if (!ok) return;

    try {
      await api.deleteIntegrationClient(client.id);
      clients = clients.filter((c) => c.id !== client.id);
      notify.success(`Integrasi ${client.name} dihapus.`);
    } catch (e: any) {
      notify.error(`Gagal menghapus client: ${e.message}`);
    }
  }

  async function handleRegenerateKey(client: IntegrationClient) {
    const ok = await notify.confirm({
      title: 'Regenerasi API Key',
      message: `Regenerasi API Key untuk '${client.name}'? Key lama tidak akan bisa dipakai lagi oleh project target.`,
      destructive: true,
    });
    if (!ok) return;

    try {
      const updated = await api.regenerateIntegrationClientKey(client.id);
      clients = clients.map((c) => (c.id === updated.id ? updated : c));
      notify.success(`API Key baru dibuat untuk ${client.name}`);
    } catch (e: any) {
      notify.error(`Gagal regenerasi API key: ${e.message}`);
    }
  }

  async function copyToClipboard(text: string, clientId: string) {
    try {
      await navigator.clipboard.writeText(text);
      copiedKey[clientId] = true;
      notify.success('API Key disalin ke clipboard');
      setTimeout(() => {
        copiedKey[clientId] = false;
      }, 2000);
    } catch {
      notify.error('Gagal menyalin ke clipboard');
    }
  }

  function openCodeModal(client: IntegrationClient) {
    selectedClientForCode = client;
    activeCodeTab = 'laravel';
    showCodeModal = true;
  }

  function openTestModal(client: IntegrationClient) {
    selectedClientForTest = client;
    testType = 'handshake';
    testResult = null;
    testError = null;
    showTestModal = true;
  }

  async function runInteractiveTest() {
    if (!selectedClientForTest) return;
    testRunning = true;
    testResult = null;
    testError = null;
    try {
      if (testType === 'handshake') {
        const res = await api.testExternalHandshake(selectedClientForTest.api_key);
        testResult = res;
        notify.success('Handshake sukses terverifikasi!');
      } else {
        const res = await api.testExternalChat(
          selectedClientForTest.api_key,
          testPrompt
        );
        testResult = res;
        notify.success('AI Chat Completion berhasil dijawab!');
      }
      // Refresh local clients list to reflect incremented request count
      loadClients();
    } catch (e: any) {
      testError = e.message || 'Tes koneksi gagal.';
      notify.error(`Tes gagal: ${testError}`);
    } finally {
      testRunning = false;
    }
  }

  function formatRelativeTime(dateStr?: string | null): string {
    if (!dateStr) return 'Belum pernah dicek';
    const date = new Date(dateStr);
    const now = new Date();
    const diffSec = Math.floor((now.getTime() - date.getTime()) / 1000);
    if (diffSec < 5) return 'Baru saja';
    if (diffSec < 60) return `${diffSec} detik lalu`;
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin} menit lalu`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr} jam lalu`;
    return date.toLocaleDateString();
  }

  const laravelSnippetEnv = (apiKey: string) => `OMNIGENSI_BASE_URL=http://localhost:8123\nOMNIGENSI_API_KEY=${apiKey}`;

  const laravelSnippetHandshake = `use Illuminate\\Support\\Facades\\Http;

$response = Http::withHeaders([
    'X-API-Key' => env('OMNIGENSI_API_KEY'),
])->get(env('OMNIGENSI_BASE_URL') . '/api/v1/integrations/v1/handshake');

if ($response->successful()) {
    $data = $response->json();
    logger()->info('Terhubung ke Omnigensi:', $data);
}`;

  const laravelSnippetChat = `use Illuminate\\Support\\Facades\\Http;

$response = Http::withHeaders([
    'X-API-Key' => env('OMNIGENSI_API_KEY'),
    'Content-Type' => 'application/json',
])->post(env('OMNIGENSI_BASE_URL') . '/api/v1/integrations/v1/chat/completions', [
    'messages' => [
        ['role' => 'system', 'content' => 'Anda adalah asisten AI dari Agen Xishie.'],
        ['role' => 'user', 'content' => 'Halo, bantu analisa data penjualan ini.'],
    ],
    'stream' => false,
]);

if ($response->successful()) {
    $aiReply = $response->json('choices.0.message.content');
    return response()->json(['reply' => $aiReply]);
}`;

  const curlSnippetHandshake = (apiKey: string) => `curl -X GET http://localhost:8123/api/v1/integrations/v1/handshake \\
  -H "X-API-Key: ${apiKey}"`;

  const curlSnippetChat = (apiKey: string) => `curl -X POST http://localhost:8123/api/v1/integrations/v1/chat/completions \\
  -H "X-API-Key: ${apiKey}" \\
  -H "Content-Type: application/json" \\
  -d '{"messages": [{"role": "user", "content": "Halo dari terminal!"}]}'`;

  const pythonSnippet = (apiKey: string) => `import httpx

headers = {"X-API-Key": "${apiKey}"}

# 1. Handshake
r = httpx.get("http://localhost:8123/api/v1/integrations/v1/handshake", headers=headers)
print("Handshake:", r.json())

# 2. Chat AI Model
payload = {
    "messages": [{"role": "user", "content": "Halo Omnigensi!"}],
    "stream": False,
}
chat = httpx.post("http://localhost:8123/api/v1/integrations/v1/chat/completions", headers=headers, json=payload)
print("AI Reply:", chat.json()["choices"][0]["message"]["content"])`;
</script>

<div class="space-y-6">
  <!-- Top Title & Description Header -->
  <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[var(--border-color)] pb-4">
    <div>
      <div class="flex items-center gap-2">
        <div class="p-2 bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] border border-[var(--accent-primary)]/30 chamfer-sm">
          <Cable class="w-5 h-5" />
        </div>
        <div>
          <h1 class="font-hud font-black text-xl tracking-wider text-[var(--text-primary)]">
            CONNECTED PROJECTS // INTEGRATION HUB
          </h1>
          <p class="text-xs font-code text-[var(--text-muted)]">
            Hubungkan project eksternal (mis. Laravel <span class="text-[var(--accent-primary)] font-bold">agen xishie</span> di http://localhost:8208/), monitoring status koneksi, dan sediakan API Key modular.
          </p>
        </div>
      </div>
    </div>

    <!-- Actions toolbar -->
    <div class="flex flex-wrap items-center gap-2">
      <!-- Auto monitor toggle -->
      <div class="flex items-center gap-2 px-3 py-1.5 border border-[var(--border-color)] bg-[var(--bg-elevated)]/60 chamfer-sm font-code text-xs">
        <label class="flex items-center gap-1.5 cursor-pointer">
          <input type="checkbox" bind:checked={autoMonitor} class="accent-[var(--accent-primary)] rounded cursor-pointer" />
          <span class={autoMonitor ? 'text-[var(--status-success)] font-bold' : 'text-[var(--text-muted)]'}>
            LIVE MONITOR
          </span>
        </label>
        {#if autoMonitor}
          <span class="w-2 h-2 rounded-full bg-[var(--status-success)] animate-pulse"></span>
          <select
            bind:value={monitorIntervalSec}
            class="bg-transparent border-b border-[var(--border-color)] text-[10px] text-[var(--accent-primary)] focus:outline-none py-0 px-1 cursor-pointer"
          >
            <option value={5}>5s</option>
            <option value={10}>10s</option>
            <option value={30}>30s</option>
          </select>
        {/if}
      </div>

      <!-- Ping all button -->
      <CyberButton
        variant="outline"
        onclick={handlePingAll}
        disabled={pingAllLoading || clients.length === 0}
        title="Ping seluruh target aktif sekarang"
      >
        {#if pingAllLoading}
          <Loader2 class="w-3.5 h-3.5 animate-spin mr-1.5 inline" />
          <span>CHECKING...</span>
        {:else}
          <RefreshCw class="w-3.5 h-3.5 mr-1.5 inline text-[var(--accent-primary)]" />
          <span>PING ALL</span>
        {/if}
      </CyberButton>

      <!-- Restore / Quick Seed Xishie -->
      <CyberButton
        variant="outline"
        onclick={handleSeedXishie}
        title="Pulihkan atau daftarkan otomatis agen xishie (http://localhost:8208/)"
      >
        <Zap class="w-3.5 h-3.5 mr-1.5 inline text-[var(--status-warning)]" />
        <span>QUICK SEED XISHIE</span>
      </CyberButton>

      <!-- Register New Project Button -->
      <CyberButton variant="primary" onclick={openRegisterModal}>
        <Plus class="w-4 h-4 mr-1.5 inline" />
        <span>+ REGISTER PROJECT</span>
      </CyberButton>
    </div>
  </div>

  <!-- Metric Badges & Search Filter -->
  <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
    <div class="p-3 border border-[var(--border-color)] bg-[var(--bg-elevated)]/40 chamfer-sm">
      <div class="text-[10px] font-code text-[var(--text-muted)] tracking-wider">TOTAL PROJECTS</div>
      <div class="font-hud font-black text-2xl text-[var(--text-primary)] mt-1">{totalClients}</div>
    </div>

    <div class="p-3 border border-[var(--status-success)]/40 bg-[var(--status-success)]/5 chamfer-sm">
      <div class="flex items-center justify-between">
        <div class="text-[10px] font-code text-[var(--status-success)] tracking-wider">ONLINE / REACHABLE</div>
        <span class="w-2 h-2 rounded-full bg-[var(--status-success)] animate-pulse"></span>
      </div>
      <div class="font-hud font-black text-2xl text-[var(--status-success)] mt-1">{onlineCount}</div>
    </div>

    <div class="p-3 border border-[var(--status-danger)]/40 bg-[var(--status-danger)]/5 chamfer-sm">
      <div class="text-[10px] font-code text-[var(--status-danger)] tracking-wider">OFFLINE / UNREACHABLE</div>
      <div class="font-hud font-black text-2xl text-[var(--status-danger)] mt-1">{offlineCount + degradedCount}</div>
    </div>

    <div class="p-3 border border-[var(--border-color)] bg-[var(--bg-elevated)]/40 chamfer-sm">
      <div class="text-[10px] font-code text-[var(--accent-primary)] tracking-wider">INBOUND API CALLS</div>
      <div class="font-hud font-black text-2xl text-[var(--accent-primary)] mt-1">{totalInbound}</div>
    </div>
  </div>

  <!-- Search Filter Input -->
  <div class="flex items-center gap-2 p-2 border border-[var(--border-color)] bg-[var(--bg-elevated)]/30 chamfer-sm">
    <Search class="w-4 h-4 text-[var(--text-muted)] ml-1" />
    <input
      type="text"
      placeholder="Cari berdasarkan nama project, target URL (e.g. localhost:8208), atau deskripsi..."
      bind:value={searchQuery}
      class="bg-transparent text-xs font-code text-[var(--text-primary)] w-full placeholder:text-[var(--text-muted)] focus:outline-none"
    />
    {#if searchQuery}
      <button
        type="button"
        onclick={() => (searchQuery = '')}
        class="text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] px-2 font-code"
      >
        CLEAR
      </button>
    {/if}
  </div>

  <!-- Content Loading / Error / Client List -->
  {#if loading}
    <div class="flex items-center justify-center py-20 gap-2 font-code text-xs text-[var(--text-muted)]">
      <Loader2 class="w-5 h-5 animate-spin text-[var(--accent-primary)]" />
      <span>MEMERIKSA DAFTAR INTEGRASI DAN KONEKTIVITAS...</span>
    </div>
  {:else if loadError}
    <LoadError message={loadError} onRetry={loadClients} />
  {:else if filteredClients.length === 0}
    <CyberCard>
      <div class="text-center py-12 space-y-4">
        <Cable class="w-12 h-12 mx-auto text-[var(--text-muted)]" />
        <div class="space-y-1">
          <h3 class="font-hud font-bold text-base text-[var(--text-primary)]">
            {#if searchQuery}TIDAK ADA PROJECT YANG COCOK{:else}BELUM ADA PROJECT EKSTERNAL TERDAFTAR{/if}
          </h3>
          <p class="text-xs font-code text-[var(--text-muted)] max-w-md mx-auto">
            Daftarkan project Laravel Anda (<span class="text-[var(--accent-primary)]">agen xishie</span> di http://localhost:8208/) untuk memonitor status koneksinya dan mulai memanggil AI models.
          </p>
        </div>
        <div class="flex justify-center gap-3">
          <CyberButton variant="outline" onclick={handleSeedXishie}>
            <Zap class="w-3.5 h-3.5 mr-1 inline" />
            DAFTARKAN AGEN XISHIE OTOMATIS
          </CyberButton>
          <CyberButton variant="primary" onclick={openRegisterModal}>
            <Plus class="w-3.5 h-3.5 mr-1 inline" />
            REGISTER MANUAL
          </CyberButton>
        </div>
      </div>
    </CyberCard>
  {:else}
    <!-- Grid of Client Cards -->
    <div class="grid grid-cols-1 gap-5">
      {#each filteredClients as client (client.id)}
        <div class="border border-[var(--border-color)] bg-[var(--bg-surface)] chamfer-sm p-5 space-y-4 shadow-sm hover:border-[var(--accent-primary)]/60 transition-all">
          <!-- Card Header -->
          <div class="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-[var(--border-color)]/70 pb-3">
            <div class="flex items-start gap-3">
              <!-- Status Icon with Glow -->
              <div class="mt-1">
                {#if client.status === 'online'}
                  <div class="relative flex items-center justify-center p-2 rounded-sm border border-[var(--status-success)]/40 bg-[var(--status-success)]/10 text-[var(--status-success)]">
                    <CheckCircle2 class="w-5 h-5" />
                    <span class="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-[var(--status-success)] animate-ping"></span>
                  </div>
                {:else if client.status === 'degraded'}
                  <div class="p-2 rounded-sm border border-[var(--status-warning)]/40 bg-[var(--status-warning)]/10 text-[var(--status-warning)]">
                    <AlertTriangle class="w-5 h-5" />
                  </div>
                {:else}
                  <div class="p-2 rounded-sm border border-[var(--status-danger)]/40 bg-[var(--status-danger)]/10 text-[var(--status-danger)]">
                    <XCircle class="w-5 h-5" />
                  </div>
                {/if}
              </div>

              <div>
                <div class="flex items-center gap-2 flex-wrap">
                  <span class="font-hud font-black text-lg text-[var(--text-primary)] tracking-wide">
                    {client.name}
                  </span>

                  <!-- Status Badge -->
                  {#if client.status === 'online'}
                    <span class="px-2 py-0.5 rounded-xs font-code font-bold text-[10px] tracking-wider bg-[var(--status-success)]/20 text-[var(--status-success)] border border-[var(--status-success)]/40">
                      ONLINE • {client.last_latency_ms ?? 0}ms • HTTP {client.last_status_code ?? 200}
                    </span>
                  {:else if client.status === 'degraded'}
                    <span class="px-2 py-0.5 rounded-xs font-code font-bold text-[10px] tracking-wider bg-[var(--status-warning)]/20 text-[var(--status-warning)] border border-[var(--status-warning)]/40">
                      DEGRADED • HTTP {client.last_status_code ?? 'ERR'}
                    </span>
                  {:else}
                    <span class="px-2 py-0.5 rounded-xs font-code font-bold text-[10px] tracking-wider bg-[var(--status-danger)]/20 text-[var(--status-danger)] border border-[var(--status-danger)]/40">
                      OFFLINE / UNREACHABLE
                    </span>
                  {/if}

                  {#if !client.is_active}
                    <span class="px-1.5 py-0.5 rounded-xs font-code text-[9px] bg-red-950/40 text-red-400 border border-red-800">
                      PAUSED
                    </span>
                  {/if}
                </div>

                {#if client.description}
                  <p class="text-xs font-code text-[var(--text-muted)] mt-0.5">{client.description}</p>
                {/if}
              </div>
            </div>

            <!-- Top Card Actions -->
            <div class="flex items-center gap-2">
              <button
                type="button"
                onclick={() => handlePing(client)}
                disabled={pingLoading[client.id]}
                class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-code font-bold rounded-sm border border-[var(--accent-primary)]/40 bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/20 transition-all cursor-pointer"
                title="Ping target URL sekarang"
              >
                {#if pingLoading[client.id]}
                  <Loader2 class="w-3.5 h-3.5 animate-spin" />
                  <span>PROBING...</span>
                {:else}
                  <RefreshCw class="w-3.5 h-3.5" />
                  <span>PING NOW</span>
                {/if}
              </button>

              <button
                type="button"
                onclick={() => openCodeModal(client)}
                class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-code rounded-sm border border-[var(--border-color)] bg-[var(--bg-elevated)] text-[var(--text-primary)] hover:border-[var(--accent-primary)] hover:text-[var(--accent-primary)] transition-all cursor-pointer"
                title="Buka panduan integrasi Laravel & cURL"
              >
                <Code2 class="w-3.5 h-3.5 text-[var(--accent-primary)]" />
                <span>INTEGRATION CODE</span>
              </button>

              <button
                type="button"
                onclick={() => openTestModal(client)}
                class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-code rounded-sm border border-[var(--border-color)] bg-[var(--bg-elevated)] text-[var(--text-primary)] hover:border-[var(--accent-primary)] hover:text-[var(--accent-primary)] transition-all cursor-pointer"
                title="Uji coba handshake atau hit model dengan API Key ini"
              >
                <Sparkles class="w-3.5 h-3.5 text-[var(--status-warning)]" />
                <span>TEST CALL</span>
              </button>

              <button
                type="button"
                onclick={() => openEditModal(client)}
                class="p-1.5 text-[var(--text-muted)] hover:text-[var(--text-primary)] border border-transparent hover:border-[var(--border-color)] rounded"
                title="Edit konfigurasi"
              >
                <Pencil class="w-3.5 h-3.5" />
              </button>

              <button
                type="button"
                onclick={() => handleDeleteClient(client)}
                class="p-1.5 text-[var(--text-muted)] hover:text-[var(--status-danger)] border border-transparent hover:border-[var(--status-danger)]/40 rounded"
                title="Hapus integrasi"
              >
                <Trash2 class="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          <!-- Card Body: 2 Columns (Outbound Monitoring vs Inbound API Security) -->
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 text-xs font-code">
            <!-- Column 1: Outbound Connectivity (Omnigensi -> Target Project) -->
            <div class="p-3 border border-[var(--border-color)] bg-[var(--bg-elevated)]/40 chamfer-sm space-y-2.5">
              <div class="flex items-center justify-between text-[11px] font-hud font-bold text-[var(--text-primary)] border-b border-[var(--border-color)]/50 pb-1.5">
                <span class="flex items-center gap-1.5 text-[var(--accent-primary)]">
                  <Activity class="w-3.5 h-3.5" />
                  OUTBOUND TARGET MONITORING
                </span>
                <span class="text-[10px] {client.status === 'online' ? 'text-[var(--status-success)]' : 'text-[var(--status-danger)]'}">
                  LAST CHECK: {formatRelativeTime(client.last_checked_at)}
                </span>
              </div>

              <div class="space-y-1.5">
                <div class="flex items-center justify-between">
                  <span class="text-[var(--text-muted)]">Target Base URL:</span>
                  <a
                    href={client.target_url}
                    target="_blank"
                    rel="noreferrer"
                    class="font-semibold text-[var(--accent-primary)] hover:underline flex items-center gap-1"
                  >
                    <span>{client.target_url}</span>
                    <ExternalLink class="w-3 h-3 inline" />
                  </a>
                </div>

                <div class="flex items-center justify-between">
                  <span class="text-[var(--text-muted)]">Health Endpoint:</span>
                  <span class="text-[var(--text-primary)] font-semibold">{client.health_endpoint}</span>
                </div>

                <div class="flex items-center justify-between">
                  <span class="text-[var(--text-muted)]">Server Header:</span>
                  <span class="text-[var(--text-primary)]">{client.target_server || 'Tidak terdeteksi'}</span>
                </div>

                <div class="flex items-center justify-between">
                  <span class="text-[var(--text-muted)]">Latency / RTT:</span>
                  <span class="font-bold {client.last_latency_ms && client.last_latency_ms < 100 ? 'text-[var(--status-success)]' : 'text-[var(--text-primary)]'}">
                    {client.last_latency_ms != null ? `${client.last_latency_ms} ms` : '—'}
                  </span>
                </div>

                {#if client.last_error}
                  <div class="p-2 border border-[var(--status-danger)]/50 bg-[var(--status-danger)]/10 text-[var(--status-danger)] text-[11px] rounded-xs mt-2">
                    <span class="font-bold">Error Terakhir:</span> {client.last_error}
                  </div>
                {/if}
              </div>
            </div>

            <!-- Column 2: Inbound API Bridge (Target Project -> Omnigensi) -->
            <div class="p-3 border border-[var(--border-color)] bg-[var(--bg-elevated)]/40 chamfer-sm space-y-2.5">
              <div class="flex items-center justify-between text-[11px] font-hud font-bold text-[var(--text-primary)] border-b border-[var(--border-color)]/50 pb-1.5">
                <span class="flex items-center gap-1.5 text-[var(--status-warning)]">
                  <Shield class="w-3.5 h-3.5" />
                  INBOUND API BRIDGE & CREDENTIALS
                </span>
                <span class="text-[10px] text-[var(--accent-primary)] font-bold">
                  {client.inbound_requests_count || 0} CALLS RECORDED
                </span>
              </div>

              <div class="space-y-1.5">
                <!-- API Key Display & Actions -->
                <div>
                  <div class="flex items-center justify-between mb-1">
                    <span class="text-[var(--text-muted)]">Client Secret / API Key:</span>
                    <button
                      type="button"
                      onclick={() => handleRegenerateKey(client)}
                      class="text-[10px] text-[var(--status-warning)] hover:underline font-code cursor-pointer"
                    >
                      [ROTATE KEY]
                    </button>
                  </div>
                  <div class="flex items-center gap-1 p-1.5 border border-[var(--border-color)] bg-[var(--bg-surface)] rounded-xs">
                    <Key class="w-3.5 h-3.5 text-[var(--status-warning)] shrink-0 ml-1" />
                    <code class="font-code text-[11px] text-[var(--text-primary)] flex-1 truncate select-all px-1">
                      {#if revealedKeys[client.id]}
                        {client.api_key}
                      {:else}
                        {client.api_key.substring(0, 10)}••••••••••••••••••••••••
                      {/if}
                    </code>
                    <button
                      type="button"
                      onclick={() => (revealedKeys[client.id] = !revealedKeys[client.id])}
                      class="p-1 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                      title={revealedKeys[client.id] ? 'Sembunyikan' : 'Tampilkan'}
                    >
                      {#if revealedKeys[client.id]}<EyeOff class="w-3.5 h-3.5" />{:else}<Eye class="w-3.5 h-3.5" />{/if}
                    </button>
                    <button
                      type="button"
                      onclick={() => copyToClipboard(client.api_key, client.id)}
                      class="p-1 text-[var(--accent-primary)] hover:text-[var(--text-primary)]"
                      title="Salin API Key"
                    >
                      {#if copiedKey[client.id]}<Check class="w-3.5 h-3.5 text-[var(--status-success)]" />{:else}<Copy class="w-3.5 h-3.5" />{/if}
                    </button>
                  </div>
                </div>

                <div class="flex items-center justify-between pt-1">
                  <span class="text-[var(--text-muted)]">Allowed Models:</span>
                  <span class="px-1.5 py-0.5 rounded-xs bg-[var(--bg-surface)] border border-[var(--border-color)] font-bold text-[var(--accent-primary)] text-[10px]">
                    {#if !client.allowed_models || client.allowed_models.includes('*')}
                      ALL ACTIVE MODELS (*)
                    {:else}
                      {client.allowed_models.join(', ')}
                    {/if}
                  </span>
                </div>

                <div class="flex items-center justify-between">
                  <span class="text-[var(--text-muted)]">Last Inbound Request:</span>
                  <span class="text-[var(--text-primary)]">
                    {#if client.last_handshake_at}
                      {formatRelativeTime(client.last_handshake_at)}
                    {:else}
                      Belum ada request dari target
                    {/if}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<!-- ========================================================================= -->
<!-- MODAL 1: REGISTER / EDIT CLIENT -->
<!-- ========================================================================= -->
{#if showClientModal}
  <div class="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
    <div class="w-full max-w-xl border border-[var(--border-color)] bg-[var(--bg-surface)] chamfer-sm p-6 shadow-2xl space-y-4">
      <div class="flex items-center justify-between border-b border-[var(--border-color)] pb-3">
        <div class="flex items-center gap-2">
          <Cable class="w-5 h-5 text-[var(--accent-primary)]" />
          <h2 class="font-hud font-bold text-base tracking-wider text-[var(--text-primary)]">
            {editingClient ? 'EDIT INTEGRATION TARGET' : 'REGISTER NEW TARGET PROJECT'}
          </h2>
        </div>
        <button
          type="button"
          onclick={() => (showClientModal = false)}
          class="text-[var(--text-muted)] hover:text-[var(--text-primary)] font-code text-sm"
        >
          ✕
        </button>
      </div>

      {#if formError}
        <div class="p-2.5 border border-[var(--status-danger)]/50 bg-[var(--status-danger)]/10 text-[var(--status-danger)] text-xs font-code rounded-xs">
          {formError}
        </div>
      {/if}

      <form onsubmit={(e) => { e.preventDefault(); handleSaveClient(); }} class="space-y-3 font-code text-xs">
        <div>
          <label for="form-project-name" class="block text-[var(--text-muted)] mb-1">NAMA PROJECT / IDENTIFIER *</label>
          <input
            id="form-project-name"
            type="text"
            required
            placeholder="mis. agen xishie"
            bind:value={formName}
            class="w-full p-2 border border-[var(--border-color)] bg-[var(--bg-elevated)] text-[var(--text-primary)] rounded-xs focus:border-[var(--accent-primary)] focus:outline-none"
          />
        </div>

        <div>
          <label for="form-project-desc" class="block text-[var(--text-muted)] mb-1">DESKRIPSI (OPSIONAL)</label>
          <input
            id="form-project-desc"
            type="text"
            placeholder="mis. Website Laravel Agency & Customer AI Assistant"
            bind:value={formDescription}
            class="w-full p-2 border border-[var(--border-color)] bg-[var(--bg-elevated)] text-[var(--text-primary)] rounded-xs focus:border-[var(--accent-primary)] focus:outline-none"
          />
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div class="sm:col-span-2">
            <label for="form-target-url" class="block text-[var(--text-muted)] mb-1">TARGET BASE URL *</label>
            <input
              id="form-target-url"
              type="text"
              required
              placeholder="http://localhost:8208/"
              bind:value={formTargetUrl}
              class="w-full p-2 border border-[var(--border-color)] bg-[var(--bg-elevated)] text-[var(--text-primary)] rounded-xs focus:border-[var(--accent-primary)] focus:outline-none"
            />
          </div>
          <div>
            <label for="form-health-endpoint" class="block text-[var(--text-muted)] mb-1">HEALTH ENDPOINT</label>
            <input
              id="form-health-endpoint"
              type="text"
              placeholder="/"
              bind:value={formHealthEndpoint}
              class="w-full p-2 border border-[var(--border-color)] bg-[var(--bg-elevated)] text-[var(--text-primary)] rounded-xs focus:border-[var(--accent-primary)] focus:outline-none"
            />
          </div>
        </div>

        <div>
          <label for="form-allowed-models" class="block text-[var(--text-muted)] mb-1">ALLOWED MODELS (pisahkan dengan koma atau '*' untuk semua)</label>
          <input
            id="form-allowed-models"
            type="text"
            placeholder="* atau gemini-2.5-flash, qwen-2.5-7b"
            bind:value={formAllowedModels}
            class="w-full p-2 border border-[var(--border-color)] bg-[var(--bg-elevated)] text-[var(--text-primary)] rounded-xs focus:border-[var(--accent-primary)] focus:outline-none"
          />
        </div>

        <div class="flex items-center gap-6 pt-2">
          <label class="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" bind:checked={formIsActive} class="accent-[var(--accent-primary)] rounded" />
            <span class="text-[var(--text-primary)]">Status Aktif (Boleh panggil API)</span>
          </label>

          {#if !editingClient}
            <label class="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" bind:checked={formProbeImmediately} class="accent-[var(--accent-primary)] rounded" />
              <span class="text-[var(--accent-primary)]">Langsung Ping Target saat disimpan</span>
            </label>
          {/if}
        </div>

        <div class="flex justify-end gap-2 pt-4 border-t border-[var(--border-color)]">
          <CyberButton variant="outline" onclick={() => (showClientModal = false)}>
            BATAL
          </CyberButton>
          <CyberButton variant="primary" type="submit" disabled={formSubmitting}>
            {#if formSubmitting}
              <Loader2 class="w-3.5 h-3.5 animate-spin mr-1 inline" />
              MENYIMPAN...
            {:else}
              SIMPAN INTEGRASI
            {/if}
          </CyberButton>
        </div>
      </form>
    </div>
  </div>
{/if}

<!-- ========================================================================= -->
<!-- MODAL 2: INTEGRATION CODE SNIPPETS & GUIDE -->
<!-- ========================================================================= -->
{#if showCodeModal && selectedClientForCode}
  <div class="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
    <div class="w-full max-w-2xl border border-[var(--border-color)] bg-[var(--bg-surface)] chamfer-sm p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
      <div class="flex items-center justify-between border-b border-[var(--border-color)] pb-3">
        <div class="flex items-center gap-2">
          <Code2 class="w-5 h-5 text-[var(--accent-primary)]" />
          <div>
            <h2 class="font-hud font-bold text-base tracking-wider text-[var(--text-primary)]">
              INTEGRATION GUIDE // {selectedClientForCode.name.toUpperCase()}
            </h2>
            <p class="text-xs font-code text-[var(--text-muted)]">
              Gunakan API Key ini di project Laravel atau backend Anda untuk memanggil model dan endpoint Omnigensi.
            </p>
          </div>
        </div>
        <button
          type="button"
          onclick={() => (showCodeModal = false)}
          class="text-[var(--text-muted)] hover:text-[var(--text-primary)] font-code text-sm"
        >
          ✕
        </button>
      </div>

      <!-- Tab Switcher -->
      <div class="flex border-b border-[var(--border-color)] font-code text-xs">
        <button
          type="button"
          onclick={() => (activeCodeTab = 'laravel')}
          class="px-4 py-2 font-bold transition-all border-b-2 {activeCodeTab === 'laravel' ? 'border-[var(--accent-primary)] text-[var(--accent-primary)] bg-[var(--accent-primary)]/10' : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]'}"
        >
          Laravel (PHP)
        </button>
        <button
          type="button"
          onclick={() => (activeCodeTab = 'curl')}
          class="px-4 py-2 font-bold transition-all border-b-2 {activeCodeTab === 'curl' ? 'border-[var(--accent-primary)] text-[var(--accent-primary)] bg-[var(--accent-primary)]/10' : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]'}"
        >
          cURL / Terminal
        </button>
        <button
          type="button"
          onclick={() => (activeCodeTab = 'python')}
          class="px-4 py-2 font-bold transition-all border-b-2 {activeCodeTab === 'python' ? 'border-[var(--accent-primary)] text-[var(--accent-primary)] bg-[var(--accent-primary)]/10' : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]'}"
        >
          Python (httpx/requests)
        </button>
      </div>

      <!-- Tab Content -->
      {#if activeCodeTab === 'laravel'}
        <div class="space-y-3 font-code text-xs">
          <p class="text-[var(--text-primary)]">
            Di project Laravel Anda (<span class="text-[var(--accent-primary)] font-bold">{selectedClientForCode.name}</span>), tambahkan konfigurasi di <code class="text-amber-400">.env</code>:
          </p>
          <pre class="p-3 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-xs overflow-x-auto text-[11px] text-[var(--text-primary)] select-all">{laravelSnippetEnv(selectedClientForCode.api_key)}</pre>

          <p class="text-[var(--text-primary)] pt-1">
            Contoh 1: Cek Status & Handshake Koneksi (misal di Controller atau Artisan Command):
          </p>
          <pre class="p-3 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-xs overflow-x-auto text-[11px] text-emerald-400 select-all">{laravelSnippetHandshake}</pre>

          <p class="text-[var(--text-primary)] pt-1">
            Contoh 2: Panggil Model AI untuk Chat Completion:
          </p>
          <pre class="p-3 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-xs overflow-x-auto text-[11px] text-cyan-300 select-all">{laravelSnippetChat}</pre>
        </div>
      {:else if activeCodeTab === 'curl'}
        <div class="space-y-3 font-code text-xs">
          <p class="text-[var(--text-primary)]">1. Handshake Probe:</p>
          <pre class="p-3 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-xs overflow-x-auto text-[11px] text-emerald-400 select-all">{curlSnippetHandshake(selectedClientForCode.api_key)}</pre>

          <p class="text-[var(--text-primary)] pt-2">2. Chat Completion:</p>
          <pre class="p-3 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-xs overflow-x-auto text-[11px] text-cyan-300 select-all">{curlSnippetChat(selectedClientForCode.api_key)}</pre>
        </div>
      {:else if activeCodeTab === 'python'}
        <div class="space-y-3 font-code text-xs">
          <p class="text-[var(--text-primary)]">Menggunakan library <code class="text-amber-400">httpx</code> atau <code class="text-amber-400">requests</code>:</p>
          <pre class="p-3 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-xs overflow-x-auto text-[11px] text-emerald-400 select-all">{pythonSnippet(selectedClientForCode.api_key)}</pre>
        </div>
      {/if}

      <div class="flex justify-end pt-3 border-t border-[var(--border-color)]">
        <CyberButton variant="outline" onclick={() => (showCodeModal = false)}>
          TUTUP
        </CyberButton>
      </div>
    </div>
  </div>
{/if}

<!-- ========================================================================= -->
<!-- MODAL 3: INTERACTIVE CONNECTION TESTER -->
<!-- ========================================================================= -->
{#if showTestModal && selectedClientForTest}
  <div class="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
    <div class="w-full max-w-xl border border-[var(--border-color)] bg-[var(--bg-surface)] chamfer-sm p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
      <div class="flex items-center justify-between border-b border-[var(--border-color)] pb-3">
        <div class="flex items-center gap-2">
          <Sparkles class="w-5 h-5 text-[var(--status-warning)]" />
          <div>
            <h2 class="font-hud font-bold text-base tracking-wider text-[var(--text-primary)]">
              SIMULASI HIT API // {selectedClientForTest.name.toUpperCase()}
            </h2>
            <p class="text-xs font-code text-[var(--text-muted)]">
              Uji coba request langsung menggunakan kredensial client ini.
            </p>
          </div>
        </div>
        <button
          type="button"
          onclick={() => (showTestModal = false)}
          class="text-[var(--text-muted)] hover:text-[var(--text-primary)] font-code text-sm"
        >
          ✕
        </button>
      </div>

      <!-- Test Mode Switcher -->
      <div class="grid grid-cols-2 gap-2 font-code text-xs">
        <button
          type="button"
          onclick={() => (testType = 'handshake')}
          class="p-2 border rounded-xs font-bold transition-all cursor-pointer {testType === 'handshake' ? 'border-[var(--accent-primary)] bg-[var(--accent-primary)]/10 text-[var(--accent-primary)]' : 'border-[var(--border-color)] text-[var(--text-muted)]'}"
        >
          1. Handshake & Model Discovery
        </button>
        <button
          type="button"
          onclick={() => (testType = 'chat')}
          class="p-2 border rounded-xs font-bold transition-all cursor-pointer {testType === 'chat' ? 'border-[var(--accent-primary)] bg-[var(--accent-primary)]/10 text-[var(--accent-primary)]' : 'border-[var(--border-color)] text-[var(--text-muted)]'}"
        >
          2. Chat Completion AI
        </button>
      </div>

      {#if testType === 'chat'}
        <div>
          <label for="test-prompt-input" class="block text-[var(--text-muted)] mb-1 font-code text-xs">PROMPT UJI COBA:</label>
          <input
            id="test-prompt-input"
            type="text"
            bind:value={testPrompt}
            class="w-full p-2 border border-[var(--border-color)] bg-[var(--bg-elevated)] text-[var(--text-primary)] font-code text-xs rounded-xs focus:border-[var(--accent-primary)] focus:outline-none"
          />
        </div>
      {/if}

      <div class="flex justify-end">
        <CyberButton variant="primary" onclick={runInteractiveTest} disabled={testRunning}>
          {#if testRunning}
            <Loader2 class="w-3.5 h-3.5 animate-spin mr-1.5 inline" />
            <span>MENGIRIM REQUEST...</span>
          {:else}
            <Send class="w-3.5 h-3.5 mr-1.5 inline" />
            <span>KIRIM REQUEST SEKARANG</span>
          {/if}
        </CyberButton>
      </div>

      <!-- Test Result Output -->
      {#if testError}
        <div class="p-3 border border-[var(--status-danger)]/50 bg-[var(--status-danger)]/10 text-[var(--status-danger)] font-code text-xs rounded-xs">
          <span class="font-bold">Error:</span> {testError}
        </div>
      {:else if testResult}
        <div class="space-y-1.5">
          <div class="flex items-center justify-between text-xs font-code text-[var(--status-success)]">
            <span class="flex items-center gap-1 font-bold">
              <CheckCircle2 class="w-4 h-4 inline" />
              RESPONS DITERIMA DENGAN SUKSES
            </span>
            <span>HTTP 200 OK</span>
          </div>
          <pre class="p-3 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-xs overflow-x-auto text-[11px] font-code text-emerald-300 max-h-60 overflow-y-auto">
{JSON.stringify(testResult, null, 2)}</pre>
        </div>
      {/if}
    </div>
  </div>
{/if}
