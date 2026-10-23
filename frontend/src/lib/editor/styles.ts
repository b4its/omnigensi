/**
 * styles — Wordcraft's Styles gallery model.
 *
 * Each style is a named, reusable bundle of paragraph + character formatting.
 * Applying a style sets the block's tag and a `data-style` attribute (for
 * round-tripping and the style pane) plus the concrete CSS, so the document
 * looks right even when it leaves the app.
 */

import { selectedBlocks, currentBlock } from './commands';

export interface DocStyle {
	/** Display name, Word-style. */
	name: string;
	/** Block tag to impose, if any. */
	tag?: 'p' | 'h1' | 'h2' | 'h3' | 'h4' | 'blockquote' | 'pre';
	/** Inline CSS applied to the block. */
	css: Record<string, string>;
	/** Short preview text shown in the gallery. */
	preview: string;
	/** Paragraph-level style? Character-only styles omit `tag`. */
	paragraph?: boolean;
}

export const BUILTIN_STYLES: DocStyle[] = [
	{ name: 'Normal', tag: 'p', preview: 'Teks isi paragraf', paragraph: true, css: {} },
	{
		name: 'Title',
		tag: 'h1',
		preview: 'Judul dokumen',
		paragraph: true,
		css: { 'font-size': '28pt', 'font-weight': '700', 'margin-bottom': '8pt', 'line-height': '1.15' },
	},
	{
		name: 'Subtitle',
		tag: 'p',
		preview: 'Subjudul',
		paragraph: true,
		css: { 'font-size': '14pt', 'font-style': 'italic', color: '#666666', 'margin-bottom': '10pt' },
	},
	{
		name: 'Heading 1',
		tag: 'h1',
		preview: 'Heading 1',
		paragraph: true,
		css: { 'font-size': '20pt', 'font-weight': '700', 'margin-top': '12pt', 'margin-bottom': '6pt' },
	},
	{
		name: 'Heading 2',
		tag: 'h2',
		preview: 'Heading 2',
		paragraph: true,
		css: { 'font-size': '16pt', 'font-weight': '700', 'margin-top': '10pt', 'margin-bottom': '5pt' },
	},
	{
		name: 'Heading 3',
		tag: 'h3',
		preview: 'Heading 3',
		paragraph: true,
		css: { 'font-size': '13pt', 'font-weight': '700', 'margin-top': '8pt', 'margin-bottom': '4pt' },
	},
	{
		name: 'Heading 4',
		tag: 'h4',
		preview: 'Heading 4',
		paragraph: true,
		css: { 'font-size': '12pt', 'font-weight': '700', 'font-style': 'italic', 'margin-top': '6pt' },
	},
	{
		name: 'Quote',
		tag: 'blockquote',
		preview: 'Kutipan panjang',
		paragraph: true,
		css: {
			'border-left': '3px solid #999999',
			'padding-left': '12px',
			'font-style': 'italic',
			color: '#555555',
			'margin-left': '24px',
		},
	},
	{
		name: 'Intense Quote',
		tag: 'blockquote',
		preview: 'Kutipan tebal',
		paragraph: true,
		css: {
			'border-left': '4px solid var(--accent-primary)',
			'padding': '8px 12px',
			'background': 'rgba(0,240,255,0.06)',
			'font-weight': '600',
		},
	},
	{
		name: 'Code',
		tag: 'pre',
		preview: 'console.log()',
		paragraph: true,
		css: { 'font-family': "'JetBrains Mono', monospace", 'font-size': '10pt', padding: '8px' },
	},
	{
		name: 'List Paragraph',
		tag: 'p',
		preview: '• Butir daftar',
		paragraph: true,
		css: { 'margin-left': '24px' },
	},
	{
		name: 'Caption',
		tag: 'p',
		preview: 'Gambar 1: keterangan',
		paragraph: true,
		css: { 'font-size': '10pt', 'font-style': 'italic', color: '#666666', 'text-align': 'center' },
	},
	{
		name: 'Footnote Text',
		tag: 'p',
		preview: 'Catatan kaki',
		paragraph: true,
		css: { 'font-size': '9pt', 'line-height': '1.2' },
	},
	{
		name: 'TOC Heading',
		tag: 'h2',
		preview: 'Daftar Isi',
		paragraph: true,
		css: {
			'font-size': '14pt',
			'letter-spacing': '0.06em',
			'text-transform': 'uppercase',
			'text-align': 'center',
		},
	},
	// Character styles (no block tag).
	{ name: 'Emphasis', preview: 'miring', css: { 'font-style': 'italic' }, paragraph: false },
	{ name: 'Strong', preview: 'tebal', css: { 'font-weight': '700' }, paragraph: false },
	{ name: 'Subtle Emphasis', preview: 'halus', css: { 'font-style': 'italic', color: '#777777' }, paragraph: false },
	{ name: 'Intense Emphasis', preview: 'tegas', css: { 'font-weight': '700', color: '#0066FF' }, paragraph: false },
];

