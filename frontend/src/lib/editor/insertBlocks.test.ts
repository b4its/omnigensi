/**
 * Unit tests for the insert building blocks and outline helpers.
 */
import { describe, expect, it } from 'vitest';
import { chart, coverPage, equation, icon, quickTable, renderMath, shape, smartArt, textBox } from './insertBlocks';
import { collectHeadings, renderToc, slug } from './headings';

describe('coverPage', () => {
	it('escapes the title and ends with a page break', () => {
		const html = coverPage('Laporan <A>', 'Sub');
		expect(html).toContain('Laporan &lt;A&gt;');
		expect(html).toContain('naskah-pagebreak');
	});

	it('supports each template variant', () => {
		expect(coverPage('T', '', 'Minimal')).toContain('naskah-cover-minimal');
		expect(coverPage('T', '', 'Laporan')).toContain('naskah-cover-report');
		expect(coverPage('T', '', 'Formal')).toContain('naskah-cover-formal');
	});
});

describe('quickTable', () => {
	it('renders headers and sample rows as a table', () => {
		const html = quickTable('Daftar Tugas');
		expect(html).toContain('<table');
		expect(html).toContain('<th>No</th>');
		expect(html).toContain('<td>1</td>');
	});
});

describe('shapes / icons', () => {
	it('draws polygon shapes as SVG', () => {
		expect(shape('star')).toContain('<svg');
		expect(shape('triangle')).toContain('<polygon');
	});

	it('draws rectangle shapes as a span', () => {
		expect(shape('rect', '#123456')).toContain('background:#123456');
	});

	it('escapes an icon glyph', () => {
		expect(icon('<')).toContain('&lt;');
	});
});

describe('charts / smart art', () => {
	it('draws bars for a bar chart', () => {
		expect(chart('bar', [1, 2, 3])).toContain('<rect');
	});

	it('draws slices for a pie chart', () => {
		expect(chart('pie', [1, 1, 1])).toContain('<path');
	});

	it('numbers SmartArt steps', () => {
		const html = smartArt(['A', 'B']);
		expect(html).toContain('>1<');
		expect(html).toContain('>2<');
	});
});

describe('renderMath', () => {
	it('renders fractions as a stacked span', () => {
		expect(renderMath('\\frac{a}{b}')).toContain('border-bottom');
	});

	it('renders superscripts and subscripts', () => {
		expect(renderMath('x^2 + y_{i}')).toContain('<sup>2</sup>');
		expect(renderMath('x^2 + y_{i}')).toContain('<sub>i</sub>');
	});

	it('replaces greek and operator commands', () => {
		expect(renderMath('\\pi \\times \\le')).toBe('π × ≤');
	});

	it('wraps a full equation block', () => {
		expect(equation('E = mc^2')).toContain('data-object="equation"');
	});
});

describe('textBox', () => {
	it('marks the object and escapes text', () => {
		const html = textBox('a <b>');
		expect(html).toContain('data-object="textbox"');
		expect(html).toContain('a &lt;b&gt;');
	});
});

describe('headings', () => {
	function doc(inner: string): HTMLElement {
		const div = document.createElement('div');
		div.innerHTML = inner;
		document.body.appendChild(div);
		return div;
	}

	it('collects heading levels in order', () => {
		const root = doc('<h1>Satu</h1><p>x</p><h3>Tiga</h3>');
		const hs = collectHeadings(root);
		expect(hs.map((h) => h.level)).toEqual([1, 3]);
	});

	it('assigns stable slugs as ids', () => {
		const root = doc('<h2>Bab Pertama</h2>');
		const [h] = collectHeadings(root);
		expect(h.text).toBe('Bab Pertama');
		expect(h.el.id).toContain('bab-pertama');
	});

	it('reuses an existing id', () => {
		const root = doc('<h2 id="tetap">Judul</h2>');
		expect(collectHeadings(root)[0].id).toBe('tetap');
	});

	it('renders a TOC with links to each heading', () => {
		const root = doc('<h1>Satu</h1><h2>Dua</h2>');
		const toc = renderToc(collectHeadings(root));
		expect(toc).toContain('Daftar Isi');
		expect(toc).toContain('href="#');
		expect(toc).toContain('Satu');
	});

	it('renders an empty-state TOC', () => {
		expect(renderToc([])).toContain('Belum ada judul');
	});

	it('slugifies accents and punctuation', () => {
		expect(slug('Résumé & CV!')).toBe('resume-cv');
	});
});
