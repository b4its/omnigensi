<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api';
  import { notify } from '$lib/stores/notify.svelte';
  import CyberCard from '$lib/components/ui/CyberCard.svelte';
  import CyberButton from '$lib/components/ui/CyberButton.svelte';
  import LoadError from '$lib/components/ui/LoadError.svelte';
  import {
    FolderOpen,
    Download,
    Trash2,
    Search,
    RefreshCw,
    Loader2,
    FileText,
    HardDrive,
    AlertTriangle
  } from 'lucide-svelte';

  const PAGE_SIZE = 50;

  interface WorkspaceFile {
    filename: string;
    path: string;
    size_bytes: number;
    modified_at: string;
    content_type: string;
  }

  let files = $state<WorkspaceFile[]>([]);
  let total = $state(0);
  let totalBytes = $state(0);
  let query = $state('');
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let busy = $state<Record<string, boolean>>({});
  let offset = $state(0);
  let cleaning = $state(false);

  const hasMore = $derived(offset + files.length < total);

  function formatBytes(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
    return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
  }

  function formatDate(iso: string): string {
    try {
      return new Date(iso).toLocaleString();
    } catch {
      return iso;
    }
  }

  function iconFor(contentType: string): string {
    if (contentType.includes('pdf')) return 'PDF';
    if (contentType.includes('word') || contentType.includes('document')) return 'DOC';
    if (contentType.includes('markdown')) return 'MD';
    if (contentType.includes('json')) return 'JSON';
    if (contentType.includes('text')) return 'TXT';
    return 'FILE';
  }

  async function load(reset = true) {
    loading = true;
    loadError = null;
    try {
      if (reset) offset = 0;
      const res = await api.listFiles({
        q: query.trim() || undefined,
        limit: PAGE_SIZE,
        offset
      });
      files = reset ? res.files : [...files, ...res.files];
      total = res.total;
      totalBytes = res.total_bytes;
    } catch (err) {
      loadError = err instanceof Error ? err.message : 'Unable to list workspace files';
      if (reset) files = [];
    } finally {
      loading = false;
    }
  }

  async function download(file: WorkspaceFile) {
    if (!file.path) return;
    busy[file.path] = true;
    try {
      // Downloads need a short-lived ticket because an <a href> cannot send
      // an Authorization header.
      let ticket: string | null = null;
      try {
        const issued = await api.createStreamTicket();
        ticket = issued.ticket;
      } catch {
        /* AUTH_ENABLED=false deployments need no credential. */
      }

      const a = document.createElement('a');
      a.href = api.getFileDownloadUrl(file.path, ticket);
      a.download = file.filename;
      a.rel = 'noopener';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } catch (err) {
      notify.fromError(err, 'Download failed');
    } finally {
      busy[file.path] = false;
    }
  }

  async function remove(file: WorkspaceFile) {
    const confirmed = await notify.confirm({
      title: 'DELETE ARTIFACT',
      message: `Delete "${file.filename}" (${formatBytes(file.size_bytes)})? This cannot be undone.`,
      confirmLabel: 'DELETE'
    });
    if (!confirmed) return;

    busy[file.path] = true;
    try {
      await api.deleteFile(file.path);
      files = files.filter((f) => f.path !== file.path);
      total = Math.max(0, total - 1);
      totalBytes = Math.max(0, totalBytes - file.size_bytes);
      notify.success(`${file.filename} deleted`);
    } catch (err) {
      notify.fromError(err, 'Delete failed');
    } finally {
      busy[file.path] = false;
    }
  }

  async function cleanup(days: number) {
    const label = days === 0 ? 'ALL artifacts' : `artifacts older than ${days} day(s)`;
    const confirmed = await notify.confirm({
      title: 'CLEAN UP WORKSPACE',
      message: `Permanently delete ${label}? Agent-generated documents will be lost.`,
      confirmLabel: 'DELETE'
    });
    if (!confirmed) return;

    cleaning = true;
    try {
      const res = await api.cleanupFiles(days);
      notify.success(
        `Removed ${res.deleted} file(s), freed ${formatBytes(res.freed_bytes)}`
      );
      await load(true);
    } catch (err) {
      notify.fromError(err, 'Cleanup failed');
    } finally {
      cleaning = false;
    }
  }

  onMount(() => load(true));
</script>

