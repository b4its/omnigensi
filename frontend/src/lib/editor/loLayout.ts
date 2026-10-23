/**
 * loLayout — the page-widget helpers that make the Naskah Studio canvas behave
 * like a LibreOffice Writer page: page-number fields placed anywhere in the
 * text, margin comments with leader lines, and the page-count/total-pages
 * relationship the Writer status bar shows.
 *
 * None of these depend on the ribbon; they are called by the page component and
 * by the review pane.
 */

import { pageLabel } from './dates';
import type { PageNumberFormat } from './dates';

// ── Page-number fields ─────────────────────────────────────────────────────

export interface NumberingContext {
	format: PageNumberFormat;
	start: number;
}

/** A Writer "Page Number" field: a non-editable span the canvas can refresh. */
export function pageFieldMarkup(context: NumberingContext, page = 1): string {
	return `<span data-object="pagefield" data-format="${context.format}" data-value="${page}" contenteditable="false" style="white-space:nowrap">${pageLabel(
		context.start + page - 1,
		context.format
	)}</span>`;
}

/** A "Page Number of Total" field combination. */
export function pageOfTotal(context: NumberingContext, page: number, total: number): string {
	return `${pageFieldMarkup(context, page)} / ${pageLabel(total, context.format)}`;
}

/**
 * Rewrite every page field in the document for the current count. The canvas
 * does not paginate for real; the page count is approximated from content
 * height, which matches what the status bar reports.
 */
export function refreshPageFields(root: HTMLElement, context: NumberingContext, total: number): number {
	let updated = 0;
	root.querySelectorAll<HTMLElement>('[data-object="pagefield"]').forEach((el) => {
		const value = Number(el.getAttribute('data-value') ?? '1');
		el.textContent = pageLabel(context.start + value - 1, context.format);
		updated++;
	});
	void total;
	return updated;
}

// ── Margin comments ────────────────────────────────────────────────────────

export interface MarginNote {
	id: string;
	text: string;
	author: string;
	/** Index of the anchor in document order, used for vertical placement. */
	index: number;
}

/**
 * Read the comment anchors and produce margin notes with the vertical order the
 * canvas needs. Each entry references the anchor so the canvas can draw a leader
 * line to the right y position.
 */
export function collectMarginNotes(root: HTMLElement): MarginNote[] {
	return Array.from(root.querySelectorAll<HTMLElement>('[data-comment]')).map((el, index) => ({
		id: el.getAttribute('data-comment') ?? String(index),
		text: el.getAttribute('data-comment-text') ?? '',
		author: el.getAttribute('data-author') ?? 'Penulis',
		index,
	}));
}

/** Approximate the anchor's vertical offset, in px, inside the paper. */
export function anchorOffset(anchor: HTMLElement): number {
	const rect = anchor.getBoundingClientRect();
	const paper = anchor.closest('.naskah-paper');
	if (!paper) return 0;
	return rect.top - paper.getBoundingClientRect().top;
}

// ── Writer status bar data ─────────────────────────────────────────────────

export interface WriterStatus {
	/** "Halaman 1 dari 7" */
	pages: string;
	/** "Kata 1.234" — thousands-separated, Indonesian. */
	words: string;
	/** Insert/overwrite mode. */
	mode: string;
	/** Active language. */
	language: string;
}

export function writerStatus(page: number, total: number, words: number): WriterStatus {
	return {
		pages: `Halaman ${page} dari ${total}`,
		words: `Kata ${new Intl.NumberFormat('id-ID').format(words)}`,
		mode: 'SELIP',
		language: 'Bahasa Indonesia',
	};
}

// ── Section breaks ─────────────────────────────────────────────────────────

export type BreakKind = 'page' | 'column' | 'section';

/** A Writer break at the caret with the correct semantics for each kind. */
export function breakMarkup(kind: BreakKind): string {
	if (kind === 'column') {
		return '<div class="naskah-columnbreak" contenteditable="false" style="break-after:column"></div>';
	}
	if (kind === 'section') {
		return '<div class="naskah-sectionbreak" contenteditable="false" style="border-top:1px dashed rgba(128,128,128,0.6);margin:6px 0"><span style="font-size:8px;letter-spacing:.1em;color:#888">SECTION BREAK</span></div><p><br/></p>';
	}
	return '<div class="naskah-pagebreak" contenteditable="false"></div><p><br/></p>';
}
