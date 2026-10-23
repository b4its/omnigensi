<script lang="ts">
  /**
   * NaskahRibbon — a Word-style tabbed ribbon for the manuscript editor.
   *
   * Tabs mirror Microsoft Word / Wordcraft: File · Home · Insert · Design ·
   * Layout · References · View · Review. Every button issues a command from
   * `./commands`; actions that belong to the page (save, open, export, print,
   * find & replace modal, insert link/image dialogs) bubble up through the
   * `on*` callback props so this component stays presentational.
   *
   * Selection preservation: buttons fire on `mousedown` with preventDefault,
   * so the caret inside the contentEditable survives the interaction.
   */
  import RibbonGroup from './RibbonGroup.svelte';
  import RibbonButton from './RibbonButton.svelte';
  import { fmt, para, insert, history, isBlock, table } from './commands';
  import type { Align } from './commands';
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
    ArrowRightToLine,
    ArrowLeftToLine,
    Quote,
    Minus,
    Table,
    Image as ImageIcon,
    Link as LinkIcon,
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
  } from 'lucide-svelte';

  interface Props {
    getEditor: () => HTMLElement | undefined;
    zoom: number;
    pageWidth: number;
    marginY: number;
    readingMode: boolean;
    darkPaper: boolean;
    onsave: () => void;
    onopen: () => void;
    onexport: (format: 'doc' | 'html' | 'md' | 'txt') => void;
    onprint: () => void;
    oninsertlink: () => void;
    oninsertimage: () => void;
    oninsertdatetime: () => void;
    onfind: () => void;
    onfindnext: (backward: boolean) => void;
    onzoom: (zoom: number) => void;
    onpagemargin: (marginY: number) => void;
    onpagewidth: (width: number) => void;
    ontogglereading: () => void;
    ontoggledarkpaper: () => void;
  }

  let {
    getEditor,
    zoom,
    pageWidth,
    marginY,
    readingMode,
    darkPaper,
    onsave,
    onopen,
    onexport,
    onprint,
    oninsertlink,
    oninsertimage,
    oninsertdatetime,
    onfind,
    onfindnext,
    onzoom,
    onpagemargin,
    onpagewidth,
    ontogglereading,
    ontoggledarkpaper,
  }: Props = $props();

  type Tab = 'Home' | 'Insert' | 'Design' | 'Layout' | 'References' | 'View' | 'Review';
  // lucide-svelte icon components; typing them loosely avoids a Component
  // generic mismatch with the library's generated types.
  type IconCtor = typeof Type;
  const tabs: { name: Tab; icon: IconCtor }[] = [
    { name: 'Home', icon: Type },
    { name: 'Insert', icon: Table },
    { name: 'Design', icon: Palette },
    { name: 'Layout', icon: Columns3 },
    { name: 'References', icon: BookOpen },
    { name: 'View', icon: Eye },
    { name: 'Review', icon: Search },
  ];
  let activeTab = $state<Tab>('Home');

  // Reactive format states mirrored from selection so the ribbon can show the
  // pressed-ness of Bold/Italic/align etc. Updated by the page on selection
  // change through `refreshState`, or on each command.
  interface FmtState {
    bold: boolean;
    italic: boolean;
    underline: boolean;
    strike: boolean;
    sup: boolean;
    sub: boolean;
    align: Align;
    bullet: boolean;
    number: boolean;
    h1: boolean;
    h2: boolean;
    h3: boolean;
  }
  let fmtState = $state<FmtState>({
    bold: false,
    italic: false,
    underline: false,
    strike: false,
    sup: false,
    sub: false,
    align: 'left',
    bullet: false,
    number: false,
    h1: false,
    h2: false,
    h3: false,
  });

  export function refreshState() {
    try {
      fmtState = {
        bold: document.queryCommandState('bold'),
        italic: document.queryCommandState('italic'),
        underline: document.queryCommandState('underline'),
        strike: document.queryCommandState('strikeThrough'),
        sup: document.queryCommandState('superscript'),
        sub: document.queryCommandState('subscript'),
        align: document.queryCommandState('justifyFull')
          ? 'justify'
          : document.queryCommandState('justifyCenter')
            ? 'center'
            : document.queryCommandState('justifyRight')
              ? 'right'
              : 'left',
        bullet: document.queryCommandState('insertUnorderedList'),
        number: document.queryCommandState('insertOrderedList'),
        h1: isBlock('h1'),
        h2: isBlock('h2'),
        h3: isBlock('h3'),
      };
    } catch {
      /* queryCommandState is best-effort */
    }
  }

  const fonts = [
    'Times New Roman',
    'Georgia',
    'Arial',
    'Helvetica',
    'Calibri',
    'Cambria',
    'Courier New',
    'JetBrains Mono',
    'Verdana',
    'Garamond',
  ];
  const sizes = [8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36, 48, 72];
  const highlights = ['#FFEB3B', '#8BC34A', '#03A9F4', '#FF9800', '#E91E63', '#9C27B0', '#FFFFFF'];
  const colors = [
    '#000000',
    '#1A1A1A',
    '#FF0055',
    '#00F0FF',
    '#0066FF',
    '#00FF9D',
    '#FFB800',
    '#7C4DFF',
    '#E91E63',
    '#4CAF50',
    '#FFFFFF',
  ];

  let fontFamily = $state('Times New Roman');
  let fontSize = $state(12);
  let showHighlight = $state(false);
  let showColor = $state(false);
  let showTableGrid = $state(false);
  let tableRows = $state(3);
  let tableCols = $state(3);

  function run(fn: () => void) {
    fn();
    refreshState();
  }

  function setHeading(tag: 'p' | 'h1' | 'h2' | 'h3') {
    para.heading(tag);
    refreshState();
  }

  function applyTable() {
    insert.table(tableRows, tableCols);
    showTableGrid = false;
    refreshState();
  }

  // Close the open popovers when a mousedown lands outside any popover or its
  // trigger. Triggers/popovers carry `data-popover`; everything else closes.
  function closePopovers(e: MouseEvent) {
    const target = e.target as HTMLElement | null;
    if (target?.closest('[data-popover]')) return;
    showHighlight = false;
    showColor = false;
    showTableGrid = false;
  }
