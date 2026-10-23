/**
 * pageSetup — the section-level document properties Word's Layout tab edits:
 * paper size, orientation, margins, gutter, columns, line numbering,
 * vertical alignment, page colour, page borders and watermarks.
 *
 * These live on a small serialisable model (`SectionSetup`) rather than in the
 * document body, because they describe the page, not the text. NaskahCanvas
 * and the export pipeline both read the same model, so what is printed is what
 * was configured.
 */

import { pageLabel } from './dates';
import type { PageNumberFormat } from './dates';

export type PaperName = 'A4' | 'A5' | 'Letter' | 'Legal' | 'B5';
export type Orientation = 'portrait' | 'landscape';

/** Paper sizes in px at 96 dpi (portrait). */
export const PAPER_SIZES: Record<PaperName, { w: number; h: number; label: string }> = {
	A4: { w: 794, h: 1123, label: '21 × 29,7 cm' },
	A5: { w: 559, h: 794, label: '14,8 × 21 cm' },
	Letter: { w: 816, h: 1056, label: '8,5 × 11 in' },
	Legal: { w: 816, h: 1344, label: '8,5 × 14 in' },
	B5: { w: 709, h: 1002, label: '17,6 × 25 cm' },
};

/** Named Word margin presets (px). */
export const MARGIN_PRESETS: Record<string, { top: number; right: number; bottom: number; left: number }> = {
	Normal: { top: 96, right: 96, bottom: 96, left: 96 },
	Sempit: { top: 48, right: 48, bottom: 48, left: 48 },
	Lebar: { top: 96, right: 144, bottom: 96, left: 144 },
	Cermin: { top: 96, right: 96, bottom: 96, left: 144 },
};

export interface SectionSetup {
	paper: PaperName;
	orientation: Orientation;
	margins: { top: number; right: number; bottom: number; left: number };
	gutter: number;
	columns: number;
	/** Paragraph spacing preset applied to the body text. */
	paragraphSpacing: 'none' | 'compact' | 'normal' | 'loose';
	verticalAlign: 'top' | 'center' | 'bottom';
	lineNumbers: boolean;
	pageColor: string;
	pageBorder: { on: boolean; width: number; color: string; style: 'solid' | 'double' | 'dashed' };
	watermark: { text: string; opacity: number; rotate: number; color: string } | null;
	header: string;
	footer: string;
	headerFromTop: number;
	footerFromBottom: number;
	differentFirstPage: boolean;
	showPageNumbers: boolean;
	pageNumberFormat: PageNumberFormat;
	hyphenation: boolean;
	darkPaper: boolean;
}

export function defaultSection(): SectionSetup {
	return {
		paper: 'A4',
		orientation: 'portrait',
		margins: { ...MARGIN_PRESETS.Normal },
		gutter: 0,
		columns: 1,
		paragraphSpacing: 'normal',
		verticalAlign: 'top',
		lineNumbers: false,
		pageColor: 'transparent',
		pageBorder: { on: false, width: 1, color: '#999999', style: 'solid' },
		watermark: null,
		header: '',
		footer: '',
		headerFromTop: 24,
		footerFromBottom: 24,
		differentFirstPage: false,
		showPageNumbers: false,
		pageNumberFormat: 'decimal',
		hyphenation: false,
		darkPaper: false,
	};
}

/** Page dimensions after applying the orientation; width is what A4-zoom uses. */
export function pageDimensions(s: SectionSetup): { width: number; height: number } {
	const p = PAPER_SIZES[s.paper] ?? PAPER_SIZES.A4;
	return s.orientation === 'landscape' ? { width: p.h, height: p.w } : { width: p.w, height: p.h };
}

/** Line-height multiplier for the paragraph spacing preset. */
export function spacingMultiplier(preset: SectionSetup['paragraphSpacing']): string {
	switch (preset) {
		case 'none':
			return '1.15';
		case 'compact':
			return '1.25';
		case 'loose':
			return '2';
		default:
			return '1.5';
	}
}

