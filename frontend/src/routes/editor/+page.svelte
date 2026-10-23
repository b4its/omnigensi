<script lang="ts">
  /**
   * NASKAH STUDIO — a Word/Wordcraft-like manuscript editor.
   *
   * A dedicated, full-stage page. Composes:
   *   • NaskahRibbon — tabbed ribbon (Home → View, plus Table and Picture),
   *   • NaskahCanvas — the A4 paper with page setup, watermarks and headers,
   *   • side panes for navigation, styles and review,
   *   • the File backstage, the Tell-Me command search and ~25 dialogs,
   *   • a status bar with live word/character/page counts,
   *   • autosave, crash recovery and a version history.
   *
   * The heavy lifting lives in `$lib/editor/*` (formatting, references, review,
   * mail merge, file formats, persistence); this file only coordinates state.
   */
  import { onMount } from 'svelte';
  import NaskahRibbon from '$lib/editor/NaskahRibbon.svelte';
  import NaskahCanvas from '$lib/editor/NaskahCanvas.svelte';
  import StyleGallery from '$lib/editor/StyleGallery.svelte';
  import StyleGalleryPane from '$lib/editor/StylesPane.svelte';
  import FileBackstage from '$lib/editor/FileBackstage.svelte';
  import NavigationPane from '$lib/editor/NavigationPane.svelte';
  import ReviewPane from '$lib/editor/ReviewPane.svelte';
  import type { ReviewTab } from '$lib/editor/ReviewPane.svelte';
  import MailingsPane from '$lib/editor/MailingsPane.svelte';
  import CommandSearch from '$lib/editor/CommandSearch.svelte';
  import EditorDialogs from '$lib/editor/EditorDialogs.svelte';
  import type { DialogKind } from '$lib/editor/EditorDialogs.svelte';

  import { textStats, replaceAll, insert, findNext, countMatches, selectionStats, currentBlock, para } from '$lib/editor/commands';
  import type { TextStats, Align } from '$lib/editor/commands';
  import { charFx, applyFontDialog } from '$lib/editor/charFx';
  import { paraFx, textToTable } from '$lib/editor/paraFx';
  import { tableTools, pictureTools } from '$lib/editor/tableTools';
  import { applyStyle } from '$lib/editor/styles';
  import type { DocStyle } from '$lib/editor/styles';
  import { readState, emptyState } from '$lib/editor/editorState';
  import type { EditorStateSnapshot } from '$lib/editor/editorState';
  import { collectHeadings } from '$lib/editor/headings';
  import { renderToc } from '$lib/editor/headings';
  import {
    defaultSection,
    loadSection,
    MARGIN_PRESETS,
    saveSection,
    spacingMultiplier,
  } from '$lib/editor/pageSetup';
  import type { SectionSetup } from '$lib/editor/pageSetup';
  import {
    captionMarkup,
    ensureNotesList,
    noteMarkup,
    renumberCaptions,
    renumberNotes,
    bibliographyMarkup,
    formatSource,
    insertCitation,
    loadSources,
    saveSources,
    tableOfFigures,
  } from '$lib/editor/references';
  import type { Source, CitationStyle } from '$lib/editor/references';
  import * as review from '$lib/editor/review';
  import type { Comment, InspectionFinding } from '$lib/editor/review';
  import { parseCsv, mergePlaceholder, mergeAll, labelSheet } from '$lib/editor/mailings';
  import {
    HORIZONTAL_LINES,
    LIST_GALLERY,
    DEFAULT_AUTOTEXT,
    fieldMarkup,
    fontwork,
    horizontalLine,
    listOf,
    textFrame,
  } from '$lib/editor/loBlocks';
  import type { FieldKind } from '$lib/editor/loBlocks';
  import { breakMarkup, pageFieldMarkup } from '$lib/editor/loLayout';
  import type { NumberingContext } from '$lib/editor/loLayout';
  import { linkMarkup, validateLink } from '$lib/editor/loLinks';
  import type { Recipients, LayoutName } from '$lib/editor/mailings';
  import { downloadDocument, printDocument, readImportedFile } from '$lib/editor/export';
  import type { ExportFormat } from '$lib/editor/export';
  import { TEMPLATES } from '$lib/editor/fileFormats';
  import type { Template } from '$lib/editor/fileFormats';
  import {
    loadDraft,
    saveDraft,
    stashRecovery,
    listRecovery,
    listVersions,
    pushVersion,
    loadProperties,
    saveProperties,
    DEFAULT_PROPERTIES,
  } from '$lib/editor/persistence';
  import type { DocProperties, Version, Draft } from '$lib/editor/persistence';
  import { coverPage, quickTable, textBox, wordArt, signatureLine, dropCap, chart as chartBlock, smartArt, equation, shape } from '$lib/editor/insertBlocks';
  import { dateTimeStamp, formatNumber } from '$lib/editor/dates';
  import { commandRegistry } from '$lib/editor/commandRegistry';
  import type { Command } from '$lib/editor/commandRegistry';
  import { notify } from '$lib/stores/notify.svelte';
  import { deviceBridge } from '$lib/stores/deviceBridge.svelte';
  import { FileText, Save, Check, ChevronLeft as ChevLeft } from 'lucide-svelte';

  const DEFAULT_HTML =
    '<h1>Naskah Baru</h1>' +
    '<p>Mulai menulis di sini. Gunakan bilah pita di atas untuk memformat teks, ' +
    'menyisipkan tabel, gambar, tautan, daftar isi, catatan kaki, sitasi dan lainnya ' +
    '— seperti di Microsoft Word.</p>' +
    '<p><br/></p>';

  let canvas = $state<NaskahCanvas>();
  let html = $state(DEFAULT_HTML);
  let docTitle = $state('Naskah Tanpa Judul');
  let properties = $state<DocProperties>({ ...DEFAULT_PROPERTIES });
  let section = $state<SectionSetup>(defaultSection());
  let zoom = $state(100);
  let readingMode = $state(false);
  let pageView = $state<1 | 2>(1);
  let showRuler = $state(true);
  let showMarks = $state(false);
  let showNavPane = $state(false);
  let showStylesPane = $state(false);
  let showFileBackstage = $state(false);
  let showCommandSearch = $state(false);
  let showMailings = $state(false);
  let reviewOpen = $state(false);
  let reviewTab = $state<ReviewTab>('comments');
  let navRevision = $state(0);
  let lastSaved = $state<string | null>(null);
  let dirty = $state(false);
  let saving = $state(false);
  let trackingOn = $state(false);

  let editorState = $state<EditorStateSnapshot>(emptyState());
  let stats = $state<TextStats>({ words: 0, characters: 0, charactersNoSpaces: 0, paragraphs: 0, sentences: 0, readingMinutes: 0 });
  let selStats = $state<{ words: number; characters: number }>({ words: 0, characters: 0 });

  // Dialogs
  let dialog = $state<DialogKind | null>(null);
  let findText = $state('');
  let replaceText = $state('');
  let matchCount = $state(0);
  let sources = $state<Source[]>([]);
  let citationStyle = $state<CitationStyle>('APA');
  let comments = $state<Comment[]>([]);
  let spelling = $state<review.SpellingIssue[]>([]);
  let inspector = $state<InspectionFinding[]>([]);
  let thesaurusWord = $state('');
  let thesaurusWords = $state<string[]>([]);
  let versions = $state<Version[]>([]);
  let recovery = $state<Draft[]>([]);
  let recipients = $state<Recipients>({ fields: [], rows: [] });
  let activeRecord = $state(0);
  let mergeHighlight = $state(true);

  let fileInput = $state<HTMLInputElement>();
  let mailInput = $state<HTMLInputElement>();

  function getEditor(): HTMLElement | undefined {
    return canvas?.getEl();
  }

  // ── State refresh ───────────────────────────────────────────────────────
  function refreshAll() {
    editorState = readState();
    navRevision++;
  }

  function onChange(next: string, nextStats: TextStats) {
    html = next;
    stats = nextStats;
    dirty = true;
    selStats = selectionStats();
    refreshAll();
    autosaver.touch();
  }

  function refreshStats() {
    const el = getEditor();
    if (el) {
      stats = textStats(el);
      html = el.innerHTML;
    }
    refreshAll();
  }

  // ── Autosave ────────────────────────────────────────────────────────────
  const autosaver = {
    touch: () => {
      dirty = true;
    },
    flush: () => {
      saveDraft(getEditor()?.innerHTML ?? html, docTitle);
      dirty = false;
    },
  };

  function saveDraftNow() {
    saveDraft(getEditor()?.innerHTML ?? html, docTitle);
    lastSaved = new Date().toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' });
    dirty = false;
  }

  async function saveToWorkspace() {
    saving = true;
    try {
      const body = getEditor()?.innerHTML ?? html;
      pushVersion(body, docTitle);
      saveDraft(body, docTitle);
      const filename = `${safeName(docTitle)}.html`;
      const base64 = toBase64(wrapHtmlDocument(body));
      const res = await deviceBridge.saveAgentFileToDevice(filename, base64, 'text/html', undefined);
      // The local autosave copy is the source of truth even when the device
      // bridge declines to write (no folder mounted / mobile browser).
      saveDraftNow();
      versions = listVersions();
      if (res.success) notify.success(`Tersimpan: ${filename} (${res.mode})`);
      else notify.error('Gagal menyimpan berkas');
    } catch (e) {
      notify.fromError(e, 'Gagal menyimpan');
    } finally {
      saving = false;
    }
  }

  function wrapHtmlDocument(body: string): string {
    return `<!doctype html><html lang="id"><head><meta charset="utf-8"><title>${docTitle}</title></head><body>${body}</body></html>`;
  }
  function toBase64(text: string): string {
    const bytes = new TextEncoder().encode(text);
    let binary = '';
    const chunk = 0x8000;
    for (let i = 0; i < bytes.length; i += chunk) binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
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
      stashRecovery(getEditor()?.innerHTML ?? html, docTitle);
      const content = await readImportedFile(file);
      html = content;
      docTitle = file.name.replace(/\.[^./]+$/, '');
      properties.title = docTitle;
      refreshStats();
      dirty = true;
      notify.success(`Dibuka: ${file.name}`);
    } catch (err) {
      notify.fromError(err, 'Gagal membuka berkas');
    } finally {
      input.value = '';
    }
  }

  function newFromTemplate(tpl: Template) {
    stashRecovery(getEditor()?.innerHTML ?? html, docTitle);
    html = tpl.html;
    docTitle = tpl.label;
    properties.title = tpl.label;
    refreshStats();
    showFileBackstage = false;
    dirty = true;
    notify.info(`Dokumen baru: ${tpl.label}`);
  }

  // ── Find & replace ──────────────────────────────────────────────────────
  function doReplace() {
    const el = getEditor();
    if (!el || !findText) return;
    const res = replaceAll(el, findText, replaceText);
    refreshStats();
    matchCount = countMatches(el, findText);
    notify.info(`${res.count} kemunculan diganti`);
  }
  function doFindNext(backward = false) {
    const el = getEditor();
    if (!el || !findText) return;
    if (!findNext(el, findText, backward)) notify.warning(`Tidak ada "${findText}"`);
  }

  // ── Dialog submit dispatcher ────────────────────────────────────────────
  function submitDialog(kind: DialogKind, payload: Record<string, unknown>) {
    const el = getEditor();
    switch (kind) {
      case 'link':
        insert.link(String(payload.href), String(payload.label) || undefined);
        dialog = null;
        break;
      case 'image':
        insert.image(String(payload.src), String(payload.alt ?? ''));
        dialog = null;
        break;
      case 'font':
        applyFontDialog(payload as never);
        dialog = null;
        break;
      case 'paragraph': {
        const p = payload as { align: Align; indentLeft: number; lineSpacing: string; spacingBefore: number; spacingAfter: number };
        para.align(p.align);
        paraFx.leftIndent(p.indentLeft);
        paraFx.lineSpacing(p.lineSpacing);
        paraFx.spaceBefore(p.spacingBefore);
        paraFx.spaceAfter(p.spacingAfter);
        dialog = null;
        break;
      }
      case 'pagesetup': {
        const p = payload as Record<string, never>;
        section = {
          ...section,
          paper: p['paper'] as never,
          orientation: p['orientation'] as never,
          margins: { top: p['mTop'] as never, bottom: p['mBottom'] as never, left: p['mLeft'] as never, right: p['mRight'] as never },
          header: String(p['headerText'] ?? ''),
          footer: String(p['footerText'] ?? ''),
          showPageNumbers: Boolean(p['showPageNumbers']),
          pageNumberFormat: p['pageNumberFormat'] as never,
          pageBorder: { ...section.pageBorder, on: Boolean(p['pageBorder']), color: String(p['pageBorderColor'] ?? section.pageBorder.color) },
          lineNumbers: Boolean(p['lineNumbers']),
          hyphenation: Boolean(p['hyphenation']),
        };
        saveSection(section);
        dialog = null;
        break;
      }
      case 'watermark':
        section = {
          ...section,
          watermark: payload.remove ? null : { text: String(payload.text), opacity: Number(payload.opacity), rotate: Number(payload.rotate), color: '#888888' },
        };
        saveSection(section);
        dialog = null;
        break;
      case 'cover':
        insert.html(coverPage(String(payload.title), String(payload.subtitle), payload.template as never));
        dialog = null;
        break;
      case 'symbol':
        insert.text(String(payload.char));
        dialog = null;
        break;
      case 'equation':
        insert.html(equation(String(payload.latex)));
        dialog = null;
        break;
      case 'quickparts': {
        const what = String(payload.what);
        const parts: Record<string, string> = {
          address: '<p>Kepada Yth.<br/>Bapak/Ibu ______________<br/>Alamat<br/>Kota</p>',
          greeting: '<p>Dengan hormat,</p>',
          closing: '<p style="text-align:right">Hormat kami,</p>',
          signature: signatureLine('Nama Lengkap', 'Jabatan'),
          date: `<p>${dateTimeStamp()}</p>`,
          title: `<p style="font-weight:700;font-size:14pt">${docTitle}</p>`,
        };
        insert.html(parts[what] ?? '');
        dialog = null;
        break;
      }
      case 'chart':
        insert.html(chartBlock(payload.kind as never, payload.values as number[]));
        dialog = null;
        break;
      case 'smartart':
        insert.html(smartArt(payload.steps as string[]));
        dialog = null;
        break;
      case 'caption':
        insert.html(captionMarkup(String(payload.label), String(payload.text)));
        if (el) renumberCaptions(el);
        dialog = null;
        break;
      case 'crossref':
        insert.html(`<a href="#${payload.target}" style="color:inherit;text-decoration:underline dotted">${payload.label}</a>`);
        dialog = null;
        break;
      case 'comment': {
        const id = review.markComment(properties.author || 'Penulis', String(payload.text));
        if (id && el) {
          comments = review.collectComments(el);
          reviewOpen = true;
          reviewTab = 'comments';
        } else {
          notify.warning('Pilih teks terlebih dahulu untuk dikomentari.');
        }
        dialog = null;
        break;
      }
      case 'pagecolor':
        section = { ...section, pageColor: String(payload.color) };
        saveSection(section);
        dialog = null;
        break;
      case 'textbox':
        insert.html(textBox(String(payload.text)));
        dialog = null;
        break;
      case 'wordart':
        insert.html(wordArt(String(payload.text)));
        dialog = null;
        break;
      case 'signature':
        insert.html(signatureLine(String(payload.name), String(payload.title)));
        dialog = null;
        break;
      case 'tableborders':
        tableTools.borders(String(payload.spec));
        dialog = null;
        break;
      case 'pictureformat': {
        const activeImg = document.querySelector<HTMLImageElement>('.naskah-content img:focus, .naskah-content img:hover');
        if (!activeImg) {
          notify.warning('Klik gambar terlebih dahulu.');
          break;
        }
        if (payload.reset) pictureTools.reset(activeImg);
        else {
          if (payload.width) pictureTools.resize(activeImg, Number(payload.width));
          if (payload.rotate) pictureTools.rotate(activeImg, Number(payload.rotate));
          if (payload.alt) pictureTools.alt(activeImg, String(payload.alt));
          if (payload.wrap) pictureTools.wrap(activeImg, payload.wrap as never);
        }
        dialog = null;
        break;
      }
      case 'bookmark':
        insert.html(`<a id="${safeAnchor(String(payload.name))}" data-object="bookmark"></a>`);
        dialog = null;
        break;
      case 'autotext': {
        const entry = DEFAULT_AUTOTEXT.find((a) => a.key === payload.key);
        if (entry) insert.html(entry.html);
        dialog = null;
        break;
      }
      case 'field':
        insertWriterField(payload.field as FieldKind);
        dialog = null;
        break;
      case 'textframe':
        insert.html(
          textFrame(String(payload.text), {
            anchor: payload.anchor as never,
            wrap: payload.wrap as never,
            width: '240px',
            align: 'left',
          })
        );
        dialog = null;
        break;
      case 'hyperwriter': {
        const model = {
          kind: payload.kind as never,
          text: String(payload.text ?? ''),
          target: String(payload.target ?? ''),
          name: String(payload.name ?? ''),
          newWindow: true,
          bookmark: String(payload.bookmark ?? ''),
        };
        const problem = validateLink(model);
        if (problem) {
          notify.warning(problem);
          break;
        }
        insert.html(linkMarkup(model));
        dialog = null;
        break;
      }
      case 'fontwork':
        insert.html(fontwork(String(payload.text), payload.style as never));
        dialog = null;
        break;
    }
    refreshStats();
  }

  function safeAnchor(s: string): string {
    return (s || 'penanda').replace(/[^\w-]/g, '-');
  }

  // ── Notes / bibliography / index ────────────────────────────────────────
  function insertNote(kind: 'footnote' | 'endnote') {
    const el = getEditor();
    if (!el) return;
    const { anchor, block } = noteMarkup('[tulis catatan di sini]', kind);
    insert.html(anchor);
    const list = ensureNotesList(el, kind);
    list.insertAdjacentHTML('beforeend', block);
    renumberNotes(el);
    refreshStats();
  }

  function insertBibliography() {
    const style = citationStyle;
    insert.html(bibliographyMarkup(sources, style));
    dialog = null;
    refreshStats();
  }

  // ── TOC / TOF / Index ───────────────────────────────────────────────────
  function insertToc() {
    const el = getEditor();
    if (!el) return;
    insert.html(renderToc(collectHeadings(el)));
    refreshStats();
  }
  function insertTableOfFigures() {
    const el = getEditor();
    if (!el) return;
    insert.html(tableOfFigures(el));
    refreshStats();
  }
  function insertIndex() {
    insert.html('<div data-object="index"><h2>Indeks</h2><p style="color:#888">[Indeks dibangun dari entri yang ditandai]</p></div><p><br/></p>');
    refreshStats();
  }

  // ── Review actions ──────────────────────────────────────────────────────
  function toggleTracking() {
    trackingOn = !trackingOn;
    review.tracking.enabled = trackingOn;
    review.tracking.author = properties.author || 'Penulis';
    notify.info(trackingOn ? 'Lacak perubahan: AKTIF' : 'Lacak perubahan: NONAKTIF');
  }

  function runSpellcheck() {
    const el = getEditor();
    if (!el) return;
    spelling = review.spellCheck(el.innerText);
    reviewOpen = true;
    reviewTab = 'spelling';
    notify.info(`${spelling.length} kata ditandai`);
  }

  function openThesaurus() {
    const sel = window.getSelection()?.toString().trim() ?? '';
    thesaurusWord = sel.split(/\s+/)[0] ?? '';
    thesaurusWords = review.lookupSynonyms(thesaurusWord);
    reviewOpen = true;
    reviewTab = 'thesaurus';
  }

  function applySynonym(word: string) {
    document.execCommand('insertText', false, word);
    refreshStats();
  }

  function replaceSpelling(word: string, withWord: string) {
    const el = getEditor();
    if (!el) return;
    replaceAll(el, word, withWord);
    spelling = review.spellCheck(el.innerText);
    refreshStats();
  }

  function runInspect() {
    const el = getEditor();
    if (!el) return;
    inspector = review.inspectDocument(el);
    reviewOpen = true;
    reviewTab = 'inspect';
    dialog = 'inspect';
  }

  function readAloud() {
    const el = getEditor();
    if (!el) return;
    if (!review.readAloud(el.innerText)) notify.warning('Peramban tidak mendukung baca nyaring.');
  }

  // ── Mail merge ──────────────────────────────────────────────────────────
  function triggerMailUpload() {
    mailInput?.click();
  }
  async function onMailPicked(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    recipients = parseCsv(await file.text());
    activeRecord = 0;
    notify.success(`${recipients.rows.length} penerima dimuat (${recipients.fields.length} kolom)`);
    input.value = '';
  }
  function insertMergeField(field: string) {
    insert.text(mergePlaceholder(field));
    refreshStats();
  }
  function mergeAllRecords() {
    const el = getEditor();
    if (!el) return;
    const merged = mergeAll(el.innerHTML, recipients);
    stashRecovery(el.innerHTML, docTitle);
    html = merged;
    showMailings = false;
    refreshStats();
    notify.success(`Digabung menjadi ${recipients.rows.length} dokumen.`);
  }
  function insertLabels(layout: LayoutName) {
    const el = getEditor();
    if (!el) return;
    insert.html(labelSheet(el.innerHTML, recipients, layout));
    refreshStats();
  }

  // ── Command registry (Tell-Me) ──────────────────────────────────────────
  function buildRegistry() {
    const cmds: Command[] = [];
    const add = (id: string, label: string, tab: string, group: string, run: () => void, extra: Partial<Command> = {}) =>
      cmds.push({ id, label, tab, group, run, ...extra });
    add('file.save', 'Simpan dokumen', 'File', 'Backstage', saveToWorkspace, { keywords: ['save', 'simpan'], shortcut: 'Ctrl+S' });
    add('file.open', 'Buka dokumen', 'File', 'Backstage', triggerOpen, { keywords: ['open', 'buka'] });
    add('file.print', 'Cetak / PDF', 'File', 'Backstage', handlePrint, { keywords: ['print', 'cetak', 'pdf'], shortcut: 'Ctrl+P' });
    add('file.new', 'Dokumen baru dari template', 'File', 'Backstage', () => (showFileBackstage = true), { keywords: ['new', 'template'] });
    add('edit.find', 'Cari & ganti', 'Home', 'Penyuntingan', () => (dialog = 'find'), { keywords: ['find', 'cari', 'replace'], shortcut: 'Ctrl+F' });
    add('format.bold', 'Tebal', 'Home', 'Font', () => document.execCommand('bold'), { keywords: ['bold', 'tebal'], shortcut: 'Ctrl+B' });
    add('format.italic', 'Miring', 'Home', 'Font', () => document.execCommand('italic'), { keywords: ['italic', 'miring'] });
    add('format.underline', 'Garis bawah', 'Home', 'Font', () => document.execCommand('underline'), { keywords: ['underline'] });
    add('format.smallCaps', 'Kapital kecil', 'Home', 'Font', charFx.smallCaps);
    add('format.allCaps', 'Semua kapital', 'Home', 'Font', charFx.allCaps);
    add('format.highlight', 'Sorotan', 'Home', 'Font', () => document.execCommand('hiliteColor', false, '#FFEB3B'));
    add('format.clear', 'Hapus format', 'Home', 'Font', () => document.execCommand('removeFormat'));
    add('para.alignLeft', 'Rata kiri', 'Home', 'Paragraf', () => document.execCommand('justifyLeft'));
    add('para.justify', 'Rata kanan-kiri', 'Home', 'Paragraf', () => document.execCommand('justifyFull'));
    add('para.bullets', 'Daftar butir', 'Home', 'Paragraf', () => document.execCommand('insertUnorderedList'));
    add('para.numbering', 'Daftar bernomor', 'Home', 'Paragraf', () => document.execCommand('insertOrderedList'));
    add('styles.pane', 'Panel gaya', 'Home', 'Gaya', () => (showStylesPane = !showStylesPane));
    add('insert.table', 'Sisipkan tabel', 'Insert', 'Tabel', () => insert.table(3, 3));
    add('insert.picture', 'Sisipkan gambar', 'Insert', 'Ilustrasi', () => (dialog = 'image'));
    add('insert.link', 'Sisipkan tautan', 'Insert', 'Tautan', () => (dialog = 'link'), { shortcut: 'Ctrl+K' });
    add('insert.chart', 'Sisipkan diagram', 'Insert', 'Ilustrasi', () => (dialog = 'chart'));
    add('insert.smartArt', 'Sisipkan SmartArt', 'Insert', 'Ilustrasi', () => (dialog = 'smartart'));
    add('insert.equation', 'Sisipkan persamaan', 'Insert', 'Simbol', () => (dialog = 'equation'));
    add('insert.coverPage', 'Sampul', 'Insert', 'Halaman', () => (dialog = 'cover'));
    add('insert.textBox', 'Kotak teks', 'Insert', 'Teks', () => (dialog = 'textbox'));
    add('insert.wordArt', 'WordArt', 'Insert', 'Teks', () => (dialog = 'wordart'));
    add('insert.dropCap', 'Drop cap', 'Insert', 'Teks', () => { insert.html(dropCap(3)); });
    add('design.watermark', 'Tanda air', 'Design', 'Latar Halaman', () => (dialog = 'watermark'));
    add('layout.pageSetup', 'Penyiapan halaman', 'Layout', 'Penyiapan Halaman', () => (dialog = 'pagesetup'));
    add('layout.margins', 'Margin normal', 'Layout', 'Penyiapan Halaman', () => applyMargin('Normal'));
    add('references.toc', 'Daftar isi', 'References', 'Daftar Isi', insertToc, { keywords: ['toc', 'daftar isi'] });
    add('references.footnote', 'Catatan kaki', 'References', 'Catatan Kaki', () => insertNote('footnote'));
    add('references.endnote', 'Catatan akhir', 'References', 'Catatan Kaki', () => insertNote('endnote'));
    add('references.citation', 'Sitasi', 'References', 'Sitasi', () => (dialog = 'citations'));
    add('references.caption', 'Keterangan', 'References', 'Keterangan', () => (dialog = 'caption'));
    add('review.spelling', 'Ejaan', 'Review', 'Pemeriksaan', runSpellcheck);
    add('review.thesaurus', 'Tesisaurus', 'Review', 'Pemeriksaan', openThesaurus);
    add('review.wordCount', 'Hitung kata', 'Review', 'Pemeriksaan', () => { dialog = 'wordcount'; });
    add('review.newComment', 'Komentar baru', 'Review', 'Komentar', () => { dialog = 'comment'; });
    add('review.trackChanges', 'Lacak perubahan', 'Review', 'Lacak Perubahan', toggleTracking);
    add('review.acceptAll', 'Terima semua perubahan', 'Review', 'Lacak Perubahan', acceptAllRevisions);
    add('review.rejectAll', 'Tolak semua perubahan', 'Review', 'Lacak Perubahan', rejectAllRevisions);
    add('view.readMode', 'Mode baca', 'View', 'Tampilan', () => (readingMode = !readingMode));
    // LibreOffice Writer commands
    add('tools.autotext', 'AutoText', 'Format', 'Gaya & AutoText', () => (dialog = 'autotext'), { keywords: ['autotext', 'blok'] });
    add('insert.field', 'Sisipkan field', 'Format', 'Gaya & AutoText', () => (dialog = 'field'), { keywords: ['field', 'medan'] });
    add('insert.pageNumber', 'Nomor halaman di teks', 'Format', 'Gaya & AutoText', insertPageField);
    add('insert.textFrame', 'Teks berjalan (bingkai)', 'Format', 'Bingkai & Objek', () => (dialog = 'textframe'), { keywords: ['bingkai', 'frame'] });
    add('insert.fontwork', 'Fontwork', 'Format', 'Bingkai & Objek', () => (dialog = 'fontwork'));
    add('insert.hyperlinkWriter', 'Hyperlink Writer', 'Format', 'Bingkai & Objek', () => (dialog = 'hyperwriter'));
    add('layout.breaks', 'Pemisah halaman/kolom/bagian', 'Format', 'Sisipkan', () => {
      insert.html(breakMarkup('page'));
      refreshStats();
    }, {
      keywords: ['break', 'pemisah'],
    });
    add('view.navigationPane', 'Panel navigasi', 'View', 'Tampilan', () => (showNavPane = !showNavPane));
    add('view.ruler', 'Penggaris', 'View', 'Tampilan', () => (showRuler = !showRuler));
    add('view.marks', 'Tanda format', 'View', 'Tampilan', () => (showMarks = !showMarks));
    add('mailings.start', 'Mail merge', 'Mailings', 'Mail Merge', () => (showMailings = !showMailings));
    commandRegistry.registerAll(cmds);
  }

  function acceptAllRevisions() {
    const el = getEditor();
    if (!el) return;
    const n = review.acceptAll(el);
    refreshStats();
    notify.info(`${n} revisi diterima`);
  }
  function rejectAllRevisions() {
    const el = getEditor();
    if (!el) return;
    const n = review.rejectAll(el);
    refreshStats();
    notify.info(`${n} revisi ditolak`);
  }

  // ── Page setup helpers ──────────────────────────────────────────────────
  function applyMargin(preset: string) {
    const m = MARGIN_PRESETS[preset] ?? MARGIN_PRESETS.Normal;
    section = { ...section, margins: { ...m } };
    saveSection(section);
  }
  function toggleOrientation() {
    section = { ...section, orientation: section.orientation === 'portrait' ? 'landscape' : 'portrait' };
    saveSection(section);
  }
  function setColumns(n: number) {
    section = { ...section, columns: n };
    saveSection(section);
  }
  function setPageColor(color: string) {
    section = { ...section, pageColor: color };
    saveSection(section);
  }
  function setSpacing(preset: SectionSetup['paragraphSpacing']) {
    section = { ...section, paragraphSpacing: preset };
    saveSection(section);
  }

  // ── Writer-scoped insertions ────────────────────────────────────────────
  function numberingContext(): NumberingContext {
    return { format: section.pageNumberFormat, start: 1 };
  }
  function insertPageField() {
    insert.html(pageFieldMarkup(numberingContext(), 1));
    refreshStats();
  }
  function insertListFromGallery(key: string) {
    const style = LIST_GALLERY.find((g) => g.key === key) ?? LIST_GALLERY[0];
    insert.html(listOf(style));
    refreshStats();
  }
  function insertWriterField(kind: FieldKind) {
    insert.html(fieldMarkup(kind, { author: properties.author, title: docTitle, wordCount: stats.words }));
    refreshStats();
  }
  function applyDocStyle(style: DocStyle) {
    applyStyle(style);
    refreshStats();
  }
  // Track typing when tracking is enabled.
  function maybeTrackInsert(e: KeyboardEvent) {
    if (!trackingOn) return;
    if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
      e.preventDefault();
      if (review.trackInsert(e.key)) refreshStats();
    }
  }

  // ── Keyboard shortcuts ──────────────────────────────────────────────────
  function onKeydown(e: KeyboardEvent) {
    const mod = e.ctrlKey || e.metaKey;
    if (e.altKey && e.key.toLowerCase() === 'q') {
      e.preventDefault();
      showCommandSearch = true;
      return;
    }
    if (!mod) {
      maybeTrackInsert(e);
      return;
    }
    const key = e.key.toLowerCase();
    if (key === 's') {
      e.preventDefault();
      saveToWorkspace();
    } else if (key === 'f') {
      e.preventDefault();
      dialog = 'find';
    } else if (key === 'p') {
      e.preventDefault();
      handlePrint();
    } else if (key === 'g') {
      e.preventDefault();
      doFindNext(e.shiftKey);
    } else if (key === 'k') {
      e.preventDefault();
      dialog = 'link';
    }
  }

  function onSelectionChange() {
    selStats = selectionStats();
    editorState = readState();
  }

  onMount(() => {
    properties = loadProperties();
    const draft = loadDraft();
    if (draft) {
      html = draft.html;
      docTitle = draft.title;
      properties.title = draft.title;
    } else {
      properties.title = docTitle;
    }
    section = loadSection() ?? defaultSection();
    sources = loadSources();
    versions = listVersions();
    recovery = listRecovery();
    buildRegistry();
    refreshStats();
    const timer = setInterval(() => {
      if (dirty) autosaver.flush();
    }, 20000);
    return () => clearInterval(timer);
  });

  // Load/save the citation source list whenever the citations dialog mutates it.
  function onAddSource(s: Source) {
    sources = [...sources.filter((x) => x.id !== s.id), s];
    saveSources(sources);
  }
  function onRemoveSource(id: string) {
    sources = sources.filter((x) => x.id !== id);
    saveSources(sources);
  }
  function onInsertCitation(src: Source) {
    insertCitation(src, citationStyle);
    refreshStats();
  }

  const wordCounts = $derived(() => {
    const el = getEditor();
    void navRevision;
    return el ? review.wordCount(el) : { words: 0, characters: 0, charactersNoSpaces: 0, paragraphs: 0, lines: 0, pages: 1 };
  });
  const dialogHeadings = $derived.by(() => {
    const el = getEditor();
    void navRevision;
    return el ? collectHeadings(el).map((h) => ({ id: h.id, text: h.text, level: h.level })) : [];
  });
  const pageLabel = $derived(`${section.paper}${section.orientation === 'landscape' ? ' ↔' : ''}`);
