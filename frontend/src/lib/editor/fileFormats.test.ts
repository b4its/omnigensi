/**
 * Unit tests for the file formats: the store-only ZIP writer, the OOXML/ODT
 * package structure, RTF/LaTeX serialisation and template selection.
 */
import { describe, expect, it } from 'vitest';
import { buildDocx, buildLatex, buildOdt, buildRtf, htmlToWordBody, TEMPLATES, templateHtml } from './fileFormats';

const enc = (s: string) => new TextEncoder().encode(s);

/** Very small ZIP reader for the fields we assert on (names + magic bytes). */
function listZipNames(bytes: Uint8Array): string[] {
	const names: string[] = [];
	const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
	let p = 0;
	while (p + 4 <= bytes.length && view.getUint32(p, true) === 0x04034b50) {
		const nameLen = view.getUint16(p + 26, true);
		const extraLen = view.getUint16(p + 28, true);
		const size = view.getUint32(p + 18, true);
		const name = new TextDecoder().decode(bytes.subarray(p + 30, p + 30 + nameLen));
		names.push(name);
		p += 30 + nameLen + extraLen + size;
	}
	return names;
}

describe('zipStore via buildDocx', () => {
	const bytes = buildDocx('<h1>Judul</h1><p>Halo <b>dunia</b></p>');

	it('starts with the ZIP local header magic', () => {
		expect(Array.from(bytes.subarray(0, 4))).toEqual([0x50, 0x4b, 0x03, 0x04]);
	});

	it('contains the OOXML package parts', () => {
		const names = listZipNames(bytes);
		expect(names).toContain('[Content_Types].xml');
		expect(names).toContain('_rels/.rels');
		expect(names).toContain('word/document.xml');
		expect(names).toContain('word/styles.xml');
	});

	it('ends with the end-of-central-directory signature', () => {
		const tail = new DataView(bytes.buffer, bytes.byteOffset + bytes.length - 22, 22);
		expect(tail.getUint32(0, true)).toBe(0x06054b50);
	});
});

describe('htmlToWordBody', () => {
	it('maps headings to Word heading styles', () => {
		const xml = htmlToWordBody('<h2>Bab</h2>');
		expect(xml).toContain('w:pStyle w:val="Heading2"');
		expect(xml).toContain('<w:t xml:space="preserve">Bab</w:t>');
	});

	it('marks bold runs and escapes text', () => {
		const xml = htmlToWordBody('<p>a <b>tebal</b> &amp; aman</p>');
		expect(xml).toContain('<w:b/>');
		expect(xml).toContain('&amp; aman');
	});

	it('serialises tables into w:tbl', () => {
		const xml = htmlToWordBody('<table><tr><td>1</td><td>2</td></tr></table>');
		expect(xml).toContain('<w:tbl>');
		expect(xml).toContain('<w:tc>');
	});

	it('always ends with a section properties block', () => {
		expect(htmlToWordBody('')).toContain('<w:sectPr>');
	});
});

describe('buildOdt', () => {
	it('starts with the uncompressed mimetype entry', () => {
		const names = listZipNames(buildOdt('<p>Hi</p>'));
		expect(names[0]).toBe('mimetype');
		expect(names).toContain('content.xml');
		expect(names).toContain('META-INF/manifest.xml');
	});
});

describe('buildRtf', () => {
	it('escapes braces and emits Unicode escapes', () => {
		const rtf = buildRtf('<p>Halo {x} — ✓</p>');
		expect(rtf.startsWith('{\\rtf1')).toBe(true);
		expect(rtf).toContain('\\{x\\}');
		expect(rtf).toMatch(/\\u\d+\?/);
	});
});

describe('buildLatex', () => {
	it('wraps the body in a document environment', () => {
		const tex = buildLatex('<h1>Bab</h1><p>Isi 100%</p>', 'Laporan');
		expect(tex).toContain('\\documentclass');
		expect(tex).toContain('\\section{Bab}');
		expect(tex).toContain('100\\%');
		expect(tex).toContain('\\title{Laporan}');
	});
});

describe('templates', () => {
	it('exposes several start templates', () => {
		expect(TEMPLATES.length).toBeGreaterThanOrEqual(4);
		expect(TEMPLATES.map((t) => t.key)).toContain('blank');
	});

	it('falls back to the first template for an unknown key', () => {
		expect(templateHtml('nope')).toBe(TEMPLATES[0].html);
	});
});
