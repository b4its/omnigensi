<script lang="ts">
  /**
   * NASKAH STUDIO — a Word-like manuscript editor.
   *
   * A dedicated, full-stage page (the layout drops its max-width clamp for
   * `/editor`). Composes:
   *   • NaskahRibbon — tabbed ribbon with Word-style tool groups,
   *   • NaskahCanvas — the A4 paper with live zoom and page setup,
   *   • dialogs for Find & Replace, Insert Link and Insert Image,
   *   • a status bar with live word/character/page counts,
   *   • autosave to localStorage and save/export via the editor libs.
   *
   * The rich-text commands live in `$lib/editor/commands.ts`; export/import in
   * `$lib/editor/export.ts`. This file only coordinates state between them.
   */
  import { onMount } from 'svelte';
  import NaskahRibbon from '$lib/editor/NaskahRibbon.svelte';
  import NaskahCanvas from '$lib/editor/NaskahCanvas.svelte';
  import { textStats, replaceAll, insert } from '$lib/editor/commands';
  import type { TextStats } from '$lib/editor/commands';
  import { downloadDocument, printDocument, readImportedFile } from '$lib/editor/export';
  import type { ExportFormat } from '$lib/editor/export';
  import { notify } from '$lib/stores/notify.svelte';
  import { deviceBridge } from '$lib/stores/deviceBridge.svelte';
  import { X, FileText, Save, Check } from 'lucide-svelte';

  const STORAGE_KEY = 'omnigensi.naskah.draft.v1';
  const STORAGE_TITLE = 'omnigensi.naskah.title.v1';

  const DEFAULT_HTML =
    '<h1>Naskah Baru</h1>' +
    '<p>Mulai menulis di sini. Gunakan bilah pita di atas untuk memformat teks, ' +
    'menyisipkan tabel, gambar, tautan, dan lainnya — seperti di Microsoft Word.</p>' +
    '<p><br/></p>';

  let canvas = $state<NaskahCanvas>();
  let ribbon = $state<NaskahRibbon>();
  let html = $state(DEFAULT_HTML);
  let docTitle = $state('Naskah Tanpa Judul');
  let zoom = $state(100);
  let pageWidth = $state(794);
  let marginY = $state(96);
  let readingMode = $state(false);
  let darkPaper = $state(false);
  let stats = $state<TextStats>({
    words: 0,
    characters: 0,
    charactersNoSpaces: 0,
    paragraphs: 0,
    sentences: 0,
    readingMinutes: 0,
  });
  let lastSaved = $state<string | null>(null);
  let dirty = $state(false);
  let saving = $state(false);

  // Dialogs
  let showFind = $state(false);
  let showLink = $state(false);
  let showImage = $state(false);
  let findText = $state('');
  let replaceText = $state('');
  let linkUrl = $state('https://');
  let linkLabel = $state('');
  let imageUrl = $state('');
  let fileInput = $state<HTMLInputElement>();

  function getEditor(): HTMLElement | undefined {
    return canvas?.getEl();
  }

  function onChange(next: string, nextStats: TextStats) {
    html = next;
    stats = nextStats;
    dirty = true;
  }

  function refreshStats() {
    const el = getEditor();
    if (el) stats = textStats(el);
  }

  // ── Persistence ──────────────────────────────────────────────────────────
  function saveDraft() {
    try {
      localStorage.setItem(STORAGE_KEY, html);
      localStorage.setItem(STORAGE_TITLE, docTitle);
      lastSaved = new Date().toLocaleTimeString();
      dirty = false;
    } catch (e) {
      notify.fromError(e, 'Gagal menyimpan draf lokal');
    }
  }

  function loadDraft() {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      const savedTitle = localStorage.getItem(STORAGE_TITLE);
      if (saved) html = saved;
      if (savedTitle) docTitle = savedTitle;
    } catch {
      /* first run */
    }
  }

  async function saveToWorkspace() {
    saving = true;
    try {
      // Save a copy to the mounted device folder when the device bridge is
      // mounted; otherwise fall back to a browser download.
      const body = getEditor()?.innerHTML ?? html;
      const base64 = toBase64(wrapHtmlDocument(body));
      const filename = `${safeName(docTitle)}.html`;
      const res = await deviceBridge.saveAgentFileToDevice(
        filename,
        base64,
        'text/html',
        undefined
      );
      saveDraft();
      if (res.success) {
        notify.success(`Tersimpan: ${filename} (${res.mode})`);
      } else {
        notify.error('Gagal menyimpan berkas');
      }
    } catch (e) {
      notify.fromError(e, 'Gagal menyimpan');
    } finally {
      saving = false;
    }
  }

  function wrapHtmlDocument(body: string): string {
    return `<!doctype html><html lang="id"><head><meta charset="utf-8"><title>${docTitle}</title></head><body>${body}</body></html>`;
  }

  /** UTF-8 safe base64 (handles Indonesian diacritics & any Unicode). */
  function toBase64(text: string): string {
    const bytes = new TextEncoder().encode(text);
    let binary = '';
    const chunk = 0x8000;
    for (let i = 0; i < bytes.length; i += chunk) {
      binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
    }
    return btoa(binary);
  }

  function safeName(name: string): string {
    return (name || 'naskah').replace(/[^a-zA-Z0-9-_ ]/g, '').trim().replace(/\s+/g, '-') || 'naskah';
  }

  // ── Export / import ─────────────────────────────────────────────────────
  function handleExport(format: ExportFormat) {
    const el = getEditor();
    if (!el) return;
    downloadDocument(el.innerHTML, format, safeName(docTitle), docTitle);
    notify.success(`Diekspor sebagai .${format}`);
  }

  function handlePrint() {
    printDocument();
  }

  function triggerOpen() {
    fileInput?.click();
  }

  async function onFilePicked(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    try {
      const content = await readImportedFile(file);
      html = content;
      docTitle = file.name.replace(/\.[^./]+$/, '');
      refreshStats();
      dirty = true;
      notify.success(`Dibuka: ${file.name}`);
    } catch (err) {
      notify.fromError(err, 'Gagal membuka berkas');
    } finally {
      input.value = '';
    }
  }

  // ── Dialog actions ──────────────────────────────────────────────────────
  function doReplace() {
    const el = getEditor();
    if (!el || !findText) return;
    const res = replaceAll(el, findText, replaceText);
    html = el.innerHTML;
    refreshStats();
    notify.info(`${res.count} kemunculan diganti`);
  }

  function openLinkDialog() {
    const sel = window.getSelection()?.toString() ?? '';
    linkLabel = sel;
    linkUrl = 'https://';
    showLink = true;
  }
  function applyLink() {
    if (!linkUrl.trim()) return;
    insert.link(linkUrl.trim(), linkLabel.trim() || undefined);
    showLink = false;
    refreshStats();
  }

  function openImageDialog() {
    imageUrl = '';
    showImage = true;
  }
  function applyImageUrl() {
    if (!imageUrl.trim()) return;
    insert.image(imageUrl.trim(), 'gambar');
    showImage = false;
    refreshStats();
  }
  function applyImageFile(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      insert.image(String(reader.result), file.name);
      showImage = false;
      refreshStats();
    };
    reader.readAsDataURL(file);
    input.value = '';
  }

  // ── Keyboard shortcuts ──────────────────────────────────────────────────
  function onKeydown(e: KeyboardEvent) {
    const mod = e.ctrlKey || e.metaKey;
    if (!mod) return;
    const key = e.key.toLowerCase();
    if (key === 's') {
      e.preventDefault();
      saveToWorkspace();
    } else if (key === 'f') {
      e.preventDefault();
      showFind = true;
    } else if (key === 'p') {
      e.preventDefault();
      handlePrint();
    }
  }

  onMount(() => {
    loadDraft();
    // Autosave the draft every 20s while the page is open.
    const timer = setInterval(() => {
      if (dirty) saveDraft();
    }, 20000);
    return () => clearInterval(timer);
  });

  // Refresh the ribbon's pressed-state whenever a selection is made.
  function onSelectionChange() {
    ribbon?.refreshState();
  }