</script>

<svelte:window onkeydown={onKeydown} onselectionchange={onSelectionChange} />

{#if showFileBackstage}
  <div class="h-[calc(100vh-3.5rem)]">
    <FileBackstage
      bind:properties
      versions={listVersions()}
      recovery={listRecovery()}
      onclose={() => (showFileBackstage = false)}
      onnew={newFromTemplate}
      onopen={() => { showFileBackstage = false; triggerOpen(); }}
      onsave={saveToWorkspace}
      onexportpdf={handlePrint}
      onexport={handleExport}
      onrestoreversion={(v) => {
        html = v.html;
        docTitle = v.title;
        showFileBackstage = false;
        refreshStats();
        notify.info('Versi dipulihkan');
      }}
      onrecover={(d) => {
        html = d.html;
        docTitle = d.title;
        showFileBackstage = false;
        refreshStats();
        notify.success('Draf dipulihkan');
      }}
      onsaveproperties={(p) => {
        properties = p;
        saveProperties(p);
        docTitle = p.title;
        notify.success('Properti tersimpan');
      }}
      oninspect={() => { showFileBackstage = false; runInspect(); }}
      onaccessibility={() => { showFileBackstage = false; runInspect(); }}
    />
  </div>
{:else}
  <div class="flex flex-col h-[calc(100vh-3.5rem)]">
    <!-- Page header -->
    <div class="flex items-center justify-between gap-3 px-4 py-2 border-b border-[var(--border-color)] bg-[var(--bg-surface)]/90">
      <div class="flex items-center gap-2 min-w-0">
        <FileText class="w-4 h-4 text-[var(--accent-primary)] shrink-0" />
        <input
          bind:value={docTitle}
          oninput={() => {
            properties.title = docTitle;
            dirty = true;
          }}
          class="bg-transparent border-b border-transparent focus:border-[var(--accent-primary)] text-sm font-hud text-[var(--text-primary)] px-1 py-0.5 min-w-0 w-56 md:w-96 outline-none"
          aria-label="Judul dokumen"
        />
        {#if dirty}
          <span class="text-[9px] font-code text-[var(--status-warning)]">● UNSAVED</span>
        {:else if lastSaved}
          <span class="text-[9px] font-code text-[var(--status-success)] flex items-center gap-0.5"><Check class="w-3 h-3" /> {lastSaved}</span>
        {/if}
        {#if trackingOn}<span class="text-[9px] font-code text-[var(--accent-primary)]">LACAK ●</span>{/if}
      </div>
      <div class="flex items-center gap-2">
        <button type="button" onclick={() => (showCommandSearch = true)} class="flex items-center gap-1 px-2 py-1.5 text-[11px] font-code border border-[var(--border-color)] text-[var(--text-muted)] chamfer-sm hover:text-[var(--accent-primary)]" title="Cari perintah (Alt+Q)">
          <span class="hidden sm:inline">CARI PERINTAH</span><span class="sm:hidden">⌕</span>
        </button>
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
    </div>

    <!-- Ribbon -->
    <NaskahRibbon
      {getEditor}
      doc={editorState}
      {zoom}
      readingMode={readingMode}
      inTable={editorState.ctx.inTable}
      inPicture={false}
      revision={navRevision}
      onfile={() => (showFileBackstage = true)}
      onsave={saveToWorkspace}
      onopen={triggerOpen}
      onexport={handleExport}
      onprint={handlePrint}
      onfind={() => (dialog = 'find')}
      onfindnext={doFindNext}
      oninsertlink={() => (dialog = 'link')}
      oninsertimage={() => (dialog = 'image')}
      oninsertdatetime={() => { insert.text(dateTimeStamp()); refreshStats(); }}
      onfontdialog={() => (dialog = 'font')}
      onparagraphdialog={() => (dialog = 'paragraph')}
      onpagesetup={() => (dialog = 'pagesetup')}
      onwatermark={() => (dialog = 'watermark')}
      ontableborders={() => (dialog = 'tableborders')}
      oncoverpage={() => (dialog = 'cover')}
      oninsertsymbol={() => (dialog = 'symbol')}
      oninsequation={() => (dialog = 'equation')}
      onquickparts={() => (dialog = 'quickparts')}
      oninsertcaption={() => (dialog = 'caption')}
      oncitations={() => (dialog = 'citations')}
      onbookmark={() => (dialog = 'bookmark')}
      oncrossreference={() => (dialog = 'crossref')}
      onnewcomment={() => (dialog = 'comment')}
      onreviewpane={() => (reviewOpen = true)}
      onwordcount={() => (dialog = 'wordcount')}
      onspellcheck={runSpellcheck}
      onthesaurus={openThesaurus}
      onreadaloud={readAloud}
      oninspect={runInspect}
      ontextbox={() => (dialog = 'textbox')}
      onwordart={() => (dialog = 'wordart')}
      ondropcap={() => { insert.html(dropCap(3)); refreshStats(); }}
      onsignature={() => (dialog = 'signature')}
      onsmartart={() => (dialog = 'smartart')}
      onchart={() => (dialog = 'chart')}
      onpictureformat={() => (dialog = 'pictureformat')}
      ontracking={toggleTracking}
      onacceptall={acceptAllRevisions}
      onrejectall={rejectAllRevisions}
      onmailings={() => (showMailings = !showMailings)}
      onlabels={insertLabels}
      onzoom={(z) => (zoom = z)}
      onpagetab={() => (showCommandSearch = true)}
      ontogglereading={() => (readingMode = !readingMode)}
      ontoggledarkpaper={() => { section = { ...section, darkPaper: !section.darkPaper }; saveSection(section); }}
      ontogglenavpane={() => (showNavPane = !showNavPane)}
      ontoggleruler={() => (showRuler = !showRuler)}
      ontogglemarks={() => (showMarks = !showMarks)}
      onpageview={() => (pageView = pageView === 1 ? 2 : 1)}
      onpagecolor={setPageColor}
      ontoggletoc={insertToc}
      oninsertindex={insertIndex}
      ontableoffigures={insertTableOfFigures}
      oninsertnote={insertNote}
      oninsertbibliography={insertBibliography}
      ondesignspacing={setSpacing}
      onmargin={applyMargin}
      onorientation={toggleOrientation}
      oncolumns={setColumns}
      onequestyle={applyDocStyle}
      onautotext={() => (dialog = 'autotext')}
      onfield={() => (dialog = 'field')}
      ontextframe={() => (dialog = 'textframe')}
      onwriterdialog={() => (dialog = 'hyperwriter')}
      onfontwork={() => (dialog = 'fontwork')}
      onlistgallery={(key) => insertListFromGallery(key)}
      onhorizontalline={(key) => { insert.html(horizontalLine(key as never)); refreshStats(); }}
      oninsertbreak={(kind) => { insert.html(breakMarkup(kind)); refreshStats(); }}
      oncolumnspreset={(n) => setColumns(n)}
      onpagefield={() => insertPageField()}
    />

    {#if showMailings}
      <MailingsPane
        {recipients}
        onupload={triggerMailUpload}
        oninsertfield={insertMergeField}
        oninsertaddress={() => insert.text('{{Alamat}}')}
        oninsertgreeting={() => insert.text('{{Salam}}')}
        ontogglehighlight={() => (mergeHighlight = !mergeHighlight)}
        highlight={mergeHighlight}
        onmerge={mergeAllRecords}
        onlabels={() => insertLabels('Label 3×8')}
        onselectrecord={(i) => (activeRecord = i)}
        {activeRecord}
        onexit={() => (showMailings = false)}
      />
    {/if}

    <!-- Canvas + side panes -->
    <div class="flex-1 flex overflow-hidden">
      {#if showNavPane && !readingMode}
        <NavigationPane revision={navRevision} getRoot={getEditor} onexit={() => (showNavPane = false)} />
      {/if}
      {#if showStylesPane && !readingMode}
        <StyleGalleryPane activeStyle={editorState.ctx.styleName} onexit={() => (showStylesPane = false)} />
      {/if}
      <div class="flex-1 overflow-hidden relative">
        <NaskahCanvas
          bind:this={canvas}
          {html}
          {zoom}
          reading={readingMode}
          {section}
          {pageView}
          ruler={showRuler}
          {showMarks}
          onchange={onChange}
        />
      </div>
      {#if reviewOpen && !readingMode}
        <ReviewPane
          tab={reviewTab}
          {comments}
          {spelling}
          {inspector}
          counts={wordCounts()}
          {thesaurusWord}
          synonyms={thesaurusWords}
          ontab={(t) => (reviewTab = t)}
          onjumpcomment={(id) => { const el = getEditor(); if (el) review.focusComment(el, id); }}
          onresolve={(id) => { const el = getEditor(); if (el) { review.resolveComment(el, id); comments = review.collectComments(el); refreshStats(); } }}
          ondelete={(id) => { const el = getEditor(); if (el) { review.deleteComment(el, id); comments = review.collectComments(el); refreshStats(); } }}
          onreplacespelling={replaceSpelling}
          onapplysynonym={applySynonym}
          onexit={() => (reviewOpen = false)}
        />
      {/if}
    </div>

    <!-- Status bar -->
    <div class="naskah-status flex items-center justify-between gap-4 px-4 py-1.5 border-t border-[var(--border-color)] bg-[var(--bg-surface)]/90 font-code text-[10px] text-[var(--text-muted)] overflow-x-auto">
      <div class="flex items-center gap-4 whitespace-nowrap">
        <span><b class="text-[var(--text-primary)]">{formatNumber(stats.words)}</b> kata</span>
        <span><b class="text-[var(--text-primary)]">{formatNumber(stats.characters)}</b> karakter</span>
        <span class="hidden sm:inline"><b class="text-[var(--text-primary)]">{formatNumber(stats.charactersNoSpaces)}</b> tanpa spasi</span>
        <span class="hidden md:inline"><b class="text-[var(--text-primary)]">{stats.paragraphs}</b> paragraf</span>
        <span class="hidden md:inline">~{stats.readingMinutes} mnt baca</span>
        {#if selStats.words > 0}
          <span class="text-[var(--accent-primary)]" title="Teks terpilih"><b>{formatNumber(selStats.words)}</b> kata dipilih</span>
        {/if}
      </div>
      <div class="flex items-center gap-3 whitespace-nowrap">
        <span>{pageLabel} · {section.margins.top}px · {zoom}%</span>
        {#if deviceBridge.directoryHandle}
          <span class="text-[var(--status-success)]">DISK: {deviceBridge.mountedFolderName}</span>
        {/if}
      </div>
    </div>
  </div>
{/if}

<!-- Hidden file inputs -->
<input bind:this={fileInput} type="file" accept=".html,.htm,.md,.txt,.doc,.docx,.odt,.rtf" onchange={onFilePicked} class="hidden" />
<input bind:this={mailInput} type="file" accept=".csv,.txt" onchange={onMailPicked} class="hidden" />

<!-- Dialogs -->
{#if dialog}
  <EditorDialogs
    kind={dialog}
    onexit={() => (dialog = null)}
    onsubmit={submitDialog}
    bind:findText
    bind:replaceText
    {matchCount}
    onfindnext={doFindNext}
    onreplace={doReplace}
    {sources}
    bind:citationStyle
    onaddsource={onAddSource}
    onremovesource={onRemoveSource}
    oninsertcitation={onInsertCitation}
    oninsertbibliography={insertBibliography}
    headings={dialogHeadings}
    findings={inspector}
    counts={wordCounts()}
  />
{/if}

<!-- Tell-Me command search -->
<CommandSearch open={showCommandSearch} onexit={() => (showCommandSearch = false)} />