/** The CSS that makes a paper element look like the configured section. */
export function paperStyle(s: SectionSetup): string {
	const parts: string[] = [];
	parts.push(`padding:${s.margins.top}px ${s.margins.right}px ${s.margins.bottom}px ${s.margins.left}px`);
	if (s.pageColor !== 'transparent') parts.push(`background:${s.pageColor}`);
	if (s.columns > 1) {
		parts.push(`column-count:${s.columns}`);
		parts.push('column-gap:2.4em');
		parts.push('column-rule:1px solid rgba(128,128,128,0.3)');
	}
	if (s.pageBorder.on) {
		const style = s.pageBorder.style === 'double' ? 'double' : s.pageBorder.style;
		parts.push(`outline:${s.pageBorder.width * 2}px ${style} ${s.pageBorder.color}`);
		parts.push('outline-offset:-8px');
	}
	if (s.verticalAlign !== 'top') {
		parts.push('display:flex');
		parts.push('flex-direction:column');
		parts.push(`justify-content:${s.verticalAlign === 'center' ? 'center' : 'flex-end'}`);
	}
	if (s.lineNumbers) {
		parts.push('counter-reset:naskah-line');
	}
	if (s.hyphenation) parts.push('hyphens:auto');
	return parts.join(';');
}

/** Build the watermark overlay markup (non-selectable, behind the text). */
export function watermarkMarkup(s: SectionSetup): string {
	if (!s.watermark || !s.watermark.text.trim()) return '';
	const w = s.watermark;
	return `<div class="naskah-watermark" contenteditable="false" aria-hidden="true" style="
    position:absolute;inset:0;display:flex;align-items:center;justify-content:center;pointer-events:none;
    font-size:96px;font-weight:800;letter-spacing:8px;color:${w.color};opacity:${w.opacity};
    transform:rotate(${w.rotate}deg);z-index:0;user-select:none;white-space:nowrap">${escapeHtml(w.text)}</div>`;
}

/** Header line with optional page-number field placeholder. */
export function headerMarkup(s: SectionSetup, page = 1): string {
	if (!s.header.trim() && !s.showPageNumbers) return '';
	const pageField = s.showPageNumbers
		? `<span class="naskah-page-field" data-page-format="${s.pageNumberFormat}">${pageLabel(page, s.pageNumberFormat)}</span>`
		: '';
	const parts = [escapeHtml(s.header.replace('{page}', '')).trim(), pageField].filter(Boolean);
	return parts.join('&nbsp;&nbsp;&nbsp;');
}

/** Footer line with optional page-number field. */
export function footerMarkup(s: SectionSetup, page = 1): string {
	if (!s.footer.trim() && !s.showPageNumbers) return '';
	const pageField = s.showPageNumbers
		? `<span class="naskah-page-field" data-page-format="${s.pageNumberFormat}">${pageLabel(page, s.pageNumberFormat)}</span>`
		: '';
	const parts = [escapeHtml(s.footer.replace('{page}', '')).trim(), pageField].filter(Boolean);
	return parts.join('&nbsp;&nbsp;&nbsp;');
}

/** Page-number styles Word offers in Format Page Numbers. */
export const PAGE_NUMBER_FORMATS: { key: PageNumberFormat; label: string }[] = [
	{ key: 'decimal', label: '1, 2, 3, …' },
	{ key: 'roman', label: 'i, ii, iii, …' },
	{ key: 'alpha', label: 'a, b, c, …' },
];

function escapeHtml(s: string): string {
	return s.replace(/[&<>"']/g, (c) =>
		({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string
	);
}

const KEY = 'omnigensi.naskah.section.v1';

export function loadSection(): SectionSetup | null {
	try {
		const raw = localStorage.getItem(KEY);
		if (!raw) return null;
		return { ...defaultSection(), ...(JSON.parse(raw) as SectionSetup) };
	} catch {
		return null;
	}
}

export function saveSection(s: SectionSetup): void {
	try {
		localStorage.setItem(KEY, JSON.stringify(s));
	} catch {
		/* storage blocked */
	}
}
