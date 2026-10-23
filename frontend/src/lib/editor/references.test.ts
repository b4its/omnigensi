/**
 * Unit tests for references: note numbering, citation formatting,
 * bibliography, captions and figures.
 */
import { describe, expect, it } from 'vitest';
import {
	bibliographyMarkup,
	captionMarkup,
	crossReferenceMarkup,
	formatSource,
	noteMarkup,
	renumberCaptions,
	renumberNotes,
	resetCaptions,
	shortCite,
	tableOfFigures,
} from './references';
import type { Source } from './references';

const BOOK: Source = {
	id: 'src1',
	type: 'book',
	authors: 'Budi Santoso; Rina Wijaya',
	year: '2024',
	title: 'Dasar-Dasar Penulisan',
	container: 'Gramedia',
	location: 'Jakarta',
};

function doc(inner: string): HTMLElement {
	const div = document.createElement('div');
	div.innerHTML = inner;
	document.body.appendChild(div);
	return div;
}

describe('formatSource', () => {
	it('formats APA with formatted authors', () => {
		const out = formatSource(BOOK, 'APA');
		expect(out).toContain('Santoso, B.');
		expect(out).toContain('(2024)');
		expect(out).toContain('Dasar-Dasar Penulisan');
	});

	it('formats IEEE with a quoted title', () => {
		expect(formatSource(BOOK, 'IEEE')).toContain('"Dasar-Dasar Penulisan,"');
	});

	it('formats Chicago and MLA without throwing', () => {
		expect(formatSource(BOOK, 'Chicago')).toContain('2024');
		expect(formatSource(BOOK, 'MLA')).toContain('Budi Santoso');
	});
});

describe('shortCite', () => {
	it('uses surname + year in author-date styles', () => {
		expect(shortCite(BOOK, 'APA')).toBe('(Santoso, 2024)');
	});

	it('uses a numeric bracket in IEEE', () => {
		expect(shortCite(BOOK, 'IEEE')).toBe('[src1]');
	});
});

describe('bibliographyMarkup', () => {
	it('renders a heading and one entry per source', () => {
		const html = bibliographyMarkup([BOOK], 'APA');
		expect(html).toContain('Daftar Pustaka');
		expect(html).toContain('Santoso, B.');
	});
});

describe('noteMarkup / renumberNotes', () => {
	it('creates an anchor and a note body', () => {
		const { anchor, block } = noteMarkup('Catatan', 'footnote');
		expect(anchor).toContain('data-reftype="footnote"');
		expect(block).toContain('naskah-notetext');
	});

	it('numbers footnotes sequentially', () => {
		const root = doc(`
			<p>a<sup data-reftype="footnote" data-ref="x"><a>[?]</a></sup></p>
			<p>b<sup data-reftype="footnote" data-ref="y"><a>[?]</a></sup></p>`);
		renumberNotes(root);
		const links = Array.from(root.querySelectorAll('sup a')).map((a) => a.textContent);
		expect(links).toEqual(['[1]', '[2]']);
	});
});

describe('captions', () => {
	function root() {
		return doc(
			'<p data-object="caption" data-caption-label="Gambar" data-caption-n="9">Gambar 9: A</p>' +
				'<p data-object="caption" data-caption-label="Gambar" data-caption-n="9">Gambar 9: B</p>'
		);
	}

	it('renumbers captions of the same label in document order', () => {
		const el = root();
		renumberCaptions(el);
		const texts = Array.from(el.querySelectorAll('p')).map((p) => p.textContent);
		expect(texts[0]).toContain('Gambar 1:');
		expect(texts[1]).toContain('Gambar 2:');
	});

	it('builds a table of figures from captions', () => {
		const el = root();
		expect(tableOfFigures(el)).toContain('Daftar Gambar');
	});

	it('resets counters and produces sequential caption markup', () => {
		resetCaptions();
		expect(captionMarkup('Tabel', 'X')).toContain('Tabel 1: X');
	});
});

describe('crossReferenceMarkup', () => {
	it('links to the target anchor', () => {
		expect(crossReferenceMarkup('bab-1', 'Bab 1')).toContain('href="#bab-1"');
	});
});
