/**
 * Unit tests for the LibreOffice Writer building blocks: AutoText, text frames,
 * fields, list gallery, columns, horizontal lines and Fontwork.
 */
import { describe, expect, it, beforeEach } from 'vitest';
import {
	DEFAULT_AUTOTEXT,
	FONTWORK_GALLERY,
	HORIZONTAL_LINES,
	LIST_GALLERY,
	blockQuotation,
	columnsCss,
	fieldMarkup,
	fontwork,
	horizontalLine,
	listOf,
	refreshFields,
	saveCustomAutoText,
	loadCustomAutoText,
	textFrame,
} from './loBlocks';

describe('AutoText library', () => {
	it('ships Writer-style standard entries', () => {
		const keys = DEFAULT_AUTOTEXT.map((e) => e.key);
		expect(keys).toContain('tt');
		expect(keys).toContain('ss');
		expect(DEFAULT_AUTOTEXT.every((e) => e.html.length > 0)).toBe(true);
	});

	it('round-trips custom entries through storage', () => {
		const entry = { key: 'zz', label: 'Kustom', category: 'Pribadi', html: '<p>xx</p>' };
		saveCustomAutoText([entry]);
		expect(loadCustomAutoText()).toEqual([entry]);
	});
});

describe('textFrame', () => {
	it('carries anchor and wrap data attributes', () => {
		const html = textFrame('Isi', { anchor: 'toPage', wrap: 'left', width: '200px', align: 'left' });
		expect(html).toContain('data-anchor="toPage"');
		expect(html).toContain('data-wrap="left"');
		expect(html).toContain('float:left');
		expect(html).toContain('width:200px');
	});

	it('escapes its body text', () => {
		expect(textFrame('<b>x</b>')).toContain('&lt;b&gt;x&lt;/b&gt;');
	});
});

describe('fields', () => {
	const ctx = { author: 'Ani', title: 'Laporan', wordCount: 42 };

	it('renders the author and title fields from context', () => {
		expect(fieldMarkup('author', ctx)).toContain('Ani');
		expect(fieldMarkup('title', ctx)).toContain('Laporan');
	});

	it('renders the word count field', () => {
		expect(fieldMarkup('wordCount', ctx)).toContain('42');
	});

	it('refreshes every field in the document', () => {
		const root = document.createElement('div');
		root.innerHTML =
			'<span data-object="field" data-field="author">lama</span>' +
			'<span data-object="field" data-field="title">lama</span>';
		const n = refreshFields(root, ctx);
		expect(n).toBe(2);
		expect(root.textContent).toContain('Ani');
		expect(root.textContent).toContain('Laporan');
	});
});

describe('list gallery', () => {
	it('builds an unordered list for bullet styles', () => {
		const html = listOf(LIST_GALLERY[0]);
		expect(html).toContain('<ul');
		expect(html).toContain('list-style-type:disc');
	});

	it('builds an ordered list for numbering styles', () => {
		const html = listOf(LIST_GALLERY.find((g) => g.key === 'roman')!);
		expect(html).toContain('<ol');
		expect(html).toContain('upper-roman');
	});
});

describe('columns and lines', () => {
	it('adds a separator only when requested', () => {
		expect(columnsCss(2, true)).toContain('column-rule');
		expect(columnsCss(2, false)).not.toContain('column-rule');
	});

	it('renders each horizontal-line style', () => {
		for (const line of HORIZONTAL_LINES) {
			expect(horizontalLine(line.key)).toContain('<hr');
		}
	});

	it('renders a thick line with a 3px border', () => {
		expect(horizontalLine('thick')).toContain('3px solid');
	});
});

describe('fontwork', () => {
	it('exposes a gallery of shapes', () => {
		expect(FONTWORK_GALLERY.map((f) => f.key)).toContain('arc');
	});

	it('marks the heading and escapes text', () => {
		const html = fontwork('Halo <dunia>', 'slant');
		expect(html).toContain('data-object="fontwork"');
		expect(html).toContain('&lt;dunia&gt;');
		expect(html).toContain('skewX');
	});
});

describe('blockQuotation', () => {
	it('marks the paragraph as a block quotation', () => {
		expect(blockQuotation('kutipan')).toContain('data-object="blockquote"');
	});
});

beforeEach(() => {
	localStorage.clear();
});
