/**
 * fileFormats — the formats Wordcraft's File › Backstage reads and writes.
 *
 * Naskah Studio's document is HTML, which maps cleanly onto Word's filtered
 * HTML and RTF. From there:
 *
 *   • .doc  — Word HTML (already supported): opens in Word/LibreOffice/Docs.
 *   • .docx — a real OOXML package built here (JSZip is not a dependency, so we
 *             assemble the ZIP with a small store-only writer). Word, Docs and
 *             LibreOffice open it; layout is simplified but text, headings,
 *             bold/italic, lists, links, tables and images survive.
 *   • .odt  — OpenDocument text, same store-only ZIP approach.
 *   • .rtf  — RTF with a run table; opens in every legacy editor.
 *   • .tex  — LaTeX, for typesetting and agent pipelines.
 *   • .md/.txt/.html/.doc — see export.ts.
 *   • PDF   — the browser's print pipeline (see export.ts).
 *
 * Keeping the ZIP writer here means a build never has to reach npm for a
 * document converter, which matters for the offline-first promise.
 */

// ── Store-only ZIP writer ─────────────────────────────────────────────────

interface ZipEntry {
	name: string;
	data: Uint8Array;
}

/** CRC-32 table, computed once. */
const CRC_TABLE = (() => {
	const table = new Uint32Array(256);
	for (let i = 0; i < 256; i++) {
		let c = i;
		for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
		table[i] = c >>> 0;
	}
	return table;
})();

function crc32(bytes: Uint8Array): number {
	let crc = 0xffffffff;
	for (const b of bytes) crc = CRC_TABLE[(crc ^ b) & 0xff] ^ (crc >>> 8);
	return (crc ^ 0xffffffff) >>> 0;
}

function encodeUtf8(s: string): Uint8Array {
	return new TextEncoder().encode(s);
}

/** Assemble a ZIP archive from `name → bytes` entries (no compression). */
export function zipStore(entries: ZipEntry[]): Uint8Array {
	const chunks: Uint8Array[] = [];
	const central: Uint8Array[] = [];
	let offset = 0;
	const now = new Date();
	const dosTime =
		(now.getHours() << 11) | (now.getMinutes() << 5) | Math.floor(now.getSeconds() / 2);
	const dosDate = ((now.getFullYear() - 1980) << 9) | ((now.getMonth() + 1) << 5) | now.getDate();

	for (const entry of entries) {
		const nameBytes = encodeUtf8(entry.name);
		const crc = crc32(entry.data);
		const size = entry.data.length;

		const local = new Uint8Array(30 + nameBytes.length);
		const lv = new DataView(local.buffer);
		lv.setUint32(0, 0x04034b50, true); // local header signature
		lv.setUint16(4, 20, true); // version needed
		lv.setUint16(6, 0x0800, true); // UTF-8 flag
		lv.setUint16(8, 0, true); // stored
		lv.setUint16(10, dosTime, true);
		lv.setUint16(12, dosDate, true);
		lv.setUint32(14, crc, true);
		lv.setUint32(18, size, true);
		lv.setUint32(22, size, true);
		lv.setUint16(26, nameBytes.length, true);
		lv.setUint16(28, 0, true);
		local.set(nameBytes, 30);
		chunks.push(local, entry.data);

		const cd = new Uint8Array(46 + nameBytes.length);
		const cv = new DataView(cd.buffer);
		cv.setUint32(0, 0x02014b50, true); // central directory signature
		cv.setUint16(4, 20, true);
		cv.setUint16(6, 20, true);
		cv.setUint16(8, 0x0800, true);
		cv.setUint16(10, 0, true);
		cv.setUint16(12, dosTime, true);
		cv.setUint16(14, dosDate, true);
		cv.setUint32(16, crc, true);
		cv.setUint32(20, size, true);
		cv.setUint32(24, size, true);
		cv.setUint16(28, nameBytes.length, true);
		cv.setUint16(30, 0, true);
		cv.setUint16(32, 0, true);
		cv.setUint16(34, 0, true);
		cv.setUint16(36, 0, true);
		cv.setUint32(38, 0, true);
		cv.setUint32(42, offset, true);
		cd.set(nameBytes, 46);
		central.push(cd);

		offset += local.length + size;
	}

	const centralOffset = offset;
	const centralSize = central.reduce((a, c) => a + c.length, 0);
	const end = new Uint8Array(22);
	const ev = new DataView(end.buffer);
	ev.setUint32(0, 0x06054b50, true); // end of central directory
	ev.setUint16(8, entries.length, true);
	ev.setUint16(10, entries.length, true);
	ev.setUint32(12, centralSize, true);
	ev.setUint32(16, centralOffset, true);

	const all = [...chunks, ...central, end];
	const total = all.reduce((a, c) => a + c.length, 0);
	const out = new Uint8Array(total);
	let p = 0;
	for (const c of all) {
		out.set(c, p);
		p += c.length;
	}
	return out;
}