<div class="space-y-6">
  <!-- Header -->
  <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-[var(--border-color)] pb-4">
    <div>
      <div class="text-[11px] font-code text-[var(--accent-primary)] uppercase tracking-wider">
        MODULE // 08
      </div>
      <h1 class="text-xl md:text-2xl font-hud font-black text-[var(--text-primary)]">
        WORKSPACE ARTIFACTS
      </h1>
      <p class="text-xs text-[var(--text-muted)] mt-1">
        Every document agents have written, with download and cleanup.
      </p>
    </div>
    <CyberButton variant="outline" size="sm" onclick={() => load(true)} disabled={loading}>
      <RefreshCw class="w-3.5 h-3.5 {loading ? 'animate-spin' : ''}" />
      <span>REFRESH</span>
    </CyberButton>
  </div>

  <!-- Summary -->
  <div class="grid grid-cols-2 sm:grid-cols-3 gap-3">
    <div class="border border-[var(--border-color)] bg-[var(--bg-surface)]/60 chamfer-sm p-3">
      <div class="text-[10px] font-code uppercase text-[var(--text-muted)]">Artifacts</div>
      <div class="text-xl font-hud font-black text-[var(--accent-primary)]">{total}</div>
    </div>
    <div class="border border-[var(--border-color)] bg-[var(--bg-surface)]/60 chamfer-sm p-3">
      <div class="text-[10px] font-code uppercase text-[var(--text-muted)]">Disk usage</div>
      <div class="text-xl font-hud font-black text-[var(--accent-primary)]">
        {formatBytes(totalBytes)}
      </div>
    </div>
    <div class="col-span-2 sm:col-span-1 border border-[var(--border-color)] bg-[var(--bg-surface)]/60 chamfer-sm p-3 flex items-center justify-between gap-2">
      <div class="min-w-0">
        <div class="text-[10px] font-code uppercase text-[var(--text-muted)]">Cleanup</div>
        <div class="text-[10px] text-[var(--text-muted)]">Removes old files</div>
      </div>
      <div class="flex flex-col gap-1 shrink-0">
        <button
          type="button"
          disabled={cleaning}
          onclick={() => cleanup(7)}
          class="px-2 py-1.5 text-[10px] font-hud border border-[var(--border-color)] text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] chamfer-sm disabled:opacity-40"
        >
          &gt;7d
        </button>
        <button
          type="button"
          disabled={cleaning}
          onclick={() => cleanup(0)}
          class="px-2 py-1.5 text-[10px] font-hud border border-[var(--status-danger)]/50 text-[var(--status-danger)] hover:bg-[var(--status-danger)]/10 chamfer-sm disabled:opacity-40"
        >
          ALL
        </button>
      </div>
    </div>
  </div>

  <!-- Search -->
  <label class="block font-code text-xs">
    <span class="relative block">
      <Search class="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
      <input
        type="text"
        bind:value={query}
        oninput={() => load(true)}
        placeholder="Filter by filename..."
        class="w-full pl-9 pr-3 py-2.5 bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]"
      />
    </span>
  </label>

  {#if loadError}
    <LoadError message={loadError} onRetry={() => load(true)} retrying={loading} />
  {:else if loading && files.length === 0}
    <div class="space-y-2">
      {#each Array(5) as _}
        <div class="h-16 border border-[var(--border-color)] bg-[var(--bg-surface)]/50 chamfer-sm animate-pulse"></div>
      {/each}
    </div>
  {:else if files.length === 0}
    <CyberCard code="WORKSPACE.00" title="NO ARTIFACTS">
      <div class="text-center py-8 space-y-3">
        <FolderOpen class="w-10 h-10 mx-auto text-[var(--text-muted)] opacity-50" />
        <p class="text-xs text-[var(--text-muted)]">
          {#if query}
            No file matches "{query}".
          {:else}
            Nothing here yet. Run a workflow whose agents write documents.
          {/if}
        </p>
      </div>
    </CyberCard>
  {:else}
    <div class="space-y-2">
      {#each files as file (file.path)}
        <div class="flex flex-wrap items-center gap-3 border border-[var(--border-color)] bg-[var(--bg-surface)]/70 chamfer-sm px-3 py-2.5">
          <span class="shrink-0 w-12 text-center text-[9px] font-code font-bold uppercase px-1.5 py-1 rounded bg-[var(--accent-primary)]/20 text-[var(--accent-primary)]">
            {iconFor(file.content_type)}
          </span>

          <div class="min-w-0 flex-1">
            <div class="text-[11px] font-code text-[var(--text-primary)] break-all">
              {file.filename}
            </div>
            <div class="text-[10px] font-code text-[var(--text-muted)]">
              {formatBytes(file.size_bytes)} · {formatDate(file.modified_at)}
            </div>
          </div>

          <div class="flex items-center gap-1 shrink-0">
            <button
              type="button"
              onclick={() => download(file)}
              disabled={busy[file.path]}
              class="p-2.5 text-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/10 rounded chamfer-sm disabled:opacity-40"
              title="Download"
              aria-label={`Download ${file.filename}`}
            >
              {#if busy[file.path]}
                <Loader2 class="w-4 h-4 animate-spin" />
              {:else}
                <Download class="w-4 h-4" />
              {/if}
            </button>
            <button
              type="button"
              onclick={() => remove(file)}
              disabled={busy[file.path]}
              class="p-2.5 text-[var(--status-danger)] hover:bg-[var(--status-danger)]/10 rounded chamfer-sm disabled:opacity-40"
              title="Delete"
              aria-label={`Delete ${file.filename}`}
            >
              <Trash2 class="w-4 h-4" />
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
          onclick={() => {
            offset += PAGE_SIZE;
            load(false);
          }}
        >
          {loading ? 'LOADING...' : 'LOAD MORE'}
        </CyberButton>
      </div>
    {/if}
  {/if}

  {#if total > 0}
    <div class="flex items-start gap-2 border border-[var(--border-color)]/60 bg-[var(--bg-elevated)]/30 px-3 py-2 text-[10px] font-code text-[var(--text-muted)]">
      <AlertTriangle class="w-3.5 h-3.5 shrink-0 mt-0.5" />
      <span>
        Artifacts live in the backend workspace. Deleting them does not remove the
        execution record that produced them.
      </span>
    </div>
  {/if}
</div>
