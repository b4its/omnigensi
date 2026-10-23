/**
 * useHeading — build the document outline the Navigation pane and the table of
 * contents both need. Reads headings straight out of the live DOM so it always
 * matches what the writer sees, not a stale cached copy.
 */

export interface Heading {
	level: number;
	text: string;
	id: string;
	el: HTMLElement;
}

const HEADING = 'h1,h2,h3,h4,h5,h6';

/** Every heading in the document, in reading order, with stable ids. */
export function collectHeadings(root: HTMLElement): Heading[] {
	const nodes = Array.from(root.querySelectorAll<HTMLElement>(HEADING));
	return nodes.map((el, i) => {
		const level = Number(el.tagName.slice(1));
		const text = (el.textContent ?? '').trim() || `(tanpa judul ${i + 1})`;
		let id = el.id;
		if (!id) {
			id = `naskah-h-${i}-${slug(text).slice(0, 32) || 'judul'}`;
			el.id = id;
		}
		return { level, text, id, el };
	});
}

/** Slugify heading text for stable anchors. */
export function slug(text: string): string {
	return text
		.toLowerCase()
		.normalize('NFKD')
		.replace(/[\u0300-\u036f]/g, '')
		.replace(/[^a-z0-9]+/g, '-')
		.replace(/^-+|-+$/g, '');
}

/**
 * Render a clickable table-of-contents block from the current headings.
 * Each entry links to the heading's anchor so navigation survives export.
 */
export function renderToc(headings: Heading[], title = 'Daftar Isi'): string {
	if (!headings.length) {
		return `<h2 data-object="toc-heading">${title}</h2><p style="color:#888">[Belum ada judul. Terapkan gaya Heading 1-3 pada bab Anda.]</p><p><br/></p>`;
	}
	const rows = headings
		.filter((h) => h.level <= 3)
		.map((h) => {
			const indent = (h.level - 1) * 1.4;
			const dots = '<span style="flex:1;border-bottom:1px dotted #999;margin:0 6px 4px"></span>';
			return `<div data-toc-entry style="display:flex;align-items:baseline;padding-left:${indent}em;margin:2px 0">
        <a href="#${h.id}" style="color:inherit;text-decoration:none">${escapeHtml(h.text)}</a>${dots}
        <span style="font-size:9pt;color:#888">·</span>
      </div>`;
		})
		.join('');
	return `<div data-object="toc"><h2 data-object="toc-heading">${title}</h2>${rows}</div><p><br/></p>`;
}

function escapeHtml(s: string): string {
	return s.replace(/[&<>"']/g, (c) =>
		({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string
	);
}