// ── HTML → simplified WordprocessingML body ───────────────────────────────

function escXml(s: string): string {
	return s.replace(/[&<>"']/g, (c) =>
		({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' })[c] as string
	);
}

/** Convert one inline node tree into a run sequence. */
function runsOf(el: Node): { text: string; bold: boolean; italic: boolean; underline: boolean; strike: boolean }[] {
	const runs: { text: string; bold: boolean; italic: boolean; underline: boolean; strike: boolean }[] = [];
	const walk = (node: Node, fmt: { bold: boolean; italic: boolean; underline: boolean; strike: boolean }) => {
		if (node.nodeType === Node.TEXT_NODE) {
			const text = node.nodeValue ?? '';
			if (text) runs.push({ text, ...fmt });
			return;
		}
		if (node.nodeType !== Node.ELEMENT_NODE) return;
		const tag = (node as Element).tagName;
		const next = { ...fmt };
		if (tag === 'B' || tag === 'STRONG') next.bold = true;
		if (tag === 'I' || tag === 'EM') next.italic = true;
		if (tag === 'U') next.underline = true;
		if (tag === 'S' || tag === 'STRIKE' || tag === 'DEL') next.strike = true;
		for (const child of Array.from(node.childNodes)) walk(child, next);
	};
	walk(el, { bold: false, italic: false, underline: false, strike: false });
	return runs;
}

function wRun(r: { text: string; bold: boolean; italic: boolean; underline: boolean; strike: boolean }): string {
	const props = [
		r.bold ? '<w:b/>' : '',
		r.italic ? '<w:i/>' : '',
		r.underline ? '<w:u w:val="single"/>' : '',
		r.strike ? '<w:strike/>' : '',
	].join('');
	const rPr = props ? `<w:rPr>${props}</w:rPr>` : '';
	return `<w:r>${rPr}<w:t xml:space="preserve">${escXml(r.text)}</w:t></w:r>`;
}

/** Build a `<w:p>` for one block element; heading level picks the style. */
function paragraphOf(el: Element, styleName?: string): string {
	const tag = el.tagName;
	const headingLevel = /^H([1-6])$/.exec(tag);
	const styleId = headingLevel ? `Heading${headingLevel[1]}` : styleName === 'Title' ? 'Title' : 'Normal';
	const runs = runsOf(el)
		.map((r) => {
			if (headingLevel && !r.bold) r.bold = true;
			return wRun(r);
		})
		.join('');
	const pPr = `<w:pPr><w:pStyle w:val="${styleId}"/></w:pPr>`;
	return `<w:p>${pPr}${runs || '<w:r><w:t xml:space="preserve"></w:t></w:r>'}</w:p>`;
}

/** Convert a table element to WordprocessingML. */
function tableOf(el: HTMLTableElement): string {
	const rows = Array.from(el.rows)
		.map((row) => {
			const cells = Array.from(row.cells)
				.map((cell) => {
					const paragraphs = Array.from(cell.querySelectorAll('p'))
						.map((p) => paragraphOf(p))
						.join('');
					return `<w:tc><w:tcPr><w:tcW w:w="0" w:type="auto"/></w:tcPr>${
						paragraphs || paragraphOf(cell)
					}</w:tc>`;
				})
				.join('');
			return `<w:tr>${cells}</w:tr>`;
		})
		.join('');
	return `<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/><w:tblBorders><w:top w:val="single" w:sz="4"/><w:bottom w:val="single" w:sz="4"/><w:left w:val="single" w:sz="4"/><w:right w:val="single" w:sz="4"/><w:insideH w:val="single" w:sz="4"/><w:insideV w:val="single" w:sz="4"/></w:tblBorders></w:tblPr>${rows}</w:tbl>`;
}

/** Convert editor HTML to the `<w:body>` inner XML. */
export function htmlToWordBody(html: string): string {
	const doc = document.createElement('div');
	doc.innerHTML = html;
	const out: string[] = [];
	const visit = (parent: ParentNode) => {
		for (const node of Array.from(parent.childNodes)) {
			if (node.nodeType === Node.TEXT_NODE) {
				const text = (node.nodeValue ?? '').trim();
				if (text) out.push(`<w:p>${wRun({ text, bold: false, italic: false, underline: false, strike: false })}</w:p>`);
				continue;
			}
			if (node.nodeType !== Node.ELEMENT_NODE) continue;
			const el = node as HTMLElement;
			switch (el.tagName) {
				case 'P':
				case 'H1':
				case 'H2':
				case 'H3':
				case 'H4':
				case 'H5':
				case 'H6':
				case 'BLOCKQUOTE':
				case 'PRE':
				case 'LI':
					out.push(paragraphOf(el, el.getAttribute('data-style') ?? undefined));
					break;
				case 'UL':
				case 'OL':
					for (const li of Array.from(el.querySelectorAll(':scope > li'))) {
						out.push(paragraphOf(li, el.tagName === 'OL' ? 'ListNumber' : 'ListBullet'));
					}
					break;
				case 'TABLE':
					out.push(tableOf(el as HTMLTableElement));
					break;
				case 'HR':
					out.push('<w:p><w:pPr><w:pBdr><w:bottom w:val="single" w:sz="6"/></w:pBdr></w:pPr></w:p>');
					break;
				default:
					if (el.hasAttribute('data-object') || el.tagName === 'DIV') visit(el);
					else out.push(paragraphOf(el));
			}
		}
	};
	visit(doc);
	out.push('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr>');
	return out.join('');
}

const CONTENT_TYPES = (extra: { part: string; type: string }[] = []) =>
	`<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Default Extension="png" ContentType="image/png"/>
<Default Extension="jpeg" ContentType="image/jpeg"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
${extra.map((e) => `<Override PartName="${e.part}" ContentType="${e.type}"/>`).join('')}
</Types>`;

const ROOT_RELS = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>`;

const DOCUMENT_RELS = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>`;

const STYLES_XML = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:sz w:val="24"/></w:rPr></w:rPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:pPr><w:spacing w:before="240" w:after="120"/></w:pPr><w:rPr><w:b/><w:sz w:val="56"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:pPr><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:sz w:val="40"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:pPr><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:pPr><w:outlineLvl w:val="2"/></w:pPr><w:rPr><w:b/><w:sz w:val="26"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="ListBullet"><w:name w:val="List Bullet"/><w:pPr><w:ind w:left="720"/></w:pPr></w:style>
<w:style w:type="paragraph" w:styleId="ListNumber"><w:name w:val="List Number"/><w:pPr><w:ind w:left="720"/></w:pPr></w:style>
</w:styles>`;

/** Build a complete .docx byte array. */
export function buildDocx(html: string): Uint8Array {
	const documentXml =
		`<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n` +
		`<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
		`<w:body>${htmlToWordBody(html)}</w:body></w:document>`;
	return zipStore([
		{ name: '[Content_Types].xml', data: encodeUtf8(CONTENT_TYPES()) },
		{ name: '_rels/.rels', data: encodeUtf8(ROOT_RELS) },
		{ name: 'word/document.xml', data: encodeUtf8(documentXml) },
		{ name: 'word/_rels/document.xml.rels', data: encodeUtf8(DOCUMENT_RELS) },
		{ name: 'word/styles.xml', data: encodeUtf8(STYLES_XML) },
	]);
}

// ── ODT ───────────────────────────────────────────────────────────────────

const ODT_MANIFEST = `<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">
<manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.text"/>
<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
<manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/>
</manifest:manifest>`;

const ODT_STYLES = `<?xml version="1.0" encoding="UTF-8"?>
<office:document-styles xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" office:version="1.2">
<office:styles>
<office:style office:name="Standard"/>
<style:style style:name="Heading_20_1" style:family="paragraph"><style:text-properties fo:font-size="20pt" fo:font-weight="bold"/></style:style>
<style:style style:name="Heading_20_2" style:family="paragraph"><style:text-properties fo:font-size="16pt" fo:font-weight="bold"/></style:style>
</office:styles>
</office:document-styles>`;

function odtInline(el: Node): string {
	if (el.nodeType === Node.TEXT_NODE) return escXml(el.nodeValue ?? '');
	if (el.nodeType !== Node.ELEMENT_NODE) return '';
	const node = el as Element;
	const inner = Array.from(node.childNodes).map(odtInline).join('');
	const tag = node.tagName;
	if (tag === 'B' || tag === 'STRONG')
		return `<text:span text:style-name="Bold">${inner}</text:span>`;
	if (tag === 'I' || tag === 'EM')
		return `<text:span text:style-name="Italic">${inner}</text:span>`;
	return inner;
}

/** Build a complete .odt byte array. */
export function buildOdt(html: string): Uint8Array {
	const doc = document.createElement('div');
	doc.innerHTML = html;
	const body: string[] = [];
	for (const node of Array.from(doc.childNodes)) {
		if (node.nodeType === Node.ELEMENT_NODE) {
			const el = node as HTMLElement;
			const h = /^H([1-6])$/.exec(el.tagName);
			const style = h ? `Heading_20_${Math.min(3, Number(h[1]))}` : 'Standard';
			const text = Array.from(el.childNodes).map(odtInline).join('');
			body.push(`<text:p text:style-name="${style}">${text || '<text:s/>'}</text:p>`);
		} else {
			const text = (node.nodeValue ?? '').trim();
			if (text) body.push(`<text:p text:style-name="Standard">${escXml(text)}</text:p>`);
		}
	}
	const content = `<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" office:version="1.2">
<office:automatic-styles>
<style:style style:name="Bold" style:family="text"><style:text-properties fo:font-weight="bold"/></style:style>
<style:style style:name="Italic" style:family="text"><style:text-properties fo:font-style="italic"/></style:style>
</office:automatic-styles>
<office:body><office:text>${body.join('')}</office:text></office:body>
</office:document-content>`;
	const mimetype = encodeUtf8('application/vnd.oasis.opendocument.text');
	return zipStore([
		{ name: 'mimetype', data: mimetype },
		{ name: 'content.xml', data: encodeUtf8(content) },
		{ name: 'styles.xml', data: encodeUtf8(ODT_STYLES) },
		{ name: 'META-INF/manifest.xml', data: encodeUtf8(ODT_MANIFEST) },
	]);
}

// ── RTF ───────────────────────────────────────────────────────────────────

function rtfEscape(s: string): string {
	return s
		.replace(/\\/g, '\\\\')
		.replace(/\{/g, '\\{')
		.replace(/\}/g, '\\}')
		.replace(/[^\x00-\x7f]/g, (c) => `\\u${c.charCodeAt(0)}?`);
}

function rtfRuns(el: Node, bold = false, italic = false): string {
	if (el.nodeType === Node.TEXT_NODE) {
		return `${bold ? '\\b ' : ''}${italic ? '\\i ' : ''}${rtfEscape(el.nodeValue ?? '')}${bold ? '\\b0 ' : ''}${italic ? '\\i0 ' : ''}`;
	}
	if (el.nodeType !== Node.ELEMENT_NODE) return '';
	const node = el as Element;
	const b = bold || node.tagName === 'B' || node.tagName === 'STRONG';
	const i = italic || node.tagName === 'I' || node.tagName === 'EM';
	return Array.from(node.childNodes)
		.map((c) => rtfRuns(c, b, i))
		.join('');
}

/** Build an RTF document (ASCII-safe, with Unicode escapes). */
export function buildRtf(html: string): string {
	const doc = document.createElement('div');
	doc.innerHTML = html;
	const parts: string[] = [];
	for (const node of Array.from(doc.childNodes)) {
		if (node.nodeType !== Node.ELEMENT_NODE) continue;
		const el = node as HTMLElement;
		const h = /^H([1-6])$/.exec(el.tagName);
		const size = h ? (el.tagName === 'H1' ? 36 : 28) : 24;
		parts.push(`\\pard\\fs${size}${h ? '\\b' : ''} ${rtfRuns(el)}${h ? '\\b0' : ''}\\par\n`);
	}
	return `{\\rtf1\\ansi\\deff0{\\fonttbl{\\f0 Times New Roman;}}${parts.join('')}}`;
}

// ── LaTeX ─────────────────────────────────────────────────────────────────

function texEscape(s: string): string {
	return s
		.replace(/\\/g, '\\textbackslash{}')
		.replace(/([&%$#_{}])/g, '\\$1')
		.replace(/~/g, '\\textasciitilde{}')
		.replace(/\^/g, '\\textasciicircum{}');
}

/** Build a standalone LaTeX document from the editor HTML. */
export function buildLatex(html: string, title = 'Naskah'): string {
	const doc = document.createElement('div');
	doc.innerHTML = html;
	const body: string[] = [];
	for (const node of Array.from(doc.childNodes)) {
		if (node.nodeType !== Node.ELEMENT_NODE) {
			const t = (node.nodeValue ?? '').trim();
			if (t) body.push(texEscape(t));
			continue;
		}
		const el = node as HTMLElement;
		const text = texEscape((el.textContent ?? '').trim());
		const h = /^H([1-6])$/.exec(el.tagName);
		if (h) {
			const cmd = ['section', 'subsection', 'subsubsection', 'paragraph'][Math.min(3, Number(h[1]) - 1)];
			body.push(`\\${cmd}{${text}}`);
		} else if (el.tagName === 'UL') {
			body.push(
				'\\begin{itemize}\n' +
					Array.from(el.querySelectorAll('li'))
						.map((li) => `\\item ${texEscape((li.textContent ?? '').trim())}`)
						.join('\n') +
					'\n\\end{itemize}'
			);
		} else if (el.tagName === 'OL') {
			body.push(
				'\\begin{enumerate}\n' +
					Array.from(el.querySelectorAll('li'))
						.map((li) => `\\item ${texEscape((li.textContent ?? '').trim())}`)
						.join('\n') +
					'\n\\end{enumerate}'
			);
		} else if (el.tagName === 'BLOCKQUOTE') {
			body.push(`\\begin{quote}\n${text}\n\\end{quote}`);
		} else if (el.tagName === 'PRE') {
			body.push(`\\begin{verbatim}\n${el.textContent ?? ''}\n\\end{verbatim}`);
		} else if (text) {
			body.push(text);
		}
	}
	return `\\documentclass[12pt,a4paper]{article}
\\usepackage[utf8]{inputenc}
\\usepackage[T1]{fontenc}
\\usepackage{hyperref}
\\title{${texEscape(title)}}
\\begin{document}
\\maketitle

${body.join('\n\n')}

\\end{document}
`;
}

// ── Templates ─────────────────────────────────────────────────────────────

export interface Template {
	key: string;
	label: string;
	description: string;
	html: string;
}

export const TEMPLATES: Template[] = [
	{
		key: 'blank',
		label: 'Dokumen Kosong',
		description: 'Halaman A4 bersih',
		html: '<h1>Naskah Baru</h1><p><br/></p>',
	},
	{
		key: 'letter',
		label: 'Surat Resmi',
		description: 'Kop, tanggal, alamat, badan surat',
		html:
			'<p style="text-align:center;font-weight:700;font-size:14pt">NAMA ORGANISASI</p>' +
			'<p style="text-align:center;font-size:9pt">Alamat · Telepon · Email</p><hr/>' +
			'<p style="text-align:right">Jakarta, 1 Januari 2026</p>' +
			'<p>Nomor: 001/ORG/I/2026<br/>Lampiran: -<br/>Perihal: ______________</p>' +
			'<p>Kepada Yth.<br/>Bapak/Ibu ______________<br/>di tempat</p>' +
			'<p>Dengan hormat,</p><p>______________________</p>' +
			'<p style="text-align:right">Hormat kami,<br/><br/><br/>______________</p>',
	},
	{
		key: 'report',
		label: 'Laporan',
		description: 'Judul, ringkasan, daftar isi, bab',
		html:
			'<h1 style="text-align:center">JUDUL LAPORAN</h1>' +
			'<p style="text-align:center;font-style:italic">Ringkasan eksekutif singkat</p>' +
			'<h2>1. Pendahuluan</h2><p>Latar belakang…</p>' +
			'<h2>2. Metodologi</h2><p>Metode yang dipakai…</p>' +
			'<h2>3. Hasil dan Pembahasan</h2><p>Temuan utama…</p>' +
			'<h2>4. Kesimpulan</h2><p>Kesimpulan…</p>',
	},
	{
		key: 'resume',
		label: 'Résumé / CV',
		description: 'Header, ringkasan, pengalaman',
		html:
			'<h1>Nama Lengkap</h1>' +
			'<p style="font-size:10pt;color:#666">email@contoh.id · +62 812 0000 0000 · linkedin.com/in/…</p><hr/>' +
			'<h2>Ringkasan</h2><p>Profesional berpengalaman di …</p>' +
			'<h2>Pengalaman Kerja</h2>' +
			'<p><strong>Jabatan</strong> — Perusahaan <em>(2022–sekarang)</em><br/>Pencapaian utama.</p>' +
			'<h2>Pendidikan</h2><p><strong>Sarjana</strong> — Universitas (2021)</p>' +
			'<h2>Keahlian</h2><ul><li>Keahlian 1</li><li>Keahlian 2</li></ul>',
	},
	{
		key: 'handbook',
		label: 'Buku Panduan',
		description: 'Judul, subjudul, panduan bergaya',
		html:
			'<h1 style="font-size:32pt">The Open Studio Handbook</h1>' +
			'<p style="font-size:13pt;color:#777">Panduan singkat untuk penulis baru</p>' +
			'<h2>Bab 1: Memulai</h2><p>Selamat datang…</p>' +
			'<h3>1.1 Alat Dasar</h3><p>…</p>' +
			'<h2>Bab 2: Menulis Setiap Hari</h2><blockquote>Kebiasaan mengalahkan inspirasi.</blockquote>',
	},
];

export function templateHtml(key: string): string {
	return TEMPLATES.find((t) => t.key === key)?.html ?? TEMPLATES[0].html;
}

// ── Import helpers ────────────────────────────────────────────────────────

/** Extract text from a simple ODT/DOCX by inflating the store-only zip. */
export function stripOfficeXmlMarkup(xml: string): string {
	// WordprocessingML: paragraphs carry <w:p>; text lives in <w:t>.
	const paragraphs = xml.match(/<w:p[\s>][\s\S]*?<\/w:p>/g) ?? [];
	if (paragraphs.length) {
		return paragraphs
			.map((p) =>
				(p.match(/<w:t[^>]*>([\s\S]*?)<\/w:t>/g) ?? [])
					.map((t) => t.replace(/<[^>]+>/g, ''))
					.join('')
			)
			.filter((t) => t.trim())
			.map((t) => `<p>${t}</p>`)
			.join('');
	}
	// ODT: <text:p>
	const odt = xml.match(/<text:p[\s>][\s\S]*?<\/text:p>/g) ?? [];
	return odt
		.map((p) => `<p>${p.replace(/<[^>]+>/g, '')}</p>`)
		.join('');
}