</script>

<svelte:window onmousedown={closePopovers} />

<div class="naskah-ribbon sticky top-0 z-20 border-b border-[var(--border-color)] bg-[var(--bg-surface)]">
  <!-- Tab strip + quick actions (hidden in reading mode) -->
  {#if !readingMode}
  <div class="flex items-center gap-0.5 px-2 pt-1.5 border-b border-[var(--border-color)]/50 overflow-x-auto">
    {#each tabs as tab}
      <button
        type="button"
        onmousedown={(e) => {
          e.preventDefault();
          activeTab = tab.name;
        }}
        class="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-hud tracking-wider rounded-t-sm whitespace-nowrap transition-colors
          {activeTab === tab.name
            ? 'bg-[var(--bg-elevated)] text-[var(--accent-primary)] border-b-2 border-[var(--accent-primary)]'
            : 'text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)]/50 border-b-2 border-transparent'}"
      >
        <tab.icon class="w-3.5 h-3.5" />
        {tab.name.toUpperCase()}
      </button>
    {/each}
  </div>
  {/if}

  <!-- Ribbon body (hidden in reading mode; a slim exit bar replaces it) -->
  {#if readingMode}
    <div class="flex items-center justify-between gap-2 px-3 py-1.5">
      <span class="text-[10px] font-code text-[var(--text-muted)]">
        MODE BACA · bilah alat disembunyikan
      </span>
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
  <div class="flex items-stretch gap-0 min-h-[74px] overflow-x-auto py-1">
    {#if activeTab === 'Home'}
      <RibbonGroup label="Clipboard">
        <RibbonButton title="Cut (Ctrl+X)" onclick={() => run(history.cut)}>
          <Scissors class="w-4 h-4" />
        </RibbonButton>
        <RibbonButton title="Copy (Ctrl+C)" onclick={() => run(history.copy)}>
          <Copy class="w-4 h-4" />
        </RibbonButton>
        <RibbonButton title="Paste (Ctrl+V)" onclick={() => run(history.paste)}>
          <Clipboard class="w-4 h-4" />
        </RibbonButton>
      </RibbonGroup>

      <RibbonGroup label="Undo">
        <RibbonButton title="Undo (Ctrl+Z)" onclick={() => run(history.undo)}>
          <Undo2 class="w-4 h-4" />
        </RibbonButton>
        <RibbonButton title="Redo (Ctrl+Y)" onclick={() => run(history.redo)}>
          <Redo2 class="w-4 h-4" />
        </RibbonButton>
      </RibbonGroup>

      <RibbonGroup label="Font" column>
        <div class="flex items-center gap-1 w-full">
          <select
            bind:value={fontFamily}
            onchange={() => run(() => fmt.fontName(fontFamily))}
            class="text-[11px] font-code bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm px-1 py-0.5 text-[var(--text-primary)] w-28"
            title="Font family"
          >
            {#each fonts as f}<option value={f}>{f}</option>{/each}
          </select>
          <select
            bind:value={fontSize}
            onchange={() => run(() => fmt.fontSize(fontSize))}
            class="text-[11px] font-code bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm px-1 py-0.5 text-[var(--text-primary)] w-14"
            title="Font size (pt)"
          >
            {#each sizes as s}<option value={s}>{s}</option>{/each}
          </select>
        </div>
        <div class="flex items-center gap-0.5 flex-wrap">
          <RibbonButton title="Bold (Ctrl+B)" active={fmtState.bold} onclick={() => run(fmt.bold)}>
            <Bold class="w-4 h-4" />
          </RibbonButton>
          <RibbonButton title="Italic (Ctrl+I)" active={fmtState.italic} onclick={() => run(fmt.italic)}>
            <Italic class="w-4 h-4" />
          </RibbonButton>
          <RibbonButton title="Underline (Ctrl+U)" active={fmtState.underline} onclick={() => run(fmt.underline)}>
            <Underline class="w-4 h-4" />
          </RibbonButton>
          <RibbonButton title="Strikethrough" active={fmtState.strike} onclick={() => run(fmt.strikethrough)}>
            <Strikethrough class="w-4 h-4" />
          </RibbonButton>
          <RibbonButton title="Superscript" active={fmtState.sup} onclick={() => run(fmt.superscript)}>
            <Superscript class="w-4 h-4" />
          </RibbonButton>
          <RibbonButton title="Subscript" active={fmtState.sub} onclick={() => run(fmt.subscript)}>
            <Subscript class="w-4 h-4" />
          </RibbonButton>
          <RibbonButton
            title="Change Case"
            onclick={() => run(() => fmt.changeCase('title'))}
          >
            <CaseSensitive class="w-4 h-4" />
          </RibbonButton>
          <div class="relative" data-popover>
            <RibbonButton title="Text highlight" onclick={() => (showHighlight = !showHighlight)}>
              <Highlighter class="w-4 h-4" />
            </RibbonButton>
            {#if showHighlight}
              <div class="absolute z-30 mt-1 p-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm shadow-lg grid grid-cols-4 gap-1">
                {#each highlights as h}
                  <button
                    type="button"
                    onmousedown={(e) => {
                      e.preventDefault();
                      run(() => fmt.highlight(h));
                      showHighlight = false;
                    }}
                    class="w-5 h-5 rounded-sm border border-white/20"
                    style:background={h}
                    title={h}
                  ></button>
                {/each}
              </div>
            {/if}
          </div>
          <div class="relative" data-popover>
            <RibbonButton title="Font color" onclick={() => (showColor = !showColor)}>
              <Baseline class="w-4 h-4 text-[var(--accent-primary)]" />
            </RibbonButton>
            {#if showColor}
              <div class="absolute z-30 mt-1 p-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm shadow-lg grid grid-cols-4 gap-1">
                {#each colors as c}
                  <button
                    type="button"
                    onmousedown={(e) => {
                      e.preventDefault();
                      run(() => fmt.color(c));
                      showColor = false;
                    }}
                    class="w-5 h-5 rounded-sm border border-white/20"
                    style:background={c}
                    title={c}
                  ></button>
                {/each}
              </div>
            {/if}
          </div>
          <RibbonButton title="Clear formatting" onclick={() => run(fmt.clear)}>
            <RemoveFormatting class="w-4 h-4" />
          </RibbonButton>
        </div>
      </RibbonGroup>

      <RibbonGroup label="Paragraph" column>
        <div class="flex items-center gap-0.5">
          <RibbonButton title="Align left" active={fmtState.align === 'left'} onclick={() => run(() => para.align('left'))}>
            <TextAlignStart class="w-4 h-4" />
          </RibbonButton>
          <RibbonButton title="Align center" active={fmtState.align === 'center'} onclick={() => run(() => para.align('center'))}>
            <TextAlignCenter class="w-4 h-4" />
          </RibbonButton>
          <RibbonButton title="Align right" active={fmtState.align === 'right'} onclick={() => run(() => para.align('right'))}>
            <TextAlignEnd class="w-4 h-4" />
          </RibbonButton>
          <RibbonButton title="Justify" active={fmtState.align === 'justify'} onclick={() => run(() => para.align('justify'))}>
            <TextAlignJustify class="w-4 h-4" />
          </RibbonButton>
        </div>
        <div class="flex items-center gap-0.5">
          <RibbonButton title="Bulleted list" active={fmtState.bullet} onclick={() => run(para.bulletList)}>
            <List class="w-4 h-4" />
          </RibbonButton>
          <RibbonButton title="Numbered list" active={fmtState.number} onclick={() => run(para.numberList)}>
            <ListOrdered class="w-4 h-4" />
          </RibbonButton>
          <RibbonButton title="Decrease indent" onclick={() => run(para.outdent)}>
            <ArrowLeftToLine class="w-4 h-4" />
          </RibbonButton>
          <RibbonButton title="Increase indent" onclick={() => run(para.indent)}>
            <ArrowRightToLine class="w-4 h-4" />
          </RibbonButton>
          <RibbonButton title="Line spacing 1.15" onclick={() => run(() => para.lineHeight('1.15'))}>
            <span class="text-[10px] font-code">1.15</span>
          </RibbonButton>
          <RibbonButton title="Line spacing 1.5" onclick={() => run(() => para.lineHeight('1.5'))}>
            <span class="text-[10px] font-code">1.5</span>
          </RibbonButton>
          <RibbonButton title="Line spacing 2.0" onclick={() => run(() => para.lineHeight('2'))}>
            <span class="text-[10px] font-code">2.0</span>
          </RibbonButton>
        </div>
      </RibbonGroup>

      <RibbonGroup label="Styles">
        <RibbonButton title="Heading 1" active={fmtState.h1} onclick={() => setHeading('h1')}>
          <Heading1 class="w-4 h-4" />
        </RibbonButton>
        <RibbonButton title="Heading 2" active={fmtState.h2} onclick={() => setHeading('h2')}>
          <Heading2 class="w-4 h-4" />
        </RibbonButton>
        <RibbonButton title="Heading 3" active={fmtState.h3} onclick={() => setHeading('h3')}>
          <Heading3 class="w-4 h-4" />
        </RibbonButton>
        <RibbonButton title="Normal text" onclick={() => setHeading('p')}>
          <Pilcrow class="w-4 h-4" />
        </RibbonButton>
        <RibbonButton title="Quote" onclick={() => run(para.quote)}>
          <Quote class="w-4 h-4" />
        </RibbonButton>
      </RibbonGroup>

      <RibbonGroup label="Editing">
        <RibbonButton title="Find & replace (Ctrl+F)" onclick={onfind}>
          <Search class="w-4 h-4" />
        </RibbonButton>
        <RibbonButton title="Find previous" onclick={() => onfindnext(true)}>
          <ChevronUp class="w-4 h-4" />
        </RibbonButton>
        <RibbonButton title="Find next (Ctrl+G)" onclick={() => onfindnext(false)}>
          <ChevronDown class="w-4 h-4" />
        </RibbonButton>
      </RibbonGroup>
    {/if}

    {#if activeTab === 'Insert'}
      <RibbonGroup label="Table">
        <div class="relative" data-popover>
          <RibbonButton title="Insert table" onclick={() => (showTableGrid = !showTableGrid)}>
            <Table class="w-4 h-4" />
            <span class="text-[11px] font-code">Tabel</span>
          </RibbonButton>
          {#if showTableGrid}
            <div class="absolute z-30 mt-1 p-2 bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-sm shadow-lg">
              <div class="grid gap-0.5" style:grid-template-columns="repeat(8, 1rem)">
                {#each Array(8 * 6) as _, i}
                  {@const r = Math.floor(i / 8) + 1}
                  {@const c = (i % 8) + 1}
                  <button
                    type="button"
                    onmouseenter={() => {
                      tableRows = r;
                      tableCols = c;
                    }}
                    onmousedown={(e) => {
                      e.preventDefault();
                      applyTable();
                    }}
                    class="w-4 h-4 border {r <= tableRows && c <= tableCols ? 'bg-[var(--accent-primary)]/50 border-[var(--accent-primary)]' : 'border-[var(--border-color)]'}"
                    title="{r} × {c}"
                  ></button>
                {/each}
              </div>
              <div class="text-center text-[10px] font-code text-[var(--text-muted)] mt-1">
                {tableRows} × {tableCols}
              </div>
            </div>
          {/if}
        </div>
      </RibbonGroup>

      <RibbonGroup label="Table Tools">
        <RibbonButton title="Add row above" onclick={() => run(table.addRowAbove)}>
          <Rows3 class="w-4 h-4" />
          <ArrowUp class="w-3 h-3" />
        </RibbonButton>
        <RibbonButton title="Add row below" onclick={() => run(table.addRowBelow)}>
          <Rows3 class="w-4 h-4" />
          <ArrowDown class="w-3 h-3" />
        </RibbonButton>
        <RibbonButton title="Add column left" onclick={() => run(table.addColumnLeft)}>
          <Columns3 class="w-4 h-4" />
          <ArrowLeft class="w-3 h-3" />
        </RibbonButton>
        <RibbonButton title="Add column right" onclick={() => run(table.addColumnRight)}>
          <Columns3 class="w-4 h-4" />
          <ArrowRight class="w-3 h-3" />
        </RibbonButton>
        <RibbonButton title="Delete row" onclick={() => run(table.deleteRow)}>
          <Trash2 class="w-4 h-4" />
          <Rows3 class="w-3 h-3" />
        </RibbonButton>
        <RibbonButton title="Delete column" onclick={() => run(table.deleteColumn)}>
          <Trash2 class="w-4 h-4" />
          <Columns3 class="w-3 h-3" />
        </RibbonButton>
      </RibbonGroup>

      <RibbonGroup label="Illustrations">
        <RibbonButton title="Insert image from URL / file" onclick={oninsertimage}>
          <ImageIcon class="w-4 h-4" />
          <span class="text-[11px] font-code">Gambar</span>
        </RibbonButton>
      </RibbonGroup>

      <RibbonGroup label="Links">
        <RibbonButton title="Insert hyperlink" onclick={oninsertlink}>
          <LinkIcon class="w-4 h-4" />
          <span class="text-[11px] font-code">Tautan</span>
        </RibbonButton>
      </RibbonGroup>

      <RibbonGroup label="Pages">
        <RibbonButton title="Insert page break" onclick={() => run(insert.pageBreak)}>
          <FileDown class="w-4 h-4" />
          <span class="text-[11px] font-code">Page Break</span>
        </RibbonButton>
        <RibbonButton title="Horizontal rule" onclick={() => run(para.hr)}>
          <Minus class="w-4 h-4" />
        </RibbonButton>
      </RibbonGroup>

      <RibbonGroup label="Symbols">
        <RibbonButton title="Em dash —" onclick={() => run(() => insert.text('—'))}>
          <span class="text-[13px]">—</span>
        </RibbonButton>
        <RibbonButton title="Copyright ©" onclick={() => run(() => insert.text('©'))}>
          <span class="text-[12px]">©</span>
        </RibbonButton>
        <RibbonButton title="Registered ®" onclick={() => run(() => insert.text('®'))}>
          <span class="text-[12px]">®</span>
        </RibbonButton>
        <RibbonButton title="Trademark ™" onclick={() => run(() => insert.text('™'))}>
          <span class="text-[12px]">™</span>
        </RibbonButton>
        <RibbonButton title="Bullet •" onclick={() => run(() => insert.text('•'))}>
          <span class="text-[12px]">•</span>
        </RibbonButton>
        <RibbonButton title="Insert date & time" onclick={oninsertdatetime}>
          <CalendarClock class="w-4 h-4" />
          <span class="text-[11px] font-code">Tanggal</span>
        </RibbonButton>
      </RibbonGroup>
    {/if}

    {#if activeTab === 'Design'}
      <RibbonGroup label="Theme">
        <RibbonButton title="Serif theme (Times)" onclick={() => run(() => fmt.fontName('Times New Roman'))}>
          <Type class="w-4 h-4" />
          <span class="text-[11px] font-code">Serif</span>
        </RibbonButton>
        <RibbonButton title="Sans theme (Arial)" onclick={() => run(() => fmt.fontName('Arial'))}>
          <Type class="w-4 h-4" />
          <span class="text-[11px] font-code">Sans</span>
        </RibbonButton>
        <RibbonButton title="Mono theme (Courier)" onclick={() => run(() => fmt.fontName('Courier New'))}>
          <Type class="w-4 h-4" />
          <span class="text-[11px] font-code">Mono</span>
        </RibbonButton>
      </RibbonGroup>
      <RibbonGroup label="Page">
        <RibbonButton title="Toggle dark paper" active={darkPaper} onclick={ontoggledarkpaper}>
          <Palette class="w-4 h-4" />
          <span class="text-[11px] font-code">Dark Paper</span>
        </RibbonButton>
      </RibbonGroup>
    {/if}

    {#if activeTab === 'Layout'}
      <RibbonGroup label="Page Setup">
        <RibbonButton title="Normal margins" onclick={() => onpagemargin(96)}>
          <Ruler class="w-4 h-4" />
          <span class="text-[11px] font-code">Normal</span>
        </RibbonButton>
        <RibbonButton title="Narrow margins" onclick={() => onpagemargin(48)}>
          <Ruler class="w-4 h-4" />
          <span class="text-[11px] font-code">Sempit</span>
        </RibbonButton>
        <RibbonButton title="Wide margins" onclick={() => onpagemargin(144)}>
          <Ruler class="w-4 h-4" />
          <span class="text-[11px] font-code">Lebar</span>
        </RibbonButton>
      </RibbonGroup>
      <RibbonGroup label="Page Width">
        <RibbonButton title="A4 (794px)" active={pageWidth === 794} onclick={() => onpagewidth(794)}>
          <span class="text-[11px] font-code">A4</span>
        </RibbonButton>
        <RibbonButton title="Letter (816px)" active={pageWidth === 816} onclick={() => onpagewidth(816)}>
          <span class="text-[11px] font-code">Letter</span>
        </RibbonButton>
        <RibbonButton title="A5 (559px)" active={pageWidth === 559} onclick={() => onpagewidth(559)}>
          <span class="text-[11px] font-code">A5</span>
        </RibbonButton>
      </RibbonGroup>
    {/if}

    {#if activeTab === 'References'}
      <RibbonGroup label="Table of Contents">
        <RibbonButton
          title="Insert table of contents placeholder"
          onclick={() =>
            run(() =>
              insert.html(
                '<h2>Daftar Isi</h2><p style="color:var(--text-muted)">[Daftar isi otomatis — tambahkan bab Anda di sini]</p>'
              )
            )}
        >
          <BookOpen class="w-4 h-4" />
          <span class="text-[11px] font-code">Daftar Isi</span>
        </RibbonButton>
      </RibbonGroup>
      <RibbonGroup label="Footnotes">
        <RibbonButton
          title="Insert footnote"
          onclick={() =>
            run(() =>
              insert.html('<sup title="footnote">[1]</sup>')
            )}
        >
          <span class="text-[11px] font-code">Catatan Kaki</span>
        </RibbonButton>
      </RibbonGroup>
      <RibbonGroup label="Captions">
        <RibbonButton
          title="Insert figure caption"
          onclick={() =>
            run(() =>
              insert.html(
                '<p style="text-align:center;font-size:10pt;color:var(--text-muted)">Gambar 1: Keterangan gambar</p>'
              )
            )}
        >
          <span class="text-[11px] font-code">Caption</span>
        </RibbonButton>
      </RibbonGroup>
    {/if}

    {#if activeTab === 'View'}
      <RibbonGroup label="Zoom">
        <RibbonButton title="Zoom out" onclick={() => onzoom(Math.max(50, zoom - 10))}>
          <ZoomOut class="w-4 h-4" />
        </RibbonButton>
        <div class="w-12 text-center text-[11px] font-code text-[var(--text-primary)]">{zoom}%</div>
        <RibbonButton title="Zoom in" onclick={() => onzoom(Math.min(200, zoom + 10))}>
          <ZoomIn class="w-4 h-4" />
        </RibbonButton>
        <RibbonButton title="100%" onclick={() => onzoom(100)}>
          <span class="text-[11px] font-code">100%</span>
        </RibbonButton>
      </RibbonGroup>
      <RibbonGroup label="Mode">
        <RibbonButton title="Reading mode" active={readingMode} onclick={ontogglereading}>
          <Eye class="w-4 h-4" />
          <span class="text-[11px] font-code">Baca</span>
        </RibbonButton>
      </RibbonGroup>
    {/if}

    {#if activeTab === 'Review'}
      <RibbonGroup label="Proofing">
        <RibbonButton title="Find & replace" onclick={onfind}>
          <Search class="w-4 h-4" />
          <span class="text-[11px] font-code">Cari</span>
        </RibbonButton>
      </RibbonGroup>
      <RibbonGroup label="Tracking">
        <RibbonButton
          title="Track changes (visual note)"
          onclick={() =>
            run(() =>
              insert.html(
                '<span style="background:rgba(0,240,255,0.15);border-bottom:1px dotted var(--accent-primary)">[revisi]</span>'
              )
            )}
        >
          <span class="text-[11px] font-code">Track</span>
        </RibbonButton>
      </RibbonGroup>
    {/if}
  </div>
  {/if}

  <!-- Quick-access file bar -->
  <div class="flex items-center gap-1 px-2 py-1 border-t border-[var(--border-color)]/40 bg-[var(--bg-elevated)]/30 overflow-x-auto">
    <RibbonButton title="Save to workspace (Ctrl+S)" onclick={onsave}>
      <Save class="w-3.5 h-3.5" />
      <span class="text-[10px] font-code">SIMPAN</span>
    </RibbonButton>
    <RibbonButton title="Open from disk" onclick={onopen}>
      <FolderOpen class="w-3.5 h-3.5" />
      <span class="text-[10px] font-code">BUKA</span>
    </RibbonButton>
    <RibbonButton title="Export .doc (Word)" onclick={() => onexport('doc')}>
      <FileDown class="w-3.5 h-3.5" />
      <span class="text-[10px] font-code">.DOC</span>
    </RibbonButton>
    <RibbonButton title="Export Markdown" onclick={() => onexport('md')}>
      <FileDown class="w-3.5 h-3.5" />
      <span class="text-[10px] font-code">.MD</span>
    </RibbonButton>
    <RibbonButton title="Export HTML" onclick={() => onexport('html')}>
      <Download class="w-3.5 h-3.5" />
      <span class="text-[10px] font-code">.HTML</span>
    </RibbonButton>
    <RibbonButton title="Export plain text" onclick={() => onexport('txt')}>
      <Download class="w-3.5 h-3.5" />
      <span class="text-[10px] font-code">.TXT</span>
    </RibbonButton>
    <div class="w-px h-5 bg-[var(--border-color)] mx-1"></div>
    <RibbonButton title="Print / Save as PDF" onclick={onprint}>
      <Printer class="w-3.5 h-3.5" />
      <span class="text-[10px] font-code">CETAK / PDF</span>
    </RibbonButton>
  </div>
</div>
