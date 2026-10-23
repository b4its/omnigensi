<script lang="ts">
  /**
   * NaskahRibbon — the Word/Wordcraft-style tabbed ribbon for Naskah Studio.
   *
   * Tabs: File · Home · Insert · Design · Layout · References · Mailings ·
   * Review · View · Table · Picture. (Table and Picture are the contextual
   * tabs Word shows when a table cell or a picture is active.)
   *
   * The ribbon is presentational: every button calls a command from the editor
   * libraries (`commands`, `charFx`, `paraFx`, `styles`, `insertBlocks`,
   * `references`, `review`, `tableTools`) or bubbles an intent to the page via
   * an `on*` prop for things that need a dialog or a side pane. All actions are
   * also registered in `commandRegistry` so the Tell-Me search can reach them.
   *
   * Selection preservation: buttons fire on `mousedown` with preventDefault,
   * so the caret inside the contentEditable survives the interaction.
   */
  import RibbonGroup from './RibbonGroup.svelte';
  import RibbonButton from './RibbonButton.svelte';
  import StyleGallery from './StyleGallery.svelte';
  import { fmt, para, insert, history, table } from './commands';
  import { charFx, encloseSelection } from './charFx';
  import { paraFx } from './paraFx';
  import { tableTools } from './tableTools';
  import { HORIZONTAL_LINES, LIST_GALLERY, listStart } from './loBlocks';
  import type { EditorStateSnapshot } from './editorState';
  import type { DocStyle } from './styles';
  import {
    Bold,
    Italic,
    Underline,
    Strikethrough,
    Subscript,
    Superscript,
    Highlighter,
    Type,
    Baseline,
    RemoveFormatting,
    TextAlignStart,
    TextAlignCenter,
    TextAlignEnd,
    TextAlignJustify,
    List,
    ListOrdered,
    ListTree,
    ArrowRightToLine,
    ArrowLeftToLine,
    Quote,
    Minus,
    Table,
    Image as ImageIcon,
    Link as LinkIcon,
    Link2Off,
    Undo2,
    Redo2,
    Save,
    FolderOpen,
    Download,
    Printer,
    Search,
    Palette,
    Columns3,
    Pilcrow,
    CaseSensitive,
    Heading1,
    Heading2,
    Heading3,
    Heading4,
    Ruler,
    ZoomIn,
    ZoomOut,
    Eye,
    FileDown,
    Scissors,
    Copy,
    Clipboard,
    BookOpen,
    Rows3,
    Plus,
    Trash2,
    ArrowUp,
    ArrowDown,
    ArrowLeft,
    ArrowRight,
    CalendarClock,
    ChevronUp,
    ChevronDown,
    Paintbrush,
    PaintRoller,
    TableProperties,
    Merge,
    Split,
    Grid3x3,
    ArrowUpDown,
    Sigma,
    SigmaSquare,
    Shapes,
    TypeOutline,
    Sparkles,
    Sticker,
    ChartBar,
    FileText,
    ListOrdered as ListOrderedIcon,
    BookOpenCheck,
    Languages,
    SpellCheck,
    MessageSquare,
    MessageSquarePlus,
    Check,
    CheckCheck,
    X,
    XCircle,
    ChevronLeft,
    ChevronRight,
    Tally5,
    Volume2,
    ShieldCheck,
    Lock,
    Columns2,
    PanelLeft,
    Maximize,
    Moon,
    Sun,
    Hash,
    Stamp,
    TextInitial,
    SquareDashedBottomCode,
    WrapText,
    Crop,
    RotateCw,
    Maximize2,
    FileImage,
    ALargeSmall,
    Baseline as BaselineIcon,
    Grid3X3,
    ListCollapse,
    ListRestart,
    ListChevronsUpDown,
    Hash as HashIcon,
  } from 'lucide-svelte';

  type Tab =
    | 'Home'
    | 'Format'
    | 'Insert'
    | 'Design'
    | 'Layout'
    | 'References'
    | 'Mailings'
    | 'Review'
    | 'View'
    | 'Table'
    | 'Picture';

  interface Props {
    getEditor: () => HTMLElement | undefined;
    doc: EditorStateSnapshot;
    zoom: number;
    readingMode: boolean;
    inTable: boolean;
    inPicture: boolean;
    /** Bumped by the page after every change so derived UI refreshes. */
    revision: number;
    // page actions that need dialogs / panes
    onfile: () => void;
    onsave: () => void;
    onopen: () => void;
    onexport: (format: 'docx' | 'doc' | 'odt' | 'rtf' | 'tex' | 'html' | 'md' | 'txt') => void;
    onprint: () => void;
    onfind: () => void;
    onfindnext: (backward: boolean) => void;
    oninsertlink: () => void;
    oninsertimage: () => void;
    oninsertdatetime: () => void;
    onfontdialog: () => void;
    onparagraphdialog: () => void;
    onpagesetup: () => void;
    onwatermark: () => void;
    ontableborders: () => void;
    oncoverpage: () => void;
    oninsertsymbol: () => void;
    oninsequation: () => void;
    onquickparts: () => void;
    oninsertcaption: () => void;
    oncitations: () => void;
    onbookmark: () => void;
    oncrossreference: () => void;
    onnewcomment: () => void;
    onreviewpane: () => void;
    onwordcount: () => void;
    onspellcheck: () => void;
    onthesaurus: () => void;
    onreadaloud: () => void;
    oninspect: () => void;
    ontextbox: () => void;
    onwordart: () => void;
    ondropcap: () => void;
    onsignature: () => void;
    onsmartart: () => void;
    onchart: () => void;
    onpictureformat: () => void;
    ontracking: () => void;
    onacceptall: () => void;
    onrejectall: () => void;
    onmailings: () => void;
    onzoom: (zoom: number) => void;
    onpagetab: (tab: Tab) => void;
    ontogglereading: () => void;
    ontoggledarkpaper: () => void;
    ontogglenavpane: () => void;
    ontoggleruler: () => void;
    ontogglemarks: () => void;
    // LibreOffice Writer tab
    onautotext: () => void;
    onfield: () => void;
    ontextframe: () => void;
    onwriterdialog: () => void;
    onfontwork: () => void;
    onlistgallery: (style: string) => void;
    onhorizontalline: (key: string) => void;
    oninsertbreak: (kind: 'page' | 'column' | 'section') => void;
    oncolumnspreset: (n: number) => void;
    onpagefield: () => void;
    onpageview: () => void;
    onpagecolor: (color: string) => void;
    ontoggletoc: () => void;
    oninsertindex: () => void;
    ontableoffigures: () => void;
    oninsertnote: (kind: 'footnote' | 'endnote') => void;
    oninsertbibliography: () => void;
    onlabels: (layout: 'Envelope C5' | 'Label 3×8') => void;
    ondesignspacing: (preset: 'none' | 'compact' | 'normal' | 'loose') => void;
    onmargin: (preset: string) => void;
    onorientation: () => void;
    oncolumns: (n: number) => void;
    onequestyle: (style: DocStyle) => void;
  }

  let {
    getEditor,
    doc,
    zoom,
    readingMode,
    inTable,
    inPicture,
    revision,
    onfile,
    onsave,
    onopen,
    onexport,
    onprint,
    onfind,
    onfindnext,
    oninsertlink,
    oninsertimage,
    oninsertdatetime,
    onfontdialog,
    onparagraphdialog,
    onpagesetup,
    onwatermark,
    ontableborders,
    oncoverpage,
    oninsertsymbol,
    oninsequation,
    onquickparts,
    oninsertcaption,
    oncitations,
    onbookmark,
    oncrossreference,
    onnewcomment,
    onreviewpane,
    onwordcount,
    onspellcheck,
    onthesaurus,
    onreadaloud,
    oninspect,
    ontextbox,
    onwordart,
    ondropcap,
    onsignature,
    onsmartart,
    onchart,
    onpictureformat,
    ontracking,
    onacceptall,
    onrejectall,
    onmailings,
    onzoom,
    onpagetab,
    ontogglereading,
    ontoggledarkpaper,
    ontogglenavpane,
    ontoggleruler,
    ontogglemarks,
    onautotext,
    onfield,
    ontextframe,
    onwriterdialog,
    onfontwork,
    onlistgallery,
    onhorizontalline,
    oninsertbreak,
    oncolumnspreset,
    onpagefield,
    onpageview,
    onpagecolor,
    ontoggletoc,
    oninsertindex,
    ontableoffigures,
    oninsertnote,
    oninsertbibliography,
    onlabels,
    ondesignspacing,
    onmargin,
    onorientation,
    oncolumns,
    onequestyle,
  }: Props = $props();

  type IconCtor = typeof Type;
  const tabs: { name: Tab; icon: IconCtor }[] = [
    { name: 'Home', icon: Type },
    { name: 'Format', icon: Paintbrush },
    { name: 'Insert', icon: Table },
    { name: 'Design', icon: Palette },
    { name: 'Layout', icon: Columns3 },
    { name: 'References', icon: BookOpen },
    { name: 'Mailings', icon: FileText },
    { name: 'Review', icon: Search },
    { name: 'View', icon: Eye },
  ];

  // Word shows Table/Picture as *extra* contextual tabs and keeps the one the
  // user picked. Only auto-switch to a contextual tab when the caret enters a
  // table or picture while a non-contextual tab is active — never overwrite an
  // explicit choice, or the contextual tools become unreachable.
  let shownTab = $state<Tab>('Home');
  $effect(() => {
    if (inTable && (shownTab === 'Home' || shownTab === 'Insert') && !tableDismissed) {
      shownTab = 'Table';
    }
    if (inPicture && !pictureDismissed) {
      shownTab = 'Picture';
    }
  });
  let tableDismissed = $state(false);
  let pictureDismissed = $state(false);

  // Popover visibility, all closed on outside mousedown like Word's menus.
  let popover = $state<string | null>(null);
  const fonts = [
    'Times New Roman', 'Georgia', 'Arial', 'Helvetica', 'Calibri', 'Cambria',
    'Courier New', 'JetBrains Mono', 'Verdana', 'Garamond', 'Palatino',
    'Book Antiqua', 'Trebuchet MS', 'Tahoma', 'Consolas', 'Merriweather',
  ];
  const sizes = [8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36, 48, 72];
  const highlights = ['#FFEB3B', '#8BC34A', '#03A9F4', '#FF9800', '#E91E63', '#9C27B0', 'transparent'];
  const colors = ['#000000', '#333333', '#FF0055', '#00A86B', '#0066FF', '#00B8D4', '#FFB800', '#7C4DFF', '#E91E63', '#4CAF50', '#FFFFFF'];
  const pageColorPresets = ['transparent', '#FFF8E1', '#E8F5E9', '#E3F2FD', '#FCE4EC', '#F3E5F5'];
  const shapesList = ['rect', 'round', 'triangle', 'diamond', 'arrow', 'star'] as const;
  const symbols = ['—', '–', '©', '®', '™', '•', '…', '§', '¶', '°', '±', '×', '÷', '←', '→', '↑', '↓', '€', '£', '¥'];
  const listStyles = ['disc', 'circle', 'square', 'decimal', 'lower-alpha', 'upper-roman'];
  const shadingPresets = ['transparent', '#FFF3CD', '#D1ECF1', '#D4EDDA', '#F8D7DA', '#E2E3E5'];

  let fontFamily = $derived(doc.inline.fontFamily);
  let fontSize = $derived(doc.inline.fontSize);

  function run(fn: () => void) {
    fn();
  }

  function pick(p: string) {
    popover = popover === p ? null : p;
  }

  // Close an open popover when a mousedown lands outside it.
  function closePopovers(e: MouseEvent) {
    const target = e.target as HTMLElement | null;
    if (target?.closest('[data-popover]')) return;
    popover = null;
  }

  let tableRows = $state(3);
  let tableCols = $state(3);
  let shapeKey = $state<(typeof shapesList)[number]>('rect');
  let spanRows = $state(2);
  let spanCols = $state(2);
  let charSpacing = $state(1);

  // `revision` is intentionally referenced so the derived select values
  // refresh whenever the page bumps it after an edit.
  $effect(() => {
    void revision;
  });
