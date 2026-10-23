/**
 * Export and import for the Naskah Studio editor.
 *
 * The project ships no document-conversion libraries, so we emit the formats
 * that every word processor opens without a plugin. The heavy formats are built
 * in `fileFormats.ts` (native ZIP writer for .docx/.odt) and re-exported here so
 * callers have one import site:
 *
 *   • `.docx`  — real OOXML package (text, headings, bold/italic, lists, tables).
 *   • `.doc`   — HTML file wrapped in the MS Office namespace.
 *   • `.odt`   — OpenDocument text.
 *   • `.rtf`   — Rich Text Format.
 *   • `.tex`   — LaTeX for typesetting.
 *   • `.html`  — clean, standalone HTML for the web.
 *   • `.md`    — Markdown, for version control and agent pipelines.
 *   • `.txt`   — plain text with no formatting.
 *   • PDF      — via the browser's own print-to-PDF pipeline.
 *
 * Import accepts `.html`, `.md`, `.txt`, `.rtf`, `.docx`/`.odt` (best-effort
 * text extraction) and `.doc` written by us.
 */

import { buildDocx, buildLatex, buildOdt, buildRtf, stripOfficeXmlMarkup } from './fileFormats';
import { plainText } from './text';

export type ExportFormat = 'docx' | 'doc' | 'odt' | 'rtf' | 'tex' | 'html' | 'md' | 'txt';

const OFFICE_HEAD =
	'<html xmlns:o="urn:schemas-microsoft-com:office:office" ' +
	'xmlns:w="urn:schemas-microsoft-com:office:word" ' +
	'xmlns="http://www.w3.org/TR/REC-html40"><head><meta charset="utf-8">' +
	'<title>Naskah</title>' +
	'<!--[if gte mso 9]><xml><w:WordDocument><w:View>Print</w:View>' +
	'<w:Zoom>100</w:Zoom></w:WordDocument></xml><![endif]-->' +
	'<style>' +
	'@page { size: A4; margin: 2.54cm; }' +
	'body { font-family: "Times New Roman", serif; font-size: 12pt; line-height: 1.5; color: #111; }' +
	'h1,h2,h3,h4 { font-family: "Calibri", sans-serif; }' +
	'table { border-collapse: collapse; width: 100%; }' +
	'td,th { border: 1px solid #999; padding: 6px 8px; }' +
	'th { background: #eee; }' +
	'.naskah-pagebreak { page-break-after: always; }' +
	'blockquote { border-left: 3px solid #bbb; margin-left: 0; padding-left: 12px; color: #555; }' +
	'</style></head><body>';

const OFFICE_TAIL = '</body></html>';

/** Strip editor-only artefacts (page-break markers, selection wrappers) that
 *  must not survive into a saved file. */
function cleanHtml(html: string): string {
	return html
		.replace(/<div class="naskah-pagebreak"[^>]*><\/div>/g, '<div style="page-break-after:always"></div>')
		.replace(/\sdata-editor-[a-z-]+="[^"]*"/g, '');
}

/** DOM → Markdown (headings, bold/italic, lists, links, images, tables,
 *  blockquotes, code). Sufficient for round-tripping a written manuscript. */
