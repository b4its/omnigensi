/**
 * references — footnotes, endnotes, citations, bibliography, captions, table
 * of figures and cross-references.
 *
 * Word stamps each note with an auto-numbering field and stitches the body of
 * the note to the source location. In an HTML manuscript the honest analogue
 * is: a superscript anchor carrying an id, plus a note block in a numbered
 * notes list at the foot of the page/section. We keep the pairing in `data-`
 * attributes so `updateNotes()` can renumber everything after an insert or a
 * delete without losing the association.
 */

export interface NotePair {
	refEl: HTMLElement;
	noteEl: HTMLElement;
}

export const CITATION_STYLES = ['APA', 'MLA', 'Chicago', 'IEEE'] as const;
export type CitationStyle = (typeof CITATION_STYLES)[number];

export interface Source {
	id: string;
	type: 'book' | 'journal' | 'website' | 'report';
	authors: string; // "Budi Santoso; Rina Wijaya"
	year: string;
	title: string;
	container?: string; // publisher, journal, site
	location?: string; // city / URL
	accessed?: string;
}

const NOTES_KEY = 'omnigensi.naskah.notes.v1';
const SOURCES_KEY = 'omnigensi.naskah.sources.v1';

// ── Footnotes & endnotes ───────────────────────────────────────────────────

let noteCounter = 0;
function nextNoteId(): string {
	noteCounter += 1;
	return `naskah-note-${Date.now().toString(36)}-${noteCounter}`;
}

/** HTML for a footnote/endnote anchor (sup) plus its note list block. */
export function noteMarkup(text: string, kind: 'footnote' | 'endnote' = 'footnote'): { anchor: string; block: string } {
	const id = nextNoteId();
	const marker = kind === 'footnote' ? id : `${id}-end`;
	const anchor = `<sup data-reftype="${kind}" data-ref="${marker}" class="naskah-noteref"><a href="#${marker}-body">[?]</a></sup>`;
	const block = `<li data-notetype="${kind}" id="${marker}-body" class="naskah-notetext">${escapeHtml(text)} <a href="#${marker}" style="font-size:8pt;color:#888">↩</a></li>`;
	return { anchor, block };
}

/** Ensure the notes container exists at the end of the document. */
export function ensureNotesList(root: HTMLElement, kind: 'footnote' | 'endnote'): HTMLOListElement {
	let list = root.querySelector<HTMLOListElement>(`ol[data-notes="${kind}"]`);
	if (list) return list;
	list = document.createElement('ol');
	list.setAttribute('data-notes', kind);
	list.setAttribute('data-object', 'notes');
	list.style.cssText =
		'border-top:1px solid #bbb;margin-top:24px;padding-top:8px;font-size:9pt;line-height:1.35;color:#555';
	const heading = document.createElement('div');
	heading.setAttribute('contenteditable', 'false');
	heading.textContent = kind === 'footnote' ? 'Catatan Kaki' : 'Catatan Akhir';
	heading.style.cssText = 'font-weight:700;font-size:10pt;margin-bottom:4px;color:#333';
	root.insertBefore(heading, null);
	root.insertBefore(list, null);
	return list;
}

/** Renumber every note reference in document order and fix the anchor text. */
export function renumberNotes(root: HTMLElement): void {
	for (const kind of ['footnote', 'endnote'] as const) {
		const list = root.querySelector<HTMLOListElement>(`ol[data-notes="${kind}"]`);
		const refs = Array.from(root.querySelectorAll<HTMLElement>(`sup[data-reftype="${kind}"]`));
		refs.forEach((ref, i) => {
			const link = ref.querySelector('a');
			if (link) link.textContent = `[${i + 1}]`;
			ref.setAttribute('data-number', String(i + 1));
		});
		void list;
	}
}

/** Persist the plain text of every footnote for recovery. */
export function snapshotNotes(root: HTMLElement): Record<string, string> {
	const out: Record<string, string> = {};
	root.querySelectorAll<HTMLElement>('li.naskah-notetext').forEach((li) => {
		const id = li.id.replace(/-body$/, '');
		out[id] = (li.textContent ?? '').trim();
	});
	return out;
}

export function saveNotesSnapshot(root: HTMLElement): void {
	try {
		localStorage.setItem(NOTES_KEY, JSON.stringify(snapshotNotes(root)));
	} catch {
		/* ignore */
	}
}

// ── Citations & bibliography ───────────────────────────────────────────────

export function loadSources(): Source[] {
	try {
		const raw = localStorage.getItem(SOURCES_KEY);
		return raw ? (JSON.parse(raw) as Source[]) : [];
	} catch {
		return [];
	}
}

export function saveSources(sources: Source[]): void {
	try {
		localStorage.setItem(SOURCES_KEY, JSON.stringify(sources));
	} catch {
		/* ignore */
	}
}

function names(src: Source): string[] {
	return src.authors
		.split(/[;]/)
		.map((s) => s.trim())
		.filter(Boolean);
}

/** Format one source in the chosen citation style. */
export function formatSource(src: Source, style: CitationStyle): string {
	const who = names(src);
	const first = who[0] ?? 'Anonim';
	const formatted = (() => {
		switch (style) {
			case 'APA':
				return `${formattedAuthors(who)} (${src.year}). ${src.title}. ${src.container ?? ''}${src.location ? `, ${src.location}` : ''}.`;
			case 'MLA':
				return `${first}, et al. "${src.title}." ${src.container ?? ''}, ${src.year}${src.location ? `, ${src.location}` : ''}.`;
			case 'Chicago':
				return `${first}. ${src.title}. ${src.location ?? ''}: ${src.container ?? ''}, ${src.year}.`;
			case 'IEEE':
				return `${who.join(', ')}, "${src.title}," ${src.container ?? ''}${src.year ? `, ${src.year}` : ''}${src.location ? `, ${src.location}` : ''}.`;
		}
	})();
	return formatted.replace(/\s+/g, ' ').replace(/\.\s*\./g, '.').trim();
}

