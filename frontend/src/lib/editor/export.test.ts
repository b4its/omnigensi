/**
 * Unit tests for the export pipeline: Markdown/HTML/TXT serialisation and the
 * import helpers.
 */
import { describe, expect, it } from 'vitest';
import { htmlToMarkdown, readImportedFile, serialize } from './export';

function el(html: string): HTMLElement {
	const div = document.createElement('div');
	div.innerHTML = html;
	return div;
}

describe('htmlToMarkdown', () => {
	it('renders headings and inline styles', () => {
		const md = htmlToMarkdown(el('<h1>Judul</h1><p>Halo <strong>dunia</strong></p>'));
		expect(md).toContain('# Judul');
		expect(md).toContain('**dunia**');
	});

	it('renders lists, links and tables', () => {
		const md = htmlToMarkdown(
			el('<ul><li>a</li><li>b</li></ul><p><a href="https://x">link</a></p><table><tr><td>1</td><td>2</td></tr></table>')
		);
		expect(md).toContain('- a');
		expect(md).toContain('[link](https://x)');
		expect(md).toContain('| 1 | 2 |');
	});
});

describe('serialize', () => {
	it('wraps html output in a document', () => {
		const out = serialize('<p>isi</p>', 'html', 'Judul');
		expect(out).toContain('<!doctype html>');
		expect(out).toContain('<title>Judul</title>');
	});

	it('emits an Office namespace for the .doc format', () => {
		const out = serialize('<p>isi</p>', 'doc');
		expect(out).toContain('urn:schemas-microsoft-com:office:word');
	});

	it('strips page-break markers', () => {
		const out = serialize('<p>a</p><div class="naskah-pagebreak"></div>', 'html');
		expect(out).not.toContain('naskah-pagebreak');
	});

	it('produces RTF and LaTeX', () => {
		expect(serialize('<p>Halo</p>', 'rtf')).toContain('{\\rtf1');
		expect(serialize('<h1>Bab</h1>', 'tex')).toContain('\\section{Bab}');
	});

	it('flattens to text for .txt', () => {
		expect(serialize('<p>halo</p>', 'txt').trim()).toBe('halo');
	});
});

describe('readImportedFile', () => {
	function file(name: string, body: string): File {
		return new File([body], name, { type: 'text/plain' });
	}

	it('converts Markdown headings and bold', async () => {
		const html = await readImportedFile(file('x.md', '# Judul\n\n**tebal**'));
		expect(html).toContain('<h1>Judul</h1>');
		expect(html).toContain('<strong>tebal</strong>');
	});

	it('extracts the body of an HTML file', async () => {
		const html = await readImportedFile(file('x.html', '<html><body><p>isi</p></body></html>'));
		expect(html).toContain('<p>isi</p>');
	});

	it('wraps plain text into paragraphs', async () => {
		const html = await readImportedFile(file('x.txt', 'satu\n\ndua'));
		expect(html).toContain('<p>satu</p>');
		expect(html).toContain('<p>dua</p>');
	});

	it('converts a simple RTF paragraph', async () => {
		const html = await readImportedFile(file('x.rtf', '{\\rtf1 Halo dunia \\par}'));
		expect(html).toContain('Halo dunia');
	});
});