</script>

<svelte:window onmousedown={closePopovers} />

<div class="naskah-ribbon sticky top-0 z-20 border-b border-[var(--border-color)] bg-[var(--bg-surface)]">
  <!-- Tab strip + quick actions (hidden in reading mode) -->
  {#if !readingMode}
    <div class="flex items-center gap-0.5 px-2 pt-1.5 border-b border-[var(--border-color)]/50 overflow-x-auto">
      <button
        type="button"
        onmousedown={(e) => {
          e.preventDefault();
          onfile();
        }}
        class="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-hud tracking-wider rounded-t-sm whitespace-nowrap transition-colors text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)]/50 border-b-2 border-transparent"
      >
        <FileText class="w-3.5 h-3.5" />
        FILE
      </button>
      {#each tabs as tab}
        <button
          type="button"
          onmousedown={(e) => {
            e.preventDefault();
            shownTab = tab.name;
            if (tab.name !== 'Table') tableDismissed = true;
            if (tab.name !== 'Picture') pictureDismissed = true;
            popover = null;
          }}
          class="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-hud tracking-wider rounded-t-sm whitespace-nowrap transition-colors
            {shownTab === tab.name
              ? 'bg-[var(--bg-elevated)] text-[var(--accent-primary)] border-b-2 border-[var(--accent-primary)]'
              : 'text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)]/50 border-b-2 border-transparent'}"
        >
          <tab.icon class="w-3.5 h-3.5" />
          {tab.name.toUpperCase()}
        </button>
      {/each}
      {#if shownTab === 'Table' || shownTab === 'Picture'}
        <span class="mx-1 h-5 w-px bg-[var(--border-color)]"></span>
        <span class="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-hud tracking-wider text-[var(--accent-secondary)] bg-[var(--bg-elevated)]/40 rounded-t-sm whitespace-nowrap">
          <Table class="w-3.5 h-3.5" />
          {#if shownTab === 'Table'}TABEL{:else}GAMBAR{/if}
        </span>
      {/if}
      <div class="flex-1"></div>
      <button
      	type="button"
      	title="Cari perintah (Alt+Q)"
      	onmousedown={(e) => { e.preventDefault(); onpagetab('Home'); }}
      	class="hidden md:flex items-center gap-1 px-2 py-1 text-[10px] font-code text-[var(--text-muted)] border border-[var(--border-color)] rounded-sm hover:text-[var(--accent-primary)]"
      >
        <Search class="w-3 h-3" /> Cari perintah
      </button>
    </div>
  {/if}

  <!-- Ribbon body (hidden in reading mode; a slim exit bar replaces it) -->
  {#if readingMode}
    <div class="flex items-center justify-between gap-2 px-3 py-1.5">
      <span class="text-[10px] font-code text-[var(--text-muted)]"> MODE BACA · bilah alat disembunyikan </span>
      <button
        type="button"
        onmousedown={(e) => {
          e.preventDefault();
          ontogglereading();
        }}
        class="px-3 py-1 text-[10px] font-hud border border-[var(--accent-primary)] text-[var(--accent-primary)] chamfer-sm hover:bg-[var(--accent-primary)]/10"
      >
        KELUAR MODE BACA
      </button>
    </div>
  {:else}
    <div class="flex items-stretch gap-0 min-h-[78px] overflow-x-auto py-1">

      {#if shownTab === 'Home'}
        <RibbonGroup label="Papan Klip">
          <RibbonButton title="Potong (Ctrl+X)" onclick={() => run(history.cut)}><Scissors class="w-4 h-4" /></RibbonButton>
          <RibbonButton title="Salin (Ctrl+C)" onclick={() => run(history.copy)}><Copy class="w-4 h-4" /></RibbonButton>
          <RibbonButton title="Tempel (Ctrl+V)" onclick={() => run(history.paste)}><Clipboard class="w-4 h-4" /></RibbonButton>
          <RibbonButton title="Format Painter — salin format ke pilihan" onclick={() => run(() => {
            const sel = window.getSelection();
            if (!sel || sel.isCollapsed) return;
            const src = sel.getRangeAt(0).startContainer.parentElement;
            if (!src) return;
            const css = src.getAttribute('style') ?? '';
            document.execCommand('insertHTML', false, `<span style="${css}">${sel.toString()}</span>`);
          })}><Paintbrush class="w-4 h-4" /></RibbonButton>
        </RibbonGroup>

        <RibbonGroup label="Urungkan">
          <RibbonButton title="Urungkan (Ctrl+Z)" onclick={() => run(history.undo)}><Undo2 class="w-4 h-4" /></RibbonButton>
          <RibbonButton title="Ulangi (Ctrl+Y)" onclick={() => run(history.redo)}><Redo2 class="w-4 h-4" /></RibbonButton>
        </RibbonGroup>

        <RibbonGroup label="Font" column>
          <div class="flex items-center gap-1 w-full">
            <select
              value={fontFamily}
              onchange={(e) => run(() => fmt.fontName((e.target as HTMLSelectElement).value))}
              class="text-[11px] font-code bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm px-1 py-0.5 text-[var(--text-primary)] w-32"
              title="Jenis huruf"
            >
              {#if !fonts.includes(fontFamily)}<option value={fontFamily}>{fontFamily}</option>{/if}
              {#each fonts as f}<option value={f}>{f}</option>{/each}
            </select>
            <select
              value={fontSize}
              onchange={(e) => run(() => fmt.fontSize(Number((e.target as HTMLSelectElement).value)))}
              class="text-[11px] font-code bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm px-1 py-0.5 text-[var(--text-primary)] w-14"
              title="Ukuran huruf (pt)"
            >
              {#if !sizes.includes(fontSize)}<option value={fontSize}>{fontSize}</option>{/if}
              {#each sizes as s}<option value={s}>{s}</option>{/each}
            </select>
            <RibbonButton title="Perbesar huruf" onclick={() => run(() => fmt.fontSize(Math.min(72, fontSize + 1)))}><Plus class="w-3 h-3" /></RibbonButton>
            <RibbonButton title="Perkecil huruf" onclick={() => run(() => fmt.fontSize(Math.max(6, fontSize - 1)))}><Minus class="w-3 h-3" /></RibbonButton>
          </div>
          <div class="flex items-center gap-0.5 flex-wrap">
            <RibbonButton title="Tebal (Ctrl+B)" active={doc.inline.bold} onclick={() => run(fmt.bold)}><Bold class="w-4 h-4" /></RibbonButton>
            <RibbonButton title="Miring (Ctrl+I)" active={doc.inline.italic} onclick={() => run(fmt.italic)}><Italic class="w-4 h-4" /></RibbonButton>
            <RibbonButton title="Garis bawah (Ctrl+U)" active={doc.inline.underline} onclick={() => run(fmt.underline)}><Underline class="w-4 h-4" /></RibbonButton>
            <RibbonButton title="Cetak tebal ganda" onclick={() => run(charFx.doubleUnderline)}><Underline class="w-4 h-4" /><span class="text-[9px]">×2</span></RibbonButton>
            <RibbonButton title="Coret" active={doc.inline.strike} onclick={() => run(fmt.strikethrough)}><Strikethrough class="w-4 h-4" /></RibbonButton>
            <RibbonButton title="Coret ganda" onclick={() => run(charFx.doubleStrike)}><Strikethrough class="w-4 h-4" /><span class="text-[9px]">×2</span></RibbonButton>
            <RibbonButton title="Superskrip" active={doc.inline.sup} onclick={() => run(fmt.superscript)}><Superscript class="w-4 h-4" /></RibbonButton>
            <RibbonButton title="Subskrip" active={doc.inline.sub} onclick={() => run(fmt.subscript)}><Subscript class="w-4 h-4" /></RibbonButton>
            <RibbonButton title="Kapital kecil" active={doc.inline.smallCaps} onclick={() => run(charFx.smallCaps)}><ALargeSmall class="w-4 h-4" /></RibbonButton>
            <RibbonButton title="Semua kapital" active={doc.inline.allCaps} onclick={() => run(charFx.allCaps)}><CaseSensitive class="w-4 h-4" /></RibbonButton>
            <RibbonButton title="Teks tersembunyi" onclick={() => run(charFx.hidden)}><Eye class="w-4 h-4" /></RibbonButton>
            <RibbonButton title="Ubah kapitalisasi" onclick={() => run(() => fmt.changeCase('title'))}><CaseSensitive class="w-4 h-4" /></RibbonButton>
            <div class="relative" data-popover>
              <RibbonButton title="Sorotan warna" onclick={() => pick('hl')}><Highlighter class="w-4 h-4" /></RibbonButton>
              {#if popover === 'hl'}
                <div class="absolute z-30 mt-1 p-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm shadow-lg grid grid-cols-4 gap-1">
                  {#each highlights as h}
                    <button type="button" onmousedown={(e) => { e.preventDefault(); run(() => fmt.highlight(h)); popover = null; }}
                      class="w-5 h-5 rounded-sm border border-white/20" style:background={h === 'transparent' ? 'transparent' : h} title={h}></button>
                  {/each}
                </div>
              {/if}
            </div>
            <div class="relative" data-popover>
              <RibbonButton title="Warna huruf" onclick={() => pick('color')}><Baseline class="w-4 h-4 text-[var(--accent-primary)]" /></RibbonButton>
              {#if popover === 'color'}
                <div class="absolute z-30 mt-1 p-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm shadow-lg grid grid-cols-4 gap-1">
                  {#each colors as c}
                    <button type="button" onmousedown={(e) => { e.preventDefault(); run(() => fmt.color(c)); popover = null; }}
                      class="w-5 h-5 rounded-sm border border-white/20" style:background={c} title={c}></button>
                  {/each}
                </div>
              {/if}
            </div>
            <div class="relative" data-popover>
              <RibbonButton title="Efek teks" onclick={() => pick('fx')}><Sparkles class="w-4 h-4" /></RibbonButton>
              {#if popover === 'fx'}
                <div class="absolute z-30 mt-1 p-1 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm shadow-lg flex flex-col text-[11px] w-40">
                  {#each [['Outline', charFx.outline], ['Bayangan', charFx.shadow], ['Glow', charFx.glow], ['Emboss', charFx.emboss], ['Engrave', charFx.engrave], ['Bingkai', () => charFx.border()], ['Latar', () => charFx.shading('#FFF3CD')]] as [label, fn]}
                    <button type="button" onmousedown={(e) => { e.preventDefault(); run(fn as () => void); popover = null; }} class="text-left px-2 py-1 rounded-sm hover:bg-[var(--bg-surface)] text-[var(--text-primary)]">{label}</button>
                  {/each}
                </div>
              {/if}
            </div>
            <div class="relative" data-popover>
              <RibbonButton title="Jarak huruf & skala" onclick={() => pick('spacing')}><WrapText class="w-4 h-4" /></RibbonButton>
              {#if popover === 'spacing'}
                <div class="absolute z-30 mt-1 p-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm shadow-lg w-44 text-[11px]">
                  <div class="text-[9px] font-code text-[var(--text-muted)] mb-1">JARAK HURUF (pt)</div>
                  <div class="flex items-center gap-1 mb-2">
                    <input type="number" step="0.5" bind:value={charSpacing} class="w-14 px-1 py-0.5 bg-[var(--bg-surface)] border border-[var(--border-color)] rounded-sm text-[var(--text-primary)]" />
                    <button type="button" onmousedown={(e) => { e.preventDefault(); run(() => charFx.spacing(charSpacing)); }} class="px-2 py-0.5 bg-[var(--accent-primary)] text-[var(--on-accent)] rounded-sm">OK</button>
                  </div>
                  <div class="grid grid-cols-2 gap-1">
                    <button type="button" onmousedown={(e) => { e.preventDefault(); run(() => charFx.scale(120)); popover = null; }} class="px-1 py-0.5 border border-[var(--border-color)] rounded-sm text-[var(--text-primary)]">Skala 120%</button>
                    <button type="button" onmousedown={(e) => { e.preventDefault(); run(() => charFx.scale(80)); popover = null; }} class="px-1 py-0.5 border border-[var(--border-color)] rounded-sm text-[var(--text-primary)]">Skala 80%</button>
                    <button type="button" onmousedown={(e) => { e.preventDefault(); run(() => charFx.position(2)); popover = null; }} class="px-1 py-0.5 border border-[var(--border-color)] rounded-sm text-[var(--text-primary)]">Naik 2pt</button>
                    <button type="button" onmousedown={(e) => { e.preventDefault(); run(() => charFx.position(-2)); popover = null; }} class="px-1 py-0.5 border border-[var(--border-color)] rounded-sm text-[var(--text-primary)]">Turun 2pt</button>
                    <button type="button" onmousedown={(e) => { e.preventDefault(); run(() => encloseSelection('circle')); popover = null; }} class="px-1 py-0.5 border border-[var(--border-color)] rounded-sm text-[var(--text-primary)]">Lingkari Ⓐ</button>
                    <button type="button" onmousedown={(e) => { e.preventDefault(); run(() => encloseSelection('square')); popover = null; }} class="px-1 py-0.5 border border-[var(--border-color)] rounded-sm text-[var(--text-primary)]">Kotak 🄰</button>
                  </div>
                </div>
              {/if}
            </div>
            <RibbonButton title="Dialog Font…" onclick={onfontdialog}><Type class="w-4 h-4" /><span class="text-[9px]">…</span></RibbonButton>
            <RibbonButton title="Hapus format" onclick={() => run(fmt.clear)}><RemoveFormatting class="w-4 h-4" /></RibbonButton>
          </div>
        </RibbonGroup>

        <RibbonGroup label="Paragraf" column>
          <div class="flex items-center gap-0.5">
            <RibbonButton title="Rata kiri" active={doc.para.align === 'left'} onclick={() => run(() => para.align('left'))}><TextAlignStart class="w-4 h-4" /></RibbonButton>
            <RibbonButton title="Tengah" active={doc.para.align === 'center'} onclick={() => run(() => para.align('center'))}><TextAlignCenter class="w-4 h-4" /></RibbonButton>
            <RibbonButton title="Rata kanan" active={doc.para.align === 'right'} onclick={() => run(() => para.align('right'))}><TextAlignEnd class="w-4 h-4" /></RibbonButton>
            <RibbonButton title="Rata kanan-kiri" active={doc.para.align === 'justify'} onclick={() => run(() => para.align('justify'))}><TextAlignJustify class="w-4 h-4" /></RibbonButton>
            <RibbonButton title="Rata sebar" onclick={() => run(paraFx.distribute)}><TextAlignJustify class="w-4 h-4" /><span class="text-[9px]">≈</span></RibbonButton>
            <RibbonButton title="Arah kanan-ke-kiri" onclick={() => run(() => paraFx.rtl(true))}><ArrowRight class="w-4 h-4" /></RibbonButton>
            <RibbonButton title="Arah kiri-ke-kanan" onclick={() => run(() => paraFx.rtl(false))}><ArrowLeft class="w-4 h-4" /></RibbonButton>
          </div>
          <div class="flex items-center gap-0.5">
            <RibbonButton title="Daftar butir" active={doc.para.bullet} onclick={() => run(para.bulletList)}><List class="w-4 h-4" /></RibbonButton>
            <RibbonButton title="Daftar nomor" active={doc.para.number} onclick={() => run(para.numberList)}><ListOrdered class="w-4 h-4" /></RibbonButton>
            <div class="relative" data-popover>
              <RibbonButton title="Gaya daftar" onclick={() => pick('list')}><ListTree class="w-4 h-4" /></RibbonButton>
              {#if popover === 'list'}
                <div class="absolute z-30 mt-1 p-1 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm shadow-lg grid grid-cols-2 gap-1 text-[11px]">
                  {#each listStyles as ls}
                    <button type="button" onmousedown={(e) => { e.preventDefault(); run(() => paraFxSetList(ls)); popover = null; }} class="px-2 py-0.5 border border-[var(--border-color)] rounded-sm text-[var(--text-primary)]">{ls}</button>
                  {/each}
                </div>
              {/if}
            </div>
            <RibbonButton title="Kurangi indentasi" onclick={() => run(para.outdent)}><ArrowLeftToLine class="w-4 h-4" /></RibbonButton>
            <RibbonButton title="Tambah indentasi" onclick={() => run(para.indent)}><ArrowRightToLine class="w-4 h-4" /></RibbonButton>
            <RibbonButton title="Indentasi menggantung" onclick={() => run(() => paraFx.hangingIndent(32))}><ArrowRightToLine class="w-4 h-4" /><span class="text-[9px]">↩</span></RibbonButton>
            <div class="relative" data-popover>
              <RibbonButton title="Jarak baris" onclick={() => pick('lh')}><ListChevronsUpDown class="w-4 h-4" /></RibbonButton>
              {#if popover === 'lh'}
                <div class="absolute z-30 mt-1 p-1 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm shadow-lg flex flex-col text-[11px] w-32">
                  {#each [['1.0', '1'], ['1.15', '1.15'], ['1.5', '1.5'], ['2.0', '2'], ['2.5', '2.5'], ['3.0', '3']] as [label, v]}
                    <button type="button" onmousedown={(e) => { e.preventDefault(); run(() => para.lineHeight(v)); popover = null; }} class="text-left px-2 py-1 rounded-sm hover:bg-[var(--bg-surface)] text-[var(--text-primary)]">{label}</button>
                  {/each}
                </div>
              {/if}
            </div>
            <div class="relative" data-popover>
              <RibbonButton title="Spasi sebelum/sesudah" onclick={() => pick('sp')}><ArrowUpDown class="w-4 h-4" /></RibbonButton>
              {#if popover === 'sp'}
                <div class="absolute z-30 mt-1 p-1 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm shadow-lg flex flex-col text-[11px] w-40">
                  <button type="button" onmousedown={(e) => { e.preventDefault(); run(() => paraFx.spaceBefore(12)); popover = null; }} class="text-left px-2 py-1 rounded-sm hover:bg-[var(--bg-surface)] text-[var(--text-primary)]">Tambah spasi sebelum (12pt)</button>
                  <button type="button" onmousedown={(e) => { e.preventDefault(); run(() => para.spacingAfter(0)); popover = null; }} class="text-left px-2 py-1 rounded-sm hover:bg-[var(--bg-surface)] text-[var(--text-primary)]">Hapus spasi sesudah</button>
                  <button type="button" onmousedown={(e) => { e.preventDefault(); run(() => para.spacingAfter(6)); popover = null; }} class="text-left px-2 py-1 rounded-sm hover:bg-[var(--bg-surface)] text-[var(--text-primary)]">Spasi sesudah 6pt</button>
                </div>
              {/if}
            </div>
            <RibbonButton title="Dialog Paragraf…" onclick={onparagraphdialog}><Pilcrow class="w-4 h-4" /><span class="text-[9px]">…</span></RibbonButton>
          </div>
        </RibbonGroup>

        <RibbonGroup label="Gaya">
          <StyleGallery activeStyle={doc.ctx.styleName} onequestyle={onequestyle} />
        </RibbonGroup>

        <RibbonGroup label="Penyuntingan">
          <RibbonButton title="Cari & ganti (Ctrl+F)" onclick={onfind}><Search class="w-4 h-4" /></RibbonButton>
          <RibbonButton title="Cari sebelumnya" onclick={() => onfindnext(true)}><ChevronUp class="w-4 h-4" /></RibbonButton>
          <RibbonButton title="Cari berikutnya (Ctrl+G)" onclick={() => onfindnext(false)}><ChevronDown class="w-4 h-4" /></RibbonButton>
          <RibbonButton title="Pilih semua (Ctrl+A)" onclick={() => run(history.selectAll)}><Grid3x3 class="w-4 h-4" /></RibbonButton>
        </RibbonGroup>
      {/if}

      {#if shownTab === 'Format'}
        <RibbonGroup label="Gaya & AutoText">
          <RibbonButton title="AutoText (Ctrl+F3)" onclick={onautotext}><FileText class="w-4 h-4" /><span class="text-[10px] font-code">AutoText</span></RibbonButton>
          <RibbonButton title="Sisipkan field" onclick={onfield}><Hash class="w-4 h-4" /><span class="text-[10px] font-code">Field</span></RibbonButton>
          <RibbonButton title="Nomor halaman di teks" onclick={onpagefield}><HashIcon class="w-4 h-4" /><span class="text-[10px] font-code">No. Hlm</span></RibbonButton>
          <RibbonButton title="Bersihkan format langsung" onclick={() => run(fmt.clear)}><RemoveFormatting class="w-4 h-4" /><span class="text-[10px] font-code">Default</span></RibbonButton>
        </RibbonGroup>

        <RibbonGroup label="Bingkai & Objek">
          <RibbonButton title="Teks berjalan (bingkai)" onclick={ontextframe}><SquareDashedBottomCode class="w-4 h-4" /><span class="text-[10px] font-code">Bingkai</span></RibbonButton>
          <RibbonButton title="Fontwork" onclick={onfontwork}><TypeOutline class="w-4 h-4" /><span class="text-[10px] font-code">Fontwork</span></RibbonButton>
          <RibbonButton title="Hyperlink Writer" onclick={onwriterdialog}><LinkIcon class="w-4 h-4" /><span class="text-[10px] font-code">Tautan</span></RibbonButton>
        </RibbonGroup>

        <RibbonGroup label="Daftar">
          <div class="relative" data-popover>
            <RibbonButton title="Galeri daftar" onclick={() => pick('lo-list')}><ListTree class="w-4 h-4" /><span class="text-[10px] font-code">Galeri</span></RibbonButton>
            {#if popover === 'lo-list'}
              <div class="absolute z-30 mt-1 p-1 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm shadow-lg grid grid-cols-2 gap-1 text-[11px]">
                {#each LIST_GALLERY as g}
                  <button type="button" onmousedown={(e) => { e.preventDefault(); onlistgallery(g.key); popover = null; }} class="text-left px-2 py-1 rounded-sm hover:bg-[var(--bg-surface)] text-[var(--text-primary)]">{g.label}</button>
                {/each}
              </div>
            {/if}
          </div>
          <RibbonButton title="Mulai ulang penomoran dari 1" onclick={() => run(() => listStart(1))}><ListRestart class="w-4 h-4" /><span class="text-[10px] font-code">Ulang</span></RibbonButton>
        </RibbonGroup>

        <RibbonGroup label="Garis">
          <div class="relative" data-popover>
            <RibbonButton title="Galeri garis horizontal" onclick={() => pick('lo-line')}><Minus class="w-4 h-4" /><span class="text-[10px] font-code">Garis</span></RibbonButton>
            {#if popover === 'lo-line'}
              <div class="absolute z-30 mt-1 p-1 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm shadow-lg flex flex-col text-[11px] w-40">
                {#each HORIZONTAL_LINES as l}
                  <button type="button" onmousedown={(e) => { e.preventDefault(); onhorizontalline(l.key); popover = null; }} class="text-left px-2 py-1 rounded-sm hover:bg-[var(--bg-surface)] text-[var(--text-primary)]">{l.label}</button>
                {/each}
              </div>
            {/if}
          </div>
        </RibbonGroup>

        <RibbonGroup label="Sisipkan">
          <RibbonButton title="Pemisah halaman" onclick={() => oninsertbreak('page')}><FileDown class="w-4 h-4" /><span class="text-[10px] font-code">Halaman</span></RibbonButton>
          <RibbonButton title="Pemisah kolom" onclick={() => oninsertbreak('column')}><Columns3 class="w-4 h-4" /><span class="text-[10px] font-code">Kolom</span></RibbonButton>
          <RibbonButton title="Pemisah bagian" onclick={() => oninsertbreak('section')}><SquareDashedBottomCode class="w-4 h-4" /><span class="text-[10px] font-code">Bagian</span></RibbonButton>
        </RibbonGroup>

        <RibbonGroup label="Kolom Halaman">
          <RibbonButton title="Satu kolom" onclick={() => oncolumnspreset(1)}><Columns2 class="w-4 h-4" /><span class="text-[10px] font-code">1</span></RibbonButton>
          <RibbonButton title="Dua kolom" onclick={() => oncolumnspreset(2)}><Columns2 class="w-4 h-4" /><span class="text-[10px] font-code">2</span></RibbonButton>
          <RibbonButton title="Tiga kolom" onclick={() => oncolumnspreset(3)}><Columns3 class="w-4 h-4" /><span class="text-[10px] font-code">3</span></RibbonButton>
        </RibbonGroup>
      {/if}

      {#if shownTab === 'Insert'}
        <RibbonGroup label="Halaman">
          <RibbonButton title="Sampul" onclick={oncoverpage}><FileText class="w-4 h-4" /><span class="text-[10px] font-code">Sampul</span></RibbonButton>
          <RibbonButton title="Halaman kosong" onclick={() => run(() => insert.html('<div class="naskah-pagebreak" contenteditable="false"></div><p><br/></p>'))}><FileDown class="w-4 h-4" /><span class="text-[10px] font-code">Kosong</span></RibbonButton>
          <RibbonButton title="Pemisah halaman" onclick={() => run(insert.pageBreak)}><Minus class="w-4 h-4" /><span class="text-[10px] font-code">Page Break</span></RibbonButton>
        </RibbonGroup>

        <RibbonGroup label="Tabel">
          <div class="relative" data-popover>
            <RibbonButton title="Sisipkan tabel" onclick={() => pick('tbl')}><Table class="w-4 h-4" /><span class="text-[11px] font-code">Tabel</span></RibbonButton>
            {#if popover === 'tbl'}
              <div class="absolute z-30 mt-1 p-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm shadow-lg">
                <div class="grid gap-0.5" style:grid-template-columns="repeat(8, 1rem)">
                  {#each Array(8 * 6) as _, i}
                    {@const r = Math.floor(i / 8) + 1}
                    {@const c = (i % 8) + 1}
                    <button type="button" onmouseenter={() => { tableRows = r; tableCols = c; }}
                      onmousedown={(e) => { e.preventDefault(); run(() => insert.table(tableRows, tableCols)); popover = null; }}
                      class="w-4 h-4 border {r <= tableRows && c <= tableCols ? 'bg-[var(--accent-primary)]/50 border-[var(--accent-primary)]' : 'border-[var(--border-color)]'}"
                      title="{r} × {c}"></button>
                  {/each}
                </div>
                <div class="text-center text-[10px] font-code text-[var(--text-muted)] mt-1">{tableRows} × {tableCols}</div>
              </div>
            {/if}
          </div>
          <RibbonButton title="Tabel cepat" onclick={() => run(() => insert.html(quickTable('Daftar Tugas')))}><TableProperties class="w-4 h-4" /></RibbonButton>
          <RibbonButton title="Teks → Tabel" onclick={() => run(() => insert.html(textToTable(window.getSelection()?.toString() ?? '')))}><TableProperties class="w-4 h-4" /><span class="text-[9px]">↔</span></RibbonButton>
        </RibbonGroup>

        <RibbonGroup label="Ilustrasi">
          <RibbonButton title="Gambar" onclick={oninsertimage}><ImageIcon class="w-4 h-4" /><span class="text-[10px] font-code">Gambar</span></RibbonButton>
          <div class="relative" data-popover>
            <RibbonButton title="Bentuk" onclick={() => pick('shape')}><Shapes class="w-4 h-4" /><span class="text-[10px] font-code">Bentuk</span></RibbonButton>
            {#if popover === 'shape'}
              <div class="absolute z-30 mt-1 p-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm shadow-lg grid grid-cols-3 gap-1">
                {#each shapesList as sk}
                  <button type="button" onmousedown={(e) => { e.preventDefault(); run(() => insert.html(shape(sk))); popover = null; }} class="px-2 py-1 text-[10px] font-code border border-[var(--border-color)] rounded-sm text-[var(--text-primary)]">{sk}</button>
                {/each}
              </div>
            {/if}
          </div>
          <RibbonButton title="Ikon" onclick={() => run(() => insert.html(icon('★')))}><Sticker class="w-4 h-4" /></RibbonButton>
          <RibbonButton title="SmartArt" onclick={onsmartart}><ListTree class="w-4 h-4" /><span class="text-[10px] font-code">SmartArt</span></RibbonButton>
          <RibbonButton title="Diagram" onclick={onchart}><ChartBar class="w-4 h-4" /><span class="text-[10px] font-code">Chart</span></RibbonButton>
        </RibbonGroup>

        <RibbonGroup label="Tautan">
          <RibbonButton title="Tautan (Ctrl+K)" onclick={oninsertlink}><LinkIcon class="w-4 h-4" /><span class="text-[10px] font-code">Tautan</span></RibbonButton>
          <RibbonButton title="Hapus tautan" onclick={() => run(() => document.execCommand('unlink'))}><Link2Off class="w-4 h-4" /></RibbonButton>
          <RibbonButton title="Penanda" onclick={onbookmark}><BookOpenCheck class="w-4 h-4" /></RibbonButton>
          <RibbonButton title="Referensi silang" onclick={oncrossreference}><LinkIcon class="w-4 h-4" /><span class="text-[9px]">↔</span></RibbonButton>
        </RibbonGroup>

        <RibbonGroup label="Teks">
          <RibbonButton title="Kotak teks" onclick={ontextbox}><SquareDashedBottomCode class="w-4 h-4" /><span class="text-[10px] font-code">Kotak</span></RibbonButton>
          <RibbonButton title="WordArt" onclick={onwordart}><TypeOutline class="w-4 h-4" /><span class="text-[10px] font-code">WordArt</span></RibbonButton>
          <RibbonButton title="Drop cap" onclick={ondropcap}><TextInitial class="w-4 h-4" /><span class="text-[10px] font-code">Drop Cap</span></RibbonButton>
          <RibbonButton title="Garis tanda tangan" onclick={onsignature}><FileText class="w-4 h-4" /><span class="text-[10px] font-code">Tanda Tangan</span></RibbonButton>
          <RibbonButton title="Tanggal & waktu" onclick={oninsertdatetime}><CalendarClock class="w-4 h-4" /><span class="text-[10px] font-code">Tanggal</span></RibbonButton>
          <RibbonButton title="Bagian cepat" onclick={onquickparts}><FileText class="w-4 h-4" /><span class="text-[10px] font-code">Quick Parts</span></RibbonButton>
        </RibbonGroup>

        <RibbonGroup label="Simbol"><span class="hidden"></span>
          <div class="relative" data-popover>
            <RibbonButton title="Simbol" onclick={() => pick('sym')}><Hash class="w-4 h-4" /><span class="text-[10px] font-code">Simbol</span></RibbonButton>
            {#if popover === 'sym'}
              <div class="absolute z-30 mt-1 p-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm shadow-lg grid grid-cols-5 gap-1">
                {#each symbols as s}
                  <button type="button" onmousedown={(e) => { e.preventDefault(); run(() => insert.text(s)); popover = null; }} class="w-6 h-6 text-[13px] border border-[var(--border-color)] rounded-sm hover:bg-[var(--bg-surface)] text-[var(--text-primary)]">{s}</button>
                {/each}
              </div>
            {/if}
          </div>
          <RibbonButton title="Simbol lengkap…" onclick={oninsertsymbol}><Grid3x3 class="w-4 h-4" /></RibbonButton>
          <RibbonButton title="Spasi tak-terputus" onclick={() => run(() => insert.text('\u00A0'))}><span class="text-[10px] font-code">NBSP</span></RibbonButton>
          <RibbonButton title="Tanda hubung tak-terputus" onclick={() => run(() => insert.text('\u2011'))}><span class="text-[10px] font-code">‑</span></RibbonButton>
          <RibbonButton title="Persamaan" onclick={() => run(() => insert.html(equation('E = mc^2')))}><Sigma class="w-4 h-4" /><span class="text-[10px] font-code">Persamaan</span></RibbonButton>
          <RibbonButton title="Galeri persamaan" onclick={oninsequation}><SigmaSquare class="w-4 h-4" /></RibbonButton>
        </RibbonGroup>
      {/if}

      {#if shownTab === 'Design'}
        <RibbonGroup label="Format Dokumen">
          <RibbonButton title="Tema serif" onclick={() => run(() => fmt.fontName('Times New Roman'))}><Type class="w-4 h-4" /><span class="text-[10px] font-code">Serif</span></RibbonButton>
          <RibbonButton title="Tema sans" onclick={() => run(() => fmt.fontName('Arial'))}><Type class="w-4 h-4" /><span class="text-[10px] font-code">Sans</span></RibbonButton>
          <RibbonButton title="Tema mono" onclick={() => run(() => fmt.fontName('Courier New'))}><Type class="w-4 h-4" /><span class="text-[10px] font-code">Mono</span></RibbonButton>
          <div class="relative" data-popover>
            <RibbonButton title="Jarak paragraf dokumen" onclick={() => pick('psp')}><ListChevronsUpDown class="w-4 h-4" /><span class="text-[10px] font-code">Paragraf</span></RibbonButton>
            {#if popover === 'psp'}
              <div class="absolute z-30 mt-1 p-1 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm shadow-lg flex flex-col text-[11px] w-36">
                {#each [['none', 'Rapat'], ['compact', 'Padat'], ['normal', 'Normal'], ['loose', 'Longgar']] as [key, label]}
                  <button type="button" onmousedown={(e) => { e.preventDefault(); ondesignspacing(key as never); popover = null; }} class="text-left px-2 py-1 rounded-sm hover:bg-[var(--bg-surface)] text-[var(--text-primary)]">{label}</button>
                {/each}
              </div>
            {/if}
          </div>
        </RibbonGroup>
        <RibbonGroup label="Latar Halaman">
          <RibbonButton title="Tanda air" onclick={onwatermark}><Stamp class="w-4 h-4" /><span class="text-[10px] font-code">Watermark</span></RibbonButton>
          <div class="relative" data-popover>
            <RibbonButton title="Warna halaman" onclick={() => pick('pcol')}><PaintRoller class="w-4 h-4" /><span class="text-[10px] font-code">Warna</span></RibbonButton>
            {#if popover === 'pcol'}
              <div class="absolute z-30 mt-1 p-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm shadow-lg grid grid-cols-3 gap-1">
                {#each pageColorPresets as c}
                  <button type="button" onmousedown={(e) => { e.preventDefault(); onpagecolor(c); popover = null; }} class="w-6 h-6 rounded-sm border border-[var(--border-color)]" style:background={c === 'transparent' ? 'var(--bg-surface)' : c} title={c}></button>
                {/each}
              </div>
            {/if}
          </div>
          <RibbonButton title="Batas halaman" onclick={onpagesetup}><SquareDashedBottomCode class="w-4 h-4" /><span class="text-[10px] font-code">Batas</span></RibbonButton>
          <RibbonButton title="Mode gelap halaman" active={false} onclick={ontoggledarkpaper}><Moon class="w-4 h-4" /><span class="text-[10px] font-code">Gelap</span></RibbonButton>
        </RibbonGroup>
      {/if}

      {#if shownTab === 'Layout'}
        <RibbonGroup label="Penyiapan Halaman">
          <RibbonButton title="Dialog penyiapan halaman…" onclick={onpagesetup}><Ruler class="w-4 h-4" /><span class="text-[10px] font-code">Halaman</span></RibbonButton>
          <div class="relative" data-popover>
            <RibbonButton title="Margin" onclick={() => pick('margin')}><Ruler class="w-4 h-4" /><span class="text-[10px] font-code">Margin</span></RibbonButton>
            {#if popover === 'margin'}
              <div class="absolute z-30 mt-1 p-1 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm shadow-lg flex flex-col text-[11px] w-32">
                {#each ['Normal', 'Sempit', 'Lebar', 'Cermin'] as m}
                  <button type="button" onmousedown={(e) => { e.preventDefault(); onmargin(m); popover = null; }} class="text-left px-2 py-1 rounded-sm hover:bg-[var(--bg-surface)] text-[var(--text-primary)]">{m}</button>
                {/each}
              </div>
            {/if}
          </div>
          <RibbonButton title="Orientasi" onclick={() => onorientation()}><Columns3 class="w-4 h-4" /><span class="text-[10px] font-code">Orientasi</span></RibbonButton>
          <div class="relative" data-popover>
            <RibbonButton title="Kolom" onclick={() => pick('cols')}><Columns2 class="w-4 h-4" /><span class="text-[10px] font-code">Kolom</span></RibbonButton>
            {#if popover === 'cols'}
              <div class="absolute z-30 mt-1 p-1 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm shadow-lg flex flex-col text-[11px] w-28">
                {#each [1, 2, 3, 4] as n}
                  <button type="button" onmousedown={(e) => { e.preventDefault(); oncolumns(n); popover = null; }} class="text-left px-2 py-1 rounded-sm hover:bg-[var(--bg-surface)] text-[var(--text-primary)]">{n} kolom</button>
                {/each}
              </div>
            {/if}
          </div>
        </RibbonGroup>
        <RibbonGroup label="Paragraf">
          <RibbonButton title="Indentasi kiri" onclick={() => run(() => paraFx.leftIndent(48))}><ArrowRightToLine class="w-4 h-4" /></RibbonButton>
          <RibbonButton title="Indentasi kanan" onclick={() => run(() => paraFx.rightIndent(48))}><ArrowLeftToLine class="w-4 h-4" /></RibbonButton>
          <RibbonButton title="Spasi sebelum" onclick={() => run(() => paraFx.spaceBefore(12))}><ArrowUp class="w-4 h-4" /></RibbonButton>
          <RibbonButton title="Spasi sesudah" onclick={() => run(() => paraFx.spaceAfter(12))}><ArrowDown class="w-4 h-4" /></RibbonButton>
        </RibbonGroup>
        <RibbonGroup label="Susun">
          <RibbonButton title="Naikkan paragraf" onclick={() => run(paraFx.moveUp)}><ArrowUp class="w-4 h-4" /></RibbonButton>
          <RibbonButton title="Turunkan paragraf" onclick={() => run(paraFx.moveDown)}><ArrowDown class="w-4 h-4" /></RibbonButton>
          <RibbonButton title="Garis horizontal" onclick={() => run(para.hr)}><Minus class="w-4 h-4" /></RibbonButton>
        </RibbonGroup>
        <RibbonGroup label="Kontrol Paragraf">
          <RibbonButton title="Jaga dengan berikutnya" onclick={() => run(() => paraFx.keepWithNext(true))}><ChevronUp class="w-4 h-4" /><span class="text-[9px]">↧</span></RibbonButton>
          <RibbonButton title="Jaga baris bersama" onclick={() => run(() => paraFx.keepLines(true))}><ListCollapse class="w-4 h-4" /></RibbonButton>
          <RibbonButton title="Kontrol widows/orphans" onclick={() => run(() => paraFx.widowControl(true))}><Pilcrow class="w-4 h-4" /></RibbonButton>
          <RibbonButton title="Pecah halaman sebelum" onclick={() => run(() => paraFx.pageBreakBefore(true))}><FileDown class="w-4 h-4" /></RibbonButton>
        </RibbonGroup>
      {/if}

      {#if shownTab === 'References'}
        <RibbonGroup label="Daftar Isi">
          <RibbonButton title="Sisipkan daftar isi" onclick={ontoggletoc}><BookOpen class="w-4 h-4" /><span class="text-[10px] font-code">Daftar Isi</span></RibbonButton>
          <RibbonButton title="Daftar gambar" onclick={ontableoffigures}><FileImage class="w-4 h-4" /><span class="text-[10px] font-code">Daftar Gambar</span></RibbonButton>
          <RibbonButton title="Indeks" onclick={oninsertindex}><BookOpenCheck class="w-4 h-4" /><span class="text-[10px] font-code">Indeks</span></RibbonButton>
        </RibbonGroup>
        <RibbonGroup label="Catatan Kaki">
          <RibbonButton title="Sisipkan catatan kaki" onclick={() => oninsertnote('footnote')}><Plus class="w-4 h-4" /><span class="text-[10px] font-code">Catatan Kaki</span></RibbonButton>
          <RibbonButton title="Sisipkan catatan akhir" onclick={() => oninsertnote('endnote')}><Plus class="w-4 h-4" /><span class="text-[10px] font-code">Catatan Akhir</span></RibbonButton>
        </RibbonGroup>
        <RibbonGroup label="Sitasi & Bibliografi">
          <RibbonButton title="Kelola sumber & sitasi" onclick={oncitations}><Quote class="w-4 h-4" /><span class="text-[10px] font-code">Sitasi</span></RibbonButton>
          <RibbonButton title="Daftar pustaka" onclick={() => oninsertbibliography()}><BookOpen class="w-4 h-4" /><span class="text-[10px] font-code">Pustaka</span></RibbonButton>
        </RibbonGroup>
        <RibbonGroup label="Keterangan">
          <RibbonButton title="Sisipkan keterangan" onclick={oninsertcaption}><FileText class="w-4 h-4" /><span class="text-[10px] font-code">Caption</span></RibbonButton>
          <RibbonButton title="Referensi silang" onclick={oncrossreference}><LinkIcon class="w-4 h-4" /><span class="text-[10px] font-code">Rujukan</span></RibbonButton>
        </RibbonGroup>
      {/if}

      {#if shownTab === 'Mailings'}
        <RibbonGroup label="Mulai Mail Merge">
          <RibbonButton title="Buka panel mail merge" onclick={onmailings}><FileText class="w-4 h-4" /><span class="text-[10px] font-code">Mail Merge</span></RibbonButton>
        </RibbonGroup>
        <RibbonGroup label="Amplop & Label">
          <RibbonButton title="Amplop" onclick={() => onlabels('Envelope C5')}><FileText class="w-4 h-4" /><span class="text-[10px] font-code">Amplop</span></RibbonButton>
          <RibbonButton title="Label" onclick={() => onlabels('Label 3×8')}><Grid3x3 class="w-4 h-4" /><span class="text-[10px] font-code">Label</span></RibbonButton>
        </RibbonGroup>
      {/if}

      {#if shownTab === 'Review'}
        <RibbonGroup label="Pemeriksaan">
          <RibbonButton title="Ejaan & tata bahasa" onclick={onspellcheck}><SpellCheck class="w-4 h-4" /><span class="text-[10px] font-code">Ejaan</span></RibbonButton>
          <RibbonButton title="Tesisaurus" onclick={onthesaurus}><BookOpenCheck class="w-4 h-4" /><span class="text-[10px] font-code">Tesisaurus</span></RibbonButton>
          <RibbonButton title="Hitung kata" onclick={onwordcount}><Tally5 class="w-4 h-4" /><span class="text-[10px] font-code">Hitung</span></RibbonButton>
          <RibbonButton title="Baca nyaring" onclick={onreadaloud}><Volume2 class="w-4 h-4" /><span class="text-[10px] font-code">Baca</span></RibbonButton>
          <RibbonButton title="Periksa aksesibilitas" onclick={oninspect}><ShieldCheck class="w-4 h-4" /><span class="text-[10px] font-code">Akses</span></RibbonButton>
        </RibbonGroup>
        <RibbonGroup label="Komentar">
          <RibbonButton title="Komentar baru" onclick={onnewcomment}><MessageSquarePlus class="w-4 h-4" /><span class="text-[10px] font-code">Komentar</span></RibbonButton>
          <RibbonButton title="Panel tinjauan" onclick={onreviewpane}><MessageSquare class="w-4 h-4" /><span class="text-[10px] font-code">Panel</span></RibbonButton>
        </RibbonGroup>
        <RibbonGroup label="Lacak Perubahan">
          <RibbonButton title="Lacak perubahan aktif" active={false} onclick={ontracking}><Languages class="w-4 h-4" /><span class="text-[10px] font-code">Lacak</span></RibbonButton>
          <RibbonButton title="Terima semua" onclick={onacceptall}><CheckCheck class="w-4 h-4" /><span class="text-[10px] font-code">Terima</span></RibbonButton>
          <RibbonButton title="Tolak semua" onclick={onrejectall}><XCircle class="w-4 h-4" /><span class="text-[10px] font-code">Tolak</span></RibbonButton>
        </RibbonGroup>
      {/if}

      {#if shownTab === 'View'}
        <RibbonGroup label="Tampilan">
          <RibbonButton title="Mode baca" active={readingMode} onclick={ontogglereading}><Eye class="w-4 h-4" /><span class="text-[10px] font-code">Baca</span></RibbonButton>
          <RibbonButton title="Panel navigasi" onclick={ontogglenavpane}><PanelLeft class="w-4 h-4" /><span class="text-[10px] font-code">Navigasi</span></RibbonButton>
          <RibbonButton title="Penggaris" onclick={ontoggleruler}><Ruler class="w-4 h-4" /><span class="text-[10px] font-code">Penggaris</span></RibbonButton>
          <RibbonButton title="Tanda format" onclick={ontogglemarks}><Pilcrow class="w-4 h-4" /><span class="text-[10px] font-code">Tanda</span></RibbonButton>
          <RibbonButton title="Satu / dua halaman" onclick={onpageview}><Columns2 class="w-4 h-4" /><span class="text-[10px] font-code">Halaman</span></RibbonButton>
          <RibbonButton title="Layar penuh" onclick={() => document.documentElement.requestFullscreen?.()}><Maximize class="w-4 h-4" /><span class="text-[10px] font-code">Penuh</span></RibbonButton>
        </RibbonGroup>
        <RibbonGroup label="Gelap">
          <RibbonButton title="Mode gelap" onclick={ontoggledarkpaper}><Moon class="w-4 h-4" /><span class="text-[10px] font-code">Gelap</span></RibbonButton>
          <RibbonButton title="Mode terang" onclick={ontoggledarkpaper}><Sun class="w-4 h-4" /><span class="text-[10px] font-code">Terang</span></RibbonButton>
        </RibbonGroup>
        <RibbonGroup label="Perbesaran">
          <RibbonButton title="Perkecil" onclick={() => onzoom(Math.max(50, zoom - 10))}><ZoomOut class="w-4 h-4" /></RibbonButton>
          <div class="w-12 text-center text-[11px] font-code text-[var(--text-primary)]">{zoom}%</div>
          <RibbonButton title="Perbesar" onclick={() => onzoom(Math.min(200, zoom + 10))}><ZoomIn class="w-4 h-4" /></RibbonButton>
          <RibbonButton title="100%" onclick={() => onzoom(100)}><span class="text-[11px] font-code">100%</span></RibbonButton>
        </RibbonGroup>
      {/if}

      {#if shownTab === 'Table'}
        <RibbonGroup label="Baris & Kolom">
          <RibbonButton title="Sisip baris di atas" onclick={() => run(table.addRowAbove)}><Rows3 class="w-4 h-4" /><ArrowUp class="w-3 h-3" /></RibbonButton>
          <RibbonButton title="Sisip baris di bawah" onclick={() => run(table.addRowBelow)}><Rows3 class="w-4 h-4" /><ArrowDown class="w-3 h-3" /></RibbonButton>
          <RibbonButton title="Sisip kolom kiri" onclick={() => run(table.addColumnLeft)}><Columns3 class="w-4 h-4" /><ArrowLeft class="w-3 h-3" /></RibbonButton>
          <RibbonButton title="Sisip kolom kanan" onclick={() => run(table.addColumnRight)}><Columns3 class="w-4 h-4" /><ArrowRight class="w-3 h-3" /></RibbonButton>
          <RibbonButton title="Hapus baris" onclick={() => run(table.deleteRow)}><Trash2 class="w-4 h-4" /><Rows3 class="w-3 h-3" /></RibbonButton>
          <RibbonButton title="Hapus kolom" onclick={() => run(table.deleteColumn)}><Trash2 class="w-4 h-4" /><Columns3 class="w-3 h-3" /></RibbonButton>
          <RibbonButton title="Hapus tabel" onclick={() => run(() => activeTable()?.remove())}><Trash2 class="w-4 h-4" /><Table class="w-3 h-3" /></RibbonButton>
        </RibbonGroup>
        <RibbonGroup label="Gabung">
          <RibbonButton title="Gabung sel" onclick={() => run(tableTools.mergeCells)}><Merge class="w-4 h-4" /><span class="text-[10px] font-code">Gabung</span></RibbonButton>
          <div class="relative" data-popover>
            <RibbonButton title="Pecah sel" onclick={() => pick('split')}><Split class="w-4 h-4" /><span class="text-[10px] font-code">Pecah</span></RibbonButton>
            {#if popover === 'split'}
              <div class="absolute z-30 mt-1 p-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm shadow-lg flex items-center gap-1">
                <input type="number" min="1" max="10" bind:value={spanRows} class="w-10 px-1 py-0.5 text-[11px] bg-[var(--bg-surface)] border border-[var(--border-color)] rounded-sm text-[var(--text-primary)]" />
                <span class="text-[10px]">×</span>
                <input type="number" min="1" max="10" bind:value={spanCols} class="w-10 px-1 py-0.5 text-[11px] bg-[var(--bg-surface)] border border-[var(--border-color)] rounded-sm text-[var(--text-primary)]" />
                <button type="button" onmousedown={(e) => { e.preventDefault(); run(() => tableTools.splitCell(spanRows, spanCols)); popover = null; }} class="px-2 py-0.5 text-[10px] bg-[var(--accent-primary)] text-[var(--on-accent)] rounded-sm">OK</button>
              </div>
            {/if}
          </div>
        </RibbonGroup>
        <RibbonGroup label="Ukuran Sel">
          <RibbonButton title="Bagi rata kolom" onclick={() => run(tableTools.distributeColumns)}><Columns3 class="w-4 h-4" /></RibbonButton>
          <RibbonButton title="AutoFit" onclick={() => run(tableTools.autoFit)}><Maximize2 class="w-4 h-4" /></RibbonButton>
        </RibbonGroup>
        <RibbonGroup label="Desain Tabel">
          <RibbonButton title="Baris belang" onclick={() => run(() => tableTools.bandedRows(true))}><TableProperties class="w-4 h-4" /><span class="text-[9px]">▤</span></RibbonButton>
          <RibbonButton title="Baris judul berulang" onclick={() => run(() => tableTools.repeatHeader(true))}><Rows3 class="w-4 h-4" /><span class="text-[9px]">↺</span></RibbonButton>
          <RibbonButton title="Kolom pertama tebal" onclick={() => run(() => tableTools.firstColumn(true))}><Bold class="w-4 h-4" /><span class="text-[9px]">1st</span></RibbonButton>
          <div class="relative" data-popover>
            <RibbonButton title="Warna sel" onclick={() => pick('shade')}><PaintRoller class="w-4 h-4" /></RibbonButton>
            {#if popover === 'shade'}
              <div class="absolute z-30 mt-1 p-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm shadow-lg grid grid-cols-3 gap-1">
                {#each shadingPresets as c}
                  <button type="button" onmousedown={(e) => { e.preventDefault(); run(() => tableTools.shade(c)); popover = null; }} class="w-6 h-6 rounded-sm border border-[var(--border-color)]" style:background={c === 'transparent' ? 'var(--bg-surface)' : c} title={c}></button>
                {/each}
              </div>
            {/if}
          </div>
          <RibbonButton title="Batas sel" onclick={ontableborders}><SquareDashedBottomCode class="w-4 h-4" /></RibbonButton>
        </RibbonGroup>
        <RibbonGroup label="Data">
          <RibbonButton title="Urutkan membesar" onclick={() => run(() => tableTools.sort(true))}><ArrowUpDown class="w-4 h-4" /><span class="text-[9px]">↑</span></RibbonButton>
          <RibbonButton title="Urutkan mengecil" onclick={() => run(() => tableTools.sort(false))}><ArrowUpDown class="w-4 h-4" /><span class="text-[9px]">↓</span></RibbonButton>
          <RibbonButton title="Hitung rumus" onclick={() => run(tableTools.formulas)}><Sigma class="w-4 h-4" /><span class="text-[10px] font-code">Rumus</span></RibbonButton>
          <RibbonButton title="Tabel → Teks" onclick={() => run(tableTools.toText)}><FileText class="w-4 h-4" /></RibbonButton>
        </RibbonGroup>
      {/if}

      {#if shownTab === 'Picture'}
        <RibbonGroup label="Sesuaikan">
          <RibbonButton title="Panel format gambar" onclick={onpictureformat}><ImageIcon class="w-4 h-4" /><span class="text-[10px] font-code">Format</span></RibbonButton>
          <RibbonButton title="Pangkas" onclick={() => run(() => onpictureformat())}><Crop class="w-4 h-4" /><span class="text-[10px] font-code">Pangkas</span></RibbonButton>
          <RibbonButton title="Putar" onclick={() => onpictureformat()}><RotateCw class="w-4 h-4" /><span class="text-[10px] font-code">Putar</span></RibbonButton>
        </RibbonGroup>
        <RibbonGroup label="Gaya Gambar">
          <RibbonButton title="Bingkai gambar" onclick={() => onpictureformat()}><SquareDashedBottomCode class="w-4 h-4" /><span class="text-[10px] font-code">Bingkai</span></RibbonButton>
          <RibbonButton title="Teks alternatif" onclick={() => onpictureformat()}><Type class="w-4 h-4" /><span class="text-[10px] font-code">Alt</span></RibbonButton>
          <RibbonButton title="Bungkus teks" onclick={() => onpictureformat()}><WrapText class="w-4 h-4" /><span class="text-[10px] font-code">Bungkus</span></RibbonButton>
        </RibbonGroup>
      {/if}
    </div>
  {/if}

  <!-- Quick-access file bar -->
  <div class="flex items-center gap-1 px-2 py-1 border-t border-[var(--border-color)]/40 bg-[var(--bg-elevated)]/30 overflow-x-auto">
    <RibbonButton title="Simpan (Ctrl+S)" onclick={onsave}><Save class="w-3.5 h-3.5" /><span class="text-[10px] font-code">SIMPAN</span></RibbonButton>
    <RibbonButton title="Buka dari disk" onclick={onopen}><FolderOpen class="w-3.5 h-3.5" /><span class="text-[10px] font-code">BUKA</span></RibbonButton>
    <RibbonButton title="Ekspor .docx" onclick={() => onexport('docx')}><FileDown class="w-3.5 h-3.5" /><span class="text-[10px] font-code">.DOCX</span></RibbonButton>
    <RibbonButton title="Ekspor Markdown" onclick={() => onexport('md')}><FileDown class="w-3.5 h-3.5" /><span class="text-[10px] font-code">.MD</span></RibbonButton>
    <RibbonButton title="Ekspor HTML" onclick={() => onexport('html')}><Download class="w-3.5 h-3.5" /><span class="text-[10px] font-code">.HTML</span></RibbonButton>
    <div class="w-px h-5 bg-[var(--border-color)] mx-1"></div>
    <RibbonButton title="Cetak / Simpan PDF (Ctrl+P)" onclick={onprint}><Printer class="w-3.5 h-3.5" /><span class="text-[10px] font-code">CETAK / PDF</span></RibbonButton>
    <div class="w-px h-5 bg-[var(--border-color)] mx-1"></div>
    <RibbonButton title="Undo" onclick={() => run(history.undo)}><Undo2 class="w-3.5 h-3.5" /></RibbonButton>
    <RibbonButton title="Redo" onclick={() => run(history.redo)}><Redo2 class="w-3.5 h-3.5" /></RibbonButton>
  </div>
</div>

<script lang="ts" module>
  import { currentBlock } from './commands';
  import { activeTable } from './tableTools';
  import { quickTable, shape, icon, equation } from './insertBlocks';
  import { textToTable } from './paraFx';

  function paraFxSetList(style: string) {
    const block = currentBlock();
    if (!block) return;
    const list = block.closest('ul,ol');
    if (list) {
      (list as HTMLElement).style.listStyleType = style;
      return;
    }
    document.execCommand(style.startsWith('lower') || style.startsWith('upper') || style === 'decimal' ? 'insertOrderedList' : 'insertUnorderedList');
    const created = currentBlock()?.closest('ul,ol') as HTMLElement | null;
    if (created) created.style.listStyleType = style;
  }
</script>
