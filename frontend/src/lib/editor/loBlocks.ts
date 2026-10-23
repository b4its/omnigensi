/**
 * loBlocks — the building blocks that are specific to LibreOffice Writer.
 *
 * These are the features a Writer user reaches for that have no direct Word
 * equivalent: AutoText (the Ctrl+F3 block library), Text Frames (Insert › Text
 * Box with anchoring and wrapping), text-linked columns, and the Writer
 * "Horizontal Line" gallery. Each builder emits the same markup family the rest
 * of the editor already understands (paragraphs, tables, inline CSS), so the
 * output survives export.
 */

function esc(s: string): string {
	return s.replace(/[&<>"']/g, (c) =>
		({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string
	);
}

// ── AutoText ───────────────────────────────────────────────────────────────

export interface AutoTextEntry {
	key: string;
	label: string;
	category: string;
	html: string;
}

/**
 * The built-in AutoText library. Writer ships a set of these on the Insert ›
 * AutoText menu; the list mirrors the categories an Indonesian writer needs and
 * is stored in the same shape so custom entries can be appended later.
 */
export const DEFAULT_AUTOTEXT: AutoTextEntry[] = [
	{ key: 'tt', label: 'Tanda tangan', category: 'Standar', html: '<p>Hormat saya,<br/><br/><br/>______________</p>' },
	{ key: 'ss', label: 'Salam pembuka', category: 'Surat', html: '<p>Dengan hormat,</p>' },
	{ key: 'st', label: 'Salam penutup', category: 'Surat', html: '<p>Atas perhatian Bapak/Ibu, kami sampaikan terima kasih.</p>' },
	{ key: 'nm', label: 'Nama & gelar', category: 'Standar', html: '<p>Nama Lengkap, S.Pd.</p>' },
	{ key: 'al', label: 'Alamat surat', category: 'Surat', html: '<p>Jalan ________ No. __<br/>Kel. ________, Kec. ________<br/>Kota ________ ________</p>' },
	{ key: 'kp', label: 'Kepala surat', category: 'Surat', html: '<p style="text-align:center;font-weight:700;font-size:14pt">NAMA INSTITUSI</p><p style="text-align:center;font-size:9pt">Alamat · Telepon · Email</p><hr/>' },
	{ key: 'dd', label: 'Daftar definisi', category: 'Daftar', html: '<dl><dt>Istilah</dt><dd>Penjelasan istilah.</dd></dl>' },
	{ key: 'tbd', label: 'Tabel data', category: 'Tabel', html: '<table class="naskah-table"><tbody><tr><th>Kolom 1</th><th>Kolom 2</th></tr><tr><td>&nbsp;</td><td>&nbsp;</td></tr></tbody></table><p><br/></p>' },
	{ key: 'mt', label: 'Metode penelitian', category: 'Dokumen', html: '<h3>Metode Penelitian</h3><p>Penelitian ini menggunakan pendekatan … dengan teknik pengumpulan data …</p>' },
	{ key: 'kl', label: 'Kesimpulan', category: 'Dokumen', html: '<h3>Kesimpulan</h3><p>Berdasarkan pembahasan di atas, dapat disimpulkan bahwa …</p>' },
];

const AUTOTEXT_KEY = 'omnigensi.naskah.autotext.v1';

/** Custom AutoText entries saved by the operator. */
export function loadCustomAutoText(): AutoTextEntry[] {
	try {
		const raw = localStorage.getItem(AUTOTEXT_KEY);
		return raw ? (JSON.parse(raw) as AutoTextEntry[]) : [];
	} catch {
		return [];
	}
}

export function saveCustomAutoText(entries: AutoTextEntry[]): void {
	try {
		localStorage.setItem(AUTOTEXT_KEY, JSON.stringify(entries));
	} catch {
		/* storage blocked */
	}
}

// ── Text frames ────────────────────────────────────────────────────────────

export type Anchor = 'toParagraph' | 'toCharacter' | 'toPage' | 'asCharacter';
export type Wrap = 'none' | 'left' | 'right' | 'both';

/** A floating text frame with Writer's anchor and wrap options. */
export function textFrame(
	text: string,
	opts: { anchor: Anchor; wrap: Wrap; width: string; align: 'left' | 'center' | 'right' } = {
		anchor: 'toParagraph',
		wrap: 'right',
		width: '240px',
		align: 'left',
	}
): string {
	const float = opts.wrap === 'left' ? 'left' : opts.wrap === 'right' ? 'right' : 'none';
	const justify = opts.wrap === 'both' ? 'margin:0 auto' : '';
	return `<div data-object="textframe" data-anchor="${opts.anchor}" data-wrap="${opts.wrap}" style="
    width:${opts.width};padding:8px 12px;border:1px solid #888;background:rgba(128,128,128,0.04);
    float:${float};margin:6px 10px 6px 0;${justify}">${esc(text) || 'Teks bingkai'}</div><p><br/></p>`;
}

// ── Fields ─────────────────────────────────────────────────────────────────

export type FieldKind =
	| 'insertedBy'
	| 'createdOn'
	| 'modifiedOn'
	| 'totalPages'
	| 'pageNumber'
	| 'wordCount'
	| 'title'
	| 'author'
	| 'fileName';

/**
 * Insert a Writer field. Time-sensitive fields are rendered as a non-editable
 * span carrying the field kind, so `refreshFields()` can update them later.
 */
export function fieldMarkup(
	kind: FieldKind,
	context: { author: string; title: string; wordCount: number; pageCount?: number }
): string {
	const value = (() => {
		switch (kind) {
			case 'insertedBy':
			case 'author':
				return context.author || 'Penulis';
			case 'createdOn':
			case 'modifiedOn':
				return new Date().toLocaleDateString('id-ID', { day: '2-digit', month: 'long', year: 'numeric' });
			case 'totalPages':
				return String(context.pageCount ?? 1);
			case 'pageNumber':
				return '[#]';
			case 'wordCount':
				return String(context.wordCount);
			case 'title':
				return context.title;
			case 'fileName':
				return `${context.title}.docx`;
		}
	})();
	return `<span data-object="field" data-field="${kind}" contenteditable="false" style="border:1px solid rgba(128,128,128,0.4);padding:0 2px">${esc(value)}</span>`;
}

/** Refresh every field in the document with current values. */
export function refreshFields(
	root: HTMLElement,
	context: { author: string; title: string; wordCount: number; pageCount?: number }
): number {
	let count = 0;
	root.querySelectorAll<HTMLElement>('[data-object="field"]').forEach((el) => {
		const kind = el.getAttribute('data-field') as FieldKind | null;
		if (!kind) return;
		const fresh = document.createElement('div');
		fresh.innerHTML = fieldMarkup(kind, context);
		const value = fresh.textContent ?? '';
		el.textContent = value;
		count++;
	});
	return count;
}

// ── Numbered / gallery lists ───────────────────────────────────────────────

export const LIST_GALLERY = [
	{ key: 'bullet', label: 'Butir', tag: 'ul', style: 'disc' },
	{ key: 'circle', label: 'Lingkaran', tag: 'ul', style: 'circle' },
	{ key: 'square', label: 'Kotak', tag: 'ul', style: 'square' },
	{ key: 'num', label: 'Angka', tag: 'ol', style: 'decimal' },
	{ key: 'alpha', label: 'Huruf kecil', tag: 'ol', style: 'lower-alpha' },
	{ key: 'roman', label: 'Romawi besar', tag: 'ol', style: 'upper-roman' },
] as const;

/** A fresh list at the caret with the gallery's marker style. */
export function listOf(style: (typeof LIST_GALLERY)[number]): string {
	const items =
		style.tag === 'ul'
			? '<li>Butir pertama</li><li>Butir kedua</li>'
			: '<li>Butir pertama</li><li>Butir kedua</li>';
	return `<${style.tag} style="list-style-type:${style.style}">${items}</${style.tag}><p><br/></p>`;
}

/** Ordered-list numbering restart / continued start value. */
export function listStart(number: number): void {
	const sel = window.getSelection();
	const node = sel?.anchorNode;
	const list = (node && node.nodeType === Node.ELEMENT_NODE ? (node as Element) : node?.parentElement)?.closest(
		'ol'
	) as HTMLOListElement | null;
	if (list && number > 0) {
		list.start = number;
		return;
	}
	// No list at the caret: create one with the requested start.
	document.execCommand('insertOrderedList');
	const created = currentList();
	if (created) created.start = number;
}

function currentList(): HTMLOListElement | null {
	const sel = window.getSelection();
	const base = sel?.anchorNode;
	const element = base?.nodeType === Node.ELEMENT_NODE ? (base as Element) : base?.parentElement;
	return (element?.closest('ol') as HTMLOListElement | null) ?? null;
}

// ── Columns and lines ──────────────────────────────────────────────────────

/**
 * Writer's three-column section with separators, used as a page-setup preset
 * in place of Word's column dialog. Returns the CSS to apply to the paper.
 */
export function columnsCss(count: number, separator = true): string {
	const parts = [`column-count:${count}`, 'column-gap:2.2em'];
	if (separator) parts.push('column-rule:1px solid rgba(128,128,128,0.35)');
	return parts.join(';');
}

/** The Writer "Horizontal Line" gallery (thin, thick, double, ornamental). */
export const HORIZONTAL_LINES = [
	{ key: 'thin', label: 'Tipis', css: 'border-top:1px solid currentColor' },
	{ key: 'thick', label: 'Tebal', css: 'border-top:3px solid currentColor' },
	{ key: 'double', label: 'Ganda', css: 'border-top:3px double currentColor' },
	{ key: 'dashed', label: 'Putus-putus', css: 'border-top:1px dashed currentColor' },
	{ key: 'dotted', label: 'Titik-titik', css: 'border-top:1px dotted currentColor' },
] as const;

export function horizontalLine(key: (typeof HORIZONTAL_LINES)[number]['key']): string {
	const line = HORIZONTAL_LINES.find((l) => l.key === key) ?? HORIZONTAL_LINES[0];
	return `<hr style="border:0;${line.css};margin:1em 0"/>`;
}

// ── Fontwork ──────────────────────────────────────────────────────────────

export const FONTWORK_GALLERY = [
	{ key: 'arc', label: 'Busur' },
	{ key: 'circle', label: 'Lingkaran' },
	{ key: 'wave', label: 'Gelombang' },
	{ key: 'slant', label: 'Miring' },
] as const;

/** LibreOffice Fontwork text (the Writer counterpart of WordArt). */
export function fontwork(text: string, style: 'arc' | 'circle' | 'wave' | 'slant' = 'arc'): string {
	const base =
		'font-size:30pt;font-weight:800;letter-spacing:1px;text-align:center;-webkit-text-stroke:1px currentColor;color:transparent';
	const extra =
		style === 'slant'
			? 'transform:skewX(-12deg)'
			: style === 'wave'
				? 'text-shadow:0 3px 0 rgba(0,0,0,0.2);transform:rotate(-4deg)'
				: style === 'circle'
					? 'border-radius:50%;width:220px;height:220px;display:flex;align-items:center;justify-content:center;margin:0 auto;border:2px solid currentColor'
					: '';
	return `<p data-object="fontwork" data-fontwork="${style}" style="${base};${extra}">${esc(text)}</p>`;
}

// ── Quotation ─────────────────────────────────────────────────────────────

/** Writer's Block Quotation paragraph style, distinct from the inline quote. */
export function blockQuotation(text: string): string {
	return `<p data-object="blockquote" style="margin:1em 2.5em;font-style:italic;color:#444">${esc(text)}</p>`;
}