/**
 * Apply a paragraph style to every selected block. Character-only styles are
 * applied inline to the current selection instead of replacing the block tag.
 */
export function applyStyle(style: DocStyle): void {
	if (!style.paragraph) {
		const sel = window.getSelection();
		if (!sel || sel.rangeCount === 0 || sel.isCollapsed) return;
		const span = document.createElement('span');
		span.setAttribute('data-style', style.name);
		for (const [k, v] of Object.entries(style.css)) span.style.setProperty(k, v);
		const range = sel.getRangeAt(0);
		try {
			range.surroundContents(span);
		} catch {
			span.appendChild(range.extractContents());
			range.insertNode(span);
		}
		return;
	}

	for (const block of selectedBlocks()) {
		if (style.tag) {
			// Normalise the tag in place so nested content survives.
			const replacement = document.createElement(style.tag);
			replacement.setAttribute('data-style', style.name);
			replacement.innerHTML = block.innerHTML;
			for (const attr of Array.from(block.attributes)) {
				if (!['style', 'data-style'].includes(attr.name)) replacement.setAttribute(attr.name, attr.value);
			}
			block.replaceWith(replacement);
		} else {
			block.setAttribute('data-style', style.name);
			block.style.cssText = '';
			for (const [k, v] of Object.entries(style.css)) block.style.setProperty(k, v);
		}
	}
	if (!selectedBlocks().length) {
		const one = currentBlock();
		if (one) one.setAttribute('data-style', style.name);
	}
}

/** The style object whose `name` matches, or Normal. */
export function findStyle(name: string, list: DocStyle[] = BUILTIN_STYLES): DocStyle {
	return list.find((s) => s.name === name) ?? BUILTIN_STYLES[0];
}

const CUSTOM_KEY = 'omnigensi.naskah.styles.v1';

/** Load user-created styles from localStorage. */
export function loadCustomStyles(): DocStyle[] {
	if (typeof localStorage === 'undefined') return [];
	try {
		const raw = localStorage.getItem(CUSTOM_KEY);
		return raw ? (JSON.parse(raw) as DocStyle[]) : [];
	} catch {
		return [];
	}
}

/** Persist user-created styles. */
export function saveCustomStyles(styles: DocStyle[]): void {
	try {
		localStorage.setItem(CUSTOM_KEY, JSON.stringify(styles));
	} catch {
		/* storage full or blocked */
	}
}

/** Build a new style from the formatting currently under the caret. */
export function newStyleFromSelection(name: string): DocStyle {
	const block = currentBlock();
	const css: Record<string, string> = {};
	if (block) {
		const computed = getComputedStyle(block);
		if (computed.fontFamily) css['font-family'] = computed.fontFamily;
		if (computed.fontSize) css['font-size'] = `${Math.round((parseFloat(computed.fontSize) * 72) / 96)}pt`;
		if (computed.fontWeight) css['font-weight'] = computed.fontWeight;
		if (computed.fontStyle) css['font-style'] = computed.fontStyle;
		if (computed.textAlign) css['text-align'] = computed.textAlign;
	}
	return {
		name,
		tag: (block?.tagName.toLowerCase() as DocStyle['tag']) ?? 'p',
		css,
		preview: name,
		paragraph: true,
	};
}