function formattedAuthors(who: string[]): string {
	return who
		.map((n) => {
			const parts = n.split(/\s+/);
			const last = parts.pop() ?? n;
			const initials = parts.map((p) => `${p.charAt(0)}.`).join(' ');
			return `${last}, ${initials}`.trim();
		})
		.join('; ');
}

/** In-text short form, e.g. "(Santoso, 2024)". */
export function shortCite(src: Source, style: CitationStyle): string {
	const first = names(src)[0] ?? 'Anonim';
	const surname = first.split(/\s+/).pop() ?? first;
	return style === 'IEEE' ? `[${src.id}]` : `(${surname}, ${src.year})`;
}

/** Insert an in-text citation at the caret. */
export function insertCitation(src: Source, style: CitationStyle): void {
	const text = shortCite(src, style);
	document.execCommand(
		'insertHTML',
		false,
		`<span data-object="citation" data-source="${escapeAttr(src.id)}" title="${escapeAttr(formatSource(src, style))}">${escapeHtml(text)}</span>`
	);
}

/** Build a bibliography block from the sources actually cited. */
export function bibliographyMarkup(cites: Source[], style: CitationStyle, title = 'Daftar Pustaka'): string {
	const sorted = [...cites].sort((a, b) => formatSource(a, style).localeCompare(formatSource(b, style)));
	const entries = sorted
		.map((s) => `<p style="margin:0 0 8px;padding-left:24px;text-indent:-24px">${escapeHtml(formatSource(s, style))}</p>`)
		.join('');
	return `<div data-object="bibliography"><h2>${escapeHtml(title)}</h2>${entries}</div><p><br/></p>`;
}

// ── Captions & table of figures ────────────────────────────────────────────

const CAPTION_COUNTERS: Record<string, number> = { Gambar: 0, Tabel: 0, Persamaan: 0 };

/** Reset the caption counters (e.g. before renumbering the whole document). */
export function resetCaptions(): void {
	for (const k of Object.keys(CAPTION_COUNTERS)) CAPTION_COUNTERS[k] = 0;
}

/** Insert a caption paragraph; returns the label used. */
export function captionMarkup(label = 'Gambar', text = 'Keterangan'): string {
	CAPTION_COUNTERS[label] = (CAPTION_COUNTERS[label] ?? 0) + 1;
	const n = CAPTION_COUNTERS[label];
	return `<p data-object="caption" data-caption-label="${escapeAttr(label)}" data-caption-n="${n}" style="text-align:center;font-size:10pt;color:#666;font-style:italic">${escapeHtml(
		label
	)} ${n}: ${escapeHtml(text)}</p>`;
}

/** Renumber captions in document order, keeping their label groups separate. */
export function renumberCaptions(root: HTMLElement): void {
	const counters: Record<string, number> = {};
	root.querySelectorAll<HTMLElement>('p[data-object="caption"]').forEach((p) => {
		const label = p.getAttribute('data-caption-label') ?? 'Gambar';
		counters[label] = (counters[label] ?? 0) + 1;
		const n = counters[label];
		p.setAttribute('data-caption-n', String(n));
		const colon = (p.textContent ?? '').indexOf(':');
		if (colon >= 0) p.textContent = `${label} ${n}${(p.textContent ?? '').slice(colon)}`;
	});
}

/** A table of figures listing every caption in reading order. */
export function tableOfFigures(root: HTMLElement, label?: string, title = 'Daftar Gambar'): string {
	const items = Array.from(root.querySelectorAll<HTMLElement>('p[data-object="caption"]'))
		.filter((p) => !label || p.getAttribute('data-caption-label') === label)
		.map((p) => `<div style="display:flex;align-items:baseline;margin:2px 0"><span>${escapeHtml(
			(p.textContent ?? '').trim()
		)}</span><span style="flex:1;border-bottom:1px dotted #999;margin:0 6px 4px"></span></div>`)
		.join('');
	return `<div data-object="table-of-figures"><h2>${escapeHtml(title)}</h2>${
		items || '<p style="color:#888">[Belum ada keterangan gambar]</p>'
	}</div><p><br/></p>`;
}

// ── Cross-references & index ───────────────────────────────────────────────

/** Insert a cross-reference to a heading or a bookmarked location. */
export function crossReferenceMarkup(targetId: string, label: string): string {
	return `<a data-object="crossref" href="#${escapeAttr(targetId)}" style="color:inherit;text-decoration:underline dotted">${escapeHtml(
		label
	)}</a>`;
}

/** Mark an index entry and open an index block at the end of the document. */
export function indexEntryMarkup(term: string): { mark: string; index: string } {
	const mark = `<span data-object="index-entry" data-term="${escapeAttr(term)}" style="display:none">${escapeHtml(term)}</span>`;
	const index = `<div data-object="index"><h2>Indeks</h2><p style="color:#555">${escapeHtml(term)}</p></div>`;
	return { mark, index };
}

// ── Utilities ──────────────────────────────────────────────────────────────

function escapeHtml(s: string): string {
	return s.replace(/[&<>"']/g, (c) =>
		({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string
	);
}
function escapeAttr(s: string): string {
	return escapeHtml(s);
}
