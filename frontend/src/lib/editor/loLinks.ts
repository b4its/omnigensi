/**
 * loLinks — LibreOffice Writer's Hyperlink dialog model.
 *
 * Writer's link dialog is a four-tab notebook (Internet, Mail, Document,
 * New Document). The Document tab is the interesting one: it can point at a
 * target inside the same manuscript (a bookmark or a heading) with an optional
 * "open in this frame" behaviour, and it can carry a named target that other
 * links may reference later. This module keeps that model and builds the anchor
 * markup the editor stores.
 */

export type LinkKind = 'internet' | 'mail' | 'document' | 'newDocument';

export interface LinkModel {
	kind: LinkKind;
	/** Visible text; empty means the browser shows the target. */
	text: string;
	/** URL / mailto / document anchor. */
	target: string;
	/** Writer's "Name" — lets other links point at this one. */
	name: string;
	/** Open in a new window (Internet links). */
	newWindow: boolean;
	/** Bookmark target inside the same document. */
	bookmark: string;
}

export function emptyLink(): LinkModel {
	return { kind: 'internet', text: '', target: '', name: '', newWindow: true, bookmark: '' };
}

function esc(s: string): string {
	return s.replace(/[&<>"']/g, (c) =>
		({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string
	);
}

/** Normalise the target for the chosen link kind. */
export function resolveTarget(link: LinkModel): string {
	switch (link.kind) {
		case 'mail':
			return link.target.startsWith('mailto:') ? link.target : `mailto:${link.target}`;
		case 'document':
			return `#${link.bookmark || link.target.replace(/^#/, '')}`;
		case 'newDocument':
			return link.target || 'document-baru.docx';
		default:
			return link.target;
	}
}

/** Build the anchor HTML for a link model. */
export function linkMarkup(link: LinkModel): string {
	const href = resolveTarget(link);
	const label = link.text || link.bookmark || link.target;
	const attrs: string[] = [`href="${esc(href)}"`, `data-linkkind="${link.kind}"`];
	if (link.name) attrs.push(`name="${esc(link.name)}"`, `id="${esc(link.name)}"`);
	if (link.newWindow && (link.kind === 'internet' || link.kind === 'newDocument')) {
		attrs.push('target="_blank"', 'rel="noopener"');
	}
	return `<a ${attrs.join(' ')}>${esc(label)}</a>`;
}

/** Validate a link model; returns null when it is ready to insert. */
export function validateLink(link: LinkModel): string | null {
	const target = link.target.trim();
	if (link.kind === 'document' && !link.bookmark && !target.replace(/^#/, '')) {
		return 'Pilih atau isi tujuan dokumen.';
	}
	// A bare "https://" placeholder is not a usable target.
	const placeholder = /^(https?:\/\/|mailto:)?$/i.test(target);
	if (link.kind !== 'document' && (!target || placeholder)) return 'Tujuan tautan kosong.';
	return null;
}
