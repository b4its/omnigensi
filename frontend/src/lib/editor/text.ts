/**
 * Plain-text helpers that do not depend on the browser-only `innerText`.
 *
 * jsdom (used by the Vitest suite) does not implement `innerText`, and it is
 * also absent from some older engines the app supports. `textOf()` walks the DOM
 * and reconstructs block-level line breaks, so the export pipeline and the word
 * counter behave identically everywhere.
 */

const BLOCK_TAGS = new Set([
	'P',
	'DIV',
	'H1',
	'H2',
	'H3',
	'H4',
	'H5',
	'H6',
	'LI',
	'TR',
	'BLOCKQUOTE',
	'PRE',
	'SECTION',
	'ARTICLE',
	'TABLE',
	'UL',
	'OL',
]);

export type TextMode = 'block' | 'spaced';

/**
 * Flatten a subtree to text.
 *
 * - `block` (default) puts a newline between block elements — a manuscript's
 *   paragraphs become separate lines.
 * - `spaced` puts a space where a tag boundary falls inside a line (e.g. two
 *   inline runs), so words are never glued together.
 */
export function textOf(node: Node | null | undefined, mode: TextMode = 'block'): string {
	if (!node) return '';
	if (node.nodeType === Node.TEXT_NODE) return node.nodeValue ?? '';
	if (node.nodeType !== Node.ELEMENT_NODE) {
		let out = '';
		node.childNodes.forEach((child) => (out += textOf(child, mode)));
		return out;
	}
	const el = node as HTMLElement;
	const tag = el.tagName;
	if (tag === 'BR') return '\n';
	if (tag === 'HR') return '\n';

	let inner = '';
	el.childNodes.forEach((child) => (inner += textOf(child, mode)));

	if (BLOCK_TAGS.has(tag)) {
		// Table rows share one line separated by tabs; cells hold their own text.
		if (tag === 'TR') {
			const cells = Array.from(el.children).map((cell) => textOf(cell, 'spaced').trim());
			inner = cells.join('\t');
		}
		return `\n${inner}\n`;
	}
	if (mode === 'spaced') return ` ${inner} `;
	return inner;
}

/** Normalised plain text: one newline between paragraphs, no hanging blanks. */
export function plainText(node: Node | null | undefined): string {
	return textOf(node)
		.replace(/\u00a0/g, ' ')
		.replace(/[ \t]+\n/g, '\n')
		.replace(/\n[ \t]+/g, '\n')
		.replace(/[ \t]{2,}/g, ' ')
		.replace(/\n{2,}/g, '\n')
		.trim();
}

/**
 * Word count over plain text. Paragraphs are runs separated by blank lines when
 * the source has them, otherwise each non-empty line counts as one.
 */
export interface PlainCount {
	words: number;
	characters: number;
	charactersNoSpaces: number;
	paragraphs: number;
	lines: number;
	pages: number;
}

export function countText(node: Node | null | undefined, pageCapacity = 500): PlainCount {
	const text = plainText(node);
	const trimmed = text.trim();
	const words = trimmed ? trimmed.split(/\s+/).length : 0;
	const lines = text ? text.split('\n').length : 0;
	const paragraphs = trimmed ? trimmed.split(/\n+/).filter((p) => p.trim()).length : 0;
	return {
		words,
		characters: text.length,
		charactersNoSpaces: text.replace(/\s/g, '').length,
		paragraphs,
		lines,
		pages: Math.max(1, Math.ceil(words / pageCapacity)),
	};
}