export function htmlToMarkdown(root: HTMLElement): string {
	const lines: string[] = [];

	function inline(node: Node): string {
		if (node.nodeType === Node.TEXT_NODE) return node.nodeValue ?? '';
		if (node.nodeType !== Node.ELEMENT_NODE) return '';
		const el = node as HTMLElement;
		const children = Array.from(el.childNodes).map(inline).join('');
		switch (el.tagName) {
			case 'STRONG':
			case 'B':
				return `**${children}**`;
			case 'EM':
			case 'I':
				return `*${children}*`;
			case 'DEL':
			case 'S':
			case 'STRIKE':
				return `~~${children}~~`;
			case 'CODE':
				return `\`${children}\``;
			case 'A':
				return `[${children}](${el.getAttribute('href') ?? ''})`;
			case 'IMG':
				return `![${el.getAttribute('alt') ?? ''}](${el.getAttribute('src') ?? ''})`;
			case 'BR':
				return '  \n';
			case 'U':
				return `<u>${children}</u>`;
			case 'SUP':
				return `<sup>${children}</sup>`;
			case 'SUB':
				return `<sub>${children}</sub>`;
			default:
				return children;
		}
	}

	function block(el: HTMLElement) {
		const tag = el.tagName;
		const text = Array.from(el.childNodes).map(inline).join('').trim();
		switch (tag) {
			case 'H1':
				lines.push(`# ${text}`);
				break;
			case 'H2':
				lines.push(`## ${text}`);
				break;
			case 'H3':
				lines.push(`### ${text}`);
				break;
			case 'H4':
				lines.push(`#### ${text}`);
				break;
			case 'BLOCKQUOTE':
				lines.push(`> ${text}`);
				break;
			case "PRE":
				lines.push("```\n" + plainText(el) + "\n```");
				break;
			case 'UL':
			case 'OL': {
				const ordered = tag === 'OL';
				Array.from(el.children).forEach((li, i) => {
					const c = Array.from(li.childNodes).map(inline).join('').trim();
					lines.push(`${ordered ? `${i + 1}.` : '-'} ${c}`);
				});
				break;
			}
			case 'TABLE': {
				const rows = Array.from(el.querySelectorAll('tr'));
				rows.forEach((tr, ri) => {
					const cells = Array.from(tr.children).map((c) => inline(c).trim());
					lines.push('| ' + cells.join(' | ') + ' |');
					if (ri === 0) lines.push('| ' + cells.map(() => '---').join(' | ') + ' |');
				});
				break;
			}
			case 'HR':
				lines.push('---');
				break;
			case 'DIV':
			case 'P':
			default: {
				if (el.querySelector('h1,h2,h3,h4,ul,ol,table,blockquote,pre,p')) {
					Array.from(el.childNodes).forEach((child) => {
						if (child.nodeType === Node.ELEMENT_NODE) block(child as HTMLElement);
						else {
							const t = inline(child).trim();
							if (t) lines.push(t);
						}
					});
				} else if (text) {
					lines.push(text);
				}
			}
		}
	}

	Array.from(root.childNodes).forEach((child) => {
		if (child.nodeType === Node.ELEMENT_NODE) block(child as HTMLElement);
		else {
			const t = inline(child).trim();
			if (t) lines.push(t);
		}
	});

	return lines.join('\n\n').replace(/\n{3,}/g, '\n\n').trim() + '\n';
}

/** Render HTML for a chosen text-based export format. */
export function serialize(html: string, format: ExportFormat, title = 'Naskah'): string {
	const clean = cleanHtml(html);
	if (format === 'html') {
		return `<!doctype html><html lang="id"><head><meta charset="utf-8"><title>${title}</title>` +
			'<style>body{font-family:Georgia,serif;max-width:800px;margin:2rem auto;padding:0 1rem;line-height:1.6}' +
			'table{border-collapse:collapse;width:100%}td,th{border:1px solid #999;padding:6px 8px}</style>' +
			`</head><body>${clean}</body></html>`;
	}
	if (format === 'doc') {
		return OFFICE_HEAD + clean + OFFICE_TAIL;
	}
	if (format === 'rtf') {
		return buildRtf(clean);
	}
	if (format === 'tex') {
		return buildLatex(clean, title);
	}
	if (format === 'md') {
		const div = document.createElement('div');
		div.innerHTML = clean;
		return htmlToMarkdown(div);
	}
	// txt (docx/odt are binary and handled in downloadDocument)
	const div = document.createElement('div');
	div.innerHTML = clean;
	return plainText(div) + '\n';
}

const MIME: Record<ExportFormat, string> = {
	docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
	doc: 'application/msword',
	odt: 'application/vnd.oasis.opendocument.text',
	rtf: 'application/rtf',
	tex: 'application/x-tex',
	html: 'text/html',
	md: 'text/markdown',
	txt: 'text/plain',
};

/** Serialize to bytes or a string, depending on the format. */
export function serializeToBlob(html: string, format: ExportFormat, title = 'Naskah'): Blob {
	if (format === 'docx') return new Blob([toArrayBuffer(buildDocx(html))], { type: MIME.docx });
	if (format === 'odt') return new Blob([toArrayBuffer(buildOdt(html))], { type: MIME.odt });
	return new Blob([serialize(html, format, title)], { type: `${MIME[format]};charset=utf-8` });
}