</script>

<svelte:window onkeydown={onKeydown} onselectionchange={onSelectionChange} />

<div class="flex flex-col h-[calc(100vh-3.5rem)]">
  <!-- Page header -->
  <div class="flex items-center justify-between gap-3 px-4 py-2 border-b border-[var(--border-color)] bg-[var(--bg-surface)]/90">
    <div class="flex items-center gap-2 min-w-0">
      <FileText class="w-4 h-4 text-[var(--accent-primary)] shrink-0" />
      <input
        bind:value={docTitle}
        oninput={() => (dirty = true)}
        class="bg-transparent border-b border-transparent focus:border-[var(--accent-primary)] text-sm font-hud text-[var(--text-primary)] px-1 py-0.5 min-w-0 w-64 md:w-96 outline-none"
        aria-label="Judul dokumen"
      />
      {#if dirty}
        <span class="text-[9px] font-code text-[var(--status-warning)]">● UNSAVED</span>
      {:else if lastSaved}
        <span class="text-[9px] font-code text-[var(--status-success)] flex items-center gap-0.5">
          <Check class="w-3 h-3" /> {lastSaved}
        </span>
      {/if}
    </div>
    <button
      type="button"
      onclick={saveToWorkspace}
      disabled={saving}
      class="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-hud border border-[var(--accent-primary)] text-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/10 chamfer-sm disabled:opacity-50"
    >
      <Save class="w-3.5 h-3.5" />
      {saving ? 'MENYIMPAN…' : 'SIMPAN'}
    </button>
  </div>

  <!-- Ribbon -->
  <NaskahRibbon
    bind:this={ribbon}
    {getEditor}
    {zoom}
    {pageWidth}
    {marginY}
    {readingMode}
    {darkPaper}
    onsave={saveToWorkspace}
    onopen={triggerOpen}
    onexport={handleExport}
    onprint={handlePrint}
    oninsertlink={openLinkDialog}
    oninsertimage={openImageDialog}
    onfind={() => (showFind = true)}
    onzoom={(z) => (zoom = z)}
    onpagemargin={(m) => (marginY = m)}
    onpagewidth={(w) => (pageWidth = w)}
    ontogglereading={() => (readingMode = !readingMode)}
    ontoggledarkpaper={() => (darkPaper = !darkPaper)}
  />

  <!-- Canvas -->
  <div class="flex-1 overflow-hidden relative">
    <NaskahCanvas
      bind:this={canvas}
      {html}
      {zoom}
      reading={readingMode}
      setup={{
        width: pageWidth,
        marginY,
        marginX: marginY,
        fontFamily: darkPaper ? "'Times New Roman', Georgia, serif" : "'Times New Roman', Georgia, serif",
      }}
      onchange={onChange}
    />
  </div>

  <!-- Status bar -->
  <div class="flex items-center justify-between gap-4 px-4 py-1.5 border-t border-[var(--border-color)] bg-[var(--bg-surface)]/90 font-code text-[10px] text-[var(--text-muted)] overflow-x-auto">
    <div class="flex items-center gap-4 whitespace-nowrap">
      <span><b class="text-[var(--text-primary)]">{stats.words.toLocaleString()}</b> kata</span>
      <span><b class="text-[var(--text-primary)]">{stats.characters.toLocaleString()}</b> karakter</span>
      <span class="hidden sm:inline"><b class="text-[var(--text-primary)]">{stats.charactersNoSpaces.toLocaleString()}</b> tanpa spasi</span>
      <span class="hidden md:inline"><b class="text-[var(--text-primary)]">{stats.paragraphs}</b> paragraf</span>
      <span class="hidden md:inline">~{stats.readingMinutes} mnt baca</span>
    </div>
    <div class="flex items-center gap-3 whitespace-nowrap">
      <span>{pageWidth === 794 ? 'A4' : pageWidth === 816 ? 'Letter' : 'A5'} · {zoom}%</span>
      {#if deviceBridge.directoryHandle}
        <span class="text-[var(--status-success)]">DISK: {deviceBridge.mountedFolderName}</span>
      {/if}
    </div>
  </div>
</div>

<!-- Hidden file input for Open -->
<input
  bind:this={fileInput}
  type="file"
  accept=".html,.htm,.md,.txt,.doc,.docx"
  onchange={onFilePicked}
  class="hidden"
/>

<!-- Find & Replace dialog -->
{#if showFind}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" role="presentation" onpointerdown={() => (showFind = false)}>
    <div class="w-full max-w-md border border-[var(--border-color)] bg-[var(--bg-surface)] chamfer p-4" onpointerdown={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label="Cari dan ganti" tabindex="-1">
      <div class="flex items-center justify-between mb-3">
        <h3 class="font-hud text-sm text-[var(--text-primary)]">CARI & GANTI</h3>
        <button type="button" onclick={() => (showFind = false)} class="text-[var(--text-muted)] hover:text-[var(--text-primary)]"><X class="w-4 h-4" /></button>
      </div>
      <label for="naskah-find" class="block text-[11px] font-code text-[var(--text-muted)] mb-1">Cari</label>
      <input id="naskah-find" bind:value={findText} class="w-full mb-3 px-2 py-1.5 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm text-sm text-[var(--text-primary)] outline-none" placeholder="teks yang dicari" />
      <label for="naskah-replace" class="block text-[11px] font-code text-[var(--text-muted)] mb-1">Ganti dengan</label>
      <input id="naskah-replace" bind:value={replaceText} class="w-full mb-4 px-2 py-1.5 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm text-sm text-[var(--text-primary)] outline-none" placeholder="teks pengganti" />
      <div class="flex justify-end gap-2">
        <button type="button" onclick={() => (showFind = false)} class="px-3 py-1.5 text-[11px] font-hud border border-[var(--border-color)] text-[var(--text-muted)] chamfer-sm">TUTUP</button>
        <button type="button" onclick={doReplace} class="px-3 py-1.5 text-[11px] font-hud bg-[var(--accent-primary)] text-[var(--on-accent)] chamfer-sm">GANTI SEMUA</button>
      </div>
    </div>
  </div>
{/if}

<!-- Insert link dialog -->
{#if showLink}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" role="presentation" onpointerdown={() => (showLink = false)}>
    <div class="w-full max-w-md border border-[var(--border-color)] bg-[var(--bg-surface)] chamfer p-4" onpointerdown={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label="Sisipkan tautan" tabindex="-1">
      <div class="flex items-center justify-between mb-3">
        <h3 class="font-hud text-sm text-[var(--text-primary)]">SISIPKAN TAUTAN</h3>
        <button type="button" onclick={() => (showLink = false)} class="text-[var(--text-muted)] hover:text-[var(--text-primary)]"><X class="w-4 h-4" /></button>
      </div>
      <label for="naskah-link-url" class="block text-[11px] font-code text-[var(--text-muted)] mb-1">URL</label>
      <input id="naskah-link-url" bind:value={linkUrl} class="w-full mb-3 px-2 py-1.5 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm text-sm text-[var(--text-primary)] outline-none" placeholder="https://" />
      <label for="naskah-link-label" class="block text-[11px] font-code text-[var(--text-muted)] mb-1">Teks tampilan (opsional)</label>
      <input id="naskah-link-label" bind:value={linkLabel} class="w-full mb-4 px-2 py-1.5 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm text-sm text-[var(--text-primary)] outline-none" placeholder="teks tautan" />
      <div class="flex justify-end gap-2">
        <button type="button" onclick={() => (showLink = false)} class="px-3 py-1.5 text-[11px] font-hud border border-[var(--border-color)] text-[var(--text-muted)] chamfer-sm">BATAL</button>
        <button type="button" onclick={applyLink} class="px-3 py-1.5 text-[11px] font-hud bg-[var(--accent-primary)] text-[var(--on-accent)] chamfer-sm">SISIPKAN</button>
      </div>
    </div>
  </div>
{/if}

<!-- Insert image dialog -->
{#if showImage}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" role="presentation" onpointerdown={() => (showImage = false)}>
    <div class="w-full max-w-md border border-[var(--border-color)] bg-[var(--bg-surface)] chamfer p-4" onpointerdown={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label="Sisipkan gambar" tabindex="-1">
      <div class="flex items-center justify-between mb-3">
        <h3 class="font-hud text-sm text-[var(--text-primary)]">SISIPKAN GAMBAR</h3>
        <button type="button" onclick={() => (showImage = false)} class="text-[var(--text-muted)] hover:text-[var(--text-primary)]"><X class="w-4 h-4" /></button>
      </div>
      <label for="naskah-image-url" class="block text-[11px] font-code text-[var(--text-muted)] mb-1">URL gambar</label>
      <div class="flex gap-2 mb-3">
        <input id="naskah-image-url" bind:value={imageUrl} class="flex-1 px-2 py-1.5 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm text-sm text-[var(--text-primary)] outline-none" placeholder="https://…" />
        <button type="button" onclick={applyImageUrl} class="px-3 py-1.5 text-[11px] font-hud bg-[var(--accent-primary)] text-[var(--on-accent)] chamfer-sm">OK</button>
      </div>
      <div class="text-center text-[10px] font-code text-[var(--text-muted)] mb-2">— atau —</div>
      <label class="block">
        <span class="inline-block w-full text-center px-3 py-2 text-[11px] font-hud border border-[var(--border-color)] text-[var(--text-primary)] chamfer-sm cursor-pointer hover:bg-[var(--bg-elevated)]">
          PILIH BERKAS GAMBAR
        </span>
        <input type="file" accept="image/*" onchange={applyImageFile} class="hidden" />
      </label>
    </div>
  </div>
{/if}