/** Copy a Uint8Array into a plain ArrayBuffer Blob can always accept. */
function toArrayBuffer(bytes: Uint8Array): ArrayBuffer {
	const copy = new Uint8Array(bytes.byteLength);
	copy.set(bytes);
	return copy.buffer;
}

/** Trigger a browser download of the serialized document. */
export function downloadDocument(
	html: string,
	format: ExportFormat,
	filename: string,
	title = 'Naskah'
): void {
	const blob = serializeToBlob(html, format, title);
	const name = filename.replace(/\.[^./]+$/, '') || 'naskah';
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = `${name}.${format}`;
	a.rel = 'noopener';
	document.body.appendChild(a);
	a.click();
	document.body.removeChild(a);
	setTimeout(() => URL.revokeObjectURL(url), 2000);
}

/** Open the print dialog (browser → "Save as PDF"). */
export function printDocument(): void {
	window.print();
}

/** Best-effort import of a document into an HTML string. */
export async function readImportedFile(file: File): Promise<string> {
	const name = file.name.toLowerCase();
	if (name.endsWith('.docx') || name.endsWith('.odt')) {
		const text = await file.text();
		return stripOfficeXmlMarkup(text) || text;
	}
	const text = await file.text();
	if (name.endsWith('.rtf')) {
		return rtfToHtml(text);
	}
	if (name.endsWith('.md')) {
		return markdownToHtml(text);
	}
	if (name.endsWith('.html') || name.endsWith('.htm') || name.endsWith('.doc')) {
		const bodyMatch = text.match(/<body[^>]*>([\s\S]*)<\/body>/i);
		return bodyMatch ? bodyMatch[1] : text;
	}
	// .txt and unknown: escape and wrap paragraphs.
	return text
		.split(/\n{2,}/)
		.map((p) => `<p>${escapeHtml(p).replace(/\n/g, '<br/>')}</p>`)
		.join('');
}

/** Very small RTF → HTML converter (paragraphs and runs only). */
function rtfToHtml(rtf: string): string {
	const paragraphs = rtf.split(/\\par[d]?/);
	return paragraphs
		.map((p) => {
			const text = p
				.replace(/\{\\\*[^}]*\}/g, '')
				.replace(/\\'[0-9a-f]{2}/g, '')
				.replace(/\\u(-?\d+)\??/g, (_m, n) => String.fromCharCode(Number(n) < 0 ? Number(n) + 65536 : Number(n)))
				.replace(/\\[a-z]+-?\d* ?/g, '')
				.replace(/[{}]/g, '')
				.trim();
			return text ? `<p>${escapeHtml(text)}</p>` : '';
		})
		.join('');
}

function markdownToHtml(md: string): string {
	const lines = md.split(/\r?\n/);
	const out: string[] = [];
	let inList = false;
	for (const raw of lines) {
		const line = raw.trimEnd();
		const h = line.match(/^(#{1,4})\s+(.*)$/);
		if (h) {
			if (inList) {
				out.push('</ul>');
				inList = false;
			}
			const lvl = h[1].length;
			out.push(`<h${lvl}>${inlineMd(h[2])}</h${lvl}>`);
			continue;
		}
		const li = line.match(/^[-*]\s+(.*)$/);
		if (li) {
			if (!inList) {
				out.push('<ul>');
				inList = true;
			}
			out.push(`<li>${inlineMd(li[1])}</li>`);
			continue;
		}
		if (inList) {
			out.push('</ul>');
			inList = false;
		}
		if (line.trim() === '') continue;
		out.push(`<p>${inlineMd(line)}</p>`);
	}
	if (inList) out.push('</ul>');
	return out.join('\n');
}

function inlineMd(s: string): string {
	return escapeHtml(s)
		.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
		.replace(/\*(.+?)\*/g, '<em>$1</em>')
		.replace(/`(.+?)`/g, '<code>$1</code>')
		.replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
}

function escapeHtml(s: string): string {
	return s.replace(/[&<>"']/g, (c) =>
		({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string
	);
}
