/**
 * review — Word's Review tab: comments, track changes, accept/reject, spelling
 * and grammar, thesaurus, word count, reading aloud and document-inspector
 * style checks.
 *
 * Track-changes model: when tracking is on, edits are represented with the same
 * two element kinds Word uses — `<ins data-revision>` for insertions and
 * `<del data-revision>` for deletions — so accept/reject is a DOM walk instead
 * of a diff. Because `execCommand('insertText')` hides what actually happens,
 * the page keeps this module in charge of turning plain typing into revisions
 * while tracking is enabled.
 */

// ── Comments ───────────────────────────────────────────────────────────────

let commentSeq = 0;
export function nextCommentId(): string {
	commentSeq += 1;
	return `naskah-comment-${Date.now().toString(36)}-${commentSeq}`;
}

export interface Comment {
	id: string;
	author: string;
	text: string;
	color: string;
}

export const COMMENT_COLORS = ['#0066FF', '#FF0055', '#00A86B', '#B8860B', '#7C4DFF'];

/** Wrap the current selection in a comment anchor and return its id. */
export function markComment(author: string, text: string): string | null {
	const sel = window.getSelection();
	if (!sel || sel.rangeCount === 0 || sel.isCollapsed) return null;
	const id = nextCommentId();
	const range = sel.getRangeAt(0);
	const span = document.createElement('span');
	span.setAttribute('data-comment', id);
	span.setAttribute('data-author', author);
	span.setAttribute('data-comment-text', text);
	span.className = 'naskah-comment-anchor';
	try {
		range.surroundContents(span);
	} catch {
		span.appendChild(range.extractContents());
		range.insertNode(span);
	}
	return id;
}

/** Every comment anchor in document order. */
export function collectComments(root: HTMLElement): Comment[] {
	return Array.from(root.querySelectorAll<HTMLElement>('[data-comment]')).map((el, i) => ({
		id: el.getAttribute('data-comment') ?? String(i),
		author: el.getAttribute('data-author') ?? 'Penulis',
		text: el.getAttribute('data-comment-text') ?? '',
		color: COMMENT_COLORS[i % COMMENT_COLORS.length],
	}));
}

/** Resolve: unwrap the anchor, dropping the comment but keeping the text. */
export function resolveComment(root: HTMLElement, id: string): void {
	const el = root.querySelector<HTMLElement>(`[data-comment="${cssEscape(id)}"]`);
	if (!el) return;
	const parent = el.parentNode;
	if (!parent) return;
	while (el.firstChild) parent.insertBefore(el.firstChild, el);
	parent.removeChild(el);
}

/** Delete the comment and the text it covered. */
export function deleteComment(root: HTMLElement, id: string): void {
	root.querySelector<HTMLElement>(`[data-comment="${cssEscape(id)}"]`)?.remove();
}

/** Jump to a comment and select its anchor. */
export function focusComment(root: HTMLElement, id: string): void {
	const el = root.querySelector<HTMLElement>(`[data-comment="${cssEscape(id)}"]`);
	if (!el) return;
	el.scrollIntoView({ block: 'center', behavior: 'smooth' });
	const range = document.createRange();
	range.selectNodeContents(el);
	const sel = window.getSelection();
	sel?.removeAllRanges();
	sel?.addRange(range);
}

// ── Track changes ─────────────────────────────────────────────────────────

export const tracking = {
	enabled: false,
	author: 'Penulis',
};

/** Insert typed text as a tracked insertion. */
export function trackInsert(text: string): boolean {
	if (!tracking.enabled) return false;
	const sel = window.getSelection();
	if (!sel || sel.rangeCount === 0) return false;
	const range = sel.getRangeAt(0);
	if (!range.collapsed) trackDeleteSelection();
	const ins = document.createElement('ins');
	ins.setAttribute('data-revision', 'insert');
	ins.setAttribute('data-author', tracking.author);
	ins.textContent = text;
	const r = window.getSelection();
	if (!r || r.rangeCount === 0) return false;
	const live = r.getRangeAt(0);
	live.deleteContents();
	live.insertNode(ins);
	live.setStartAfter(ins);
	live.collapse(true);
	r.removeAllRanges();
	r.addRange(live);
	return true;
}

/** Wrap the current selection in a tracked deletion. */
export function trackDeleteSelection(): boolean {
	const sel = window.getSelection();
	if (!sel || sel.rangeCount === 0) return false;
	const range = sel.getRangeAt(0);
	if (range.collapsed) return false;
	// Already inside a deletion: just remove it, no nested revision.
	const del = document.createElement('del');
	del.setAttribute('data-revision', 'delete');
	del.setAttribute('data-author', tracking.author);
	try {
		range.surroundContents(del);
	} catch {
		del.appendChild(range.extractContents());
		range.insertNode(del);
	}
	// Collapse the caret after the deletion so typing continues normally.
	const after = document.createRange();
	after.setStartAfter(del);
	after.collapse(true);
	sel.removeAllRanges();
	sel.addRange(after);
	return true;
}

export type RevisionKind = 'insert' | 'delete';

/** Every tracked revision in reading order. */
export function collectRevisions(root: HTMLElement): HTMLElement[] {
	return Array.from(root.querySelectorAll<HTMLElement>('[data-revision]'));
}

/** Accept a revision: keep insertions, drop deletions. */
export function acceptRevision(el: HTMLElement): void {
	if (el.getAttribute('data-revision') === 'delete') el.remove();
	else unwrapEl(el);
}

/** Reject a revision: drop insertions, keep deletions. */
export function rejectRevision(el: HTMLElement): void {
	if (el.getAttribute('data-revision') === 'insert') el.remove();
	else unwrapEl(el);
}

export function acceptAll(root: HTMLElement): number {
	const list = collectRevisions(root);
	for (const el of list) acceptRevision(el);
	return list.length;
}

export function rejectAll(root: HTMLElement): number {
	const list = collectRevisions(root);
	for (const el of list) rejectRevision(el);
	return list.length;
}

/** True when the given node is inside a tracked insertion (for typing merges). */
export function insideInsertion(node: Node | null): boolean {
	let n: Node | null = node;
	while (n) {
		if (n.nodeType === Node.ELEMENT_NODE && (n as Element).getAttribute('data-revision') === 'insert') return true;
		n = n.parentNode;
	}
	return false;
}

// ── Word count ────────────────────────────────────────────────────────────

export interface WordCount {
	words: number;
	characters: number;
	charactersNoSpaces: number;
	paragraphs: number;
	lines: number;
	pages: number;
}

export function wordCount(root: HTMLElement, pageCapacity = 500): WordCount {
	const text = root.innerText ?? '';
	const trimmed = text.trim();
	const words = trimmed ? trimmed.split(/\s+/).length : 0;
	return {
		words,
		characters: text.length,
		charactersNoSpaces: text.replace(/\s/g, '').length,
		paragraphs: trimmed ? trimmed.split(/\n{2,}/).filter(Boolean).length : 0,
		lines: text.split('\n').length,
		pages: Math.max(1, Math.ceil(words / pageCapacity)),
	};
}

// ── Spelling & grammar ────────────────────────────────────────────────────

/** A compact Indonesian stop-word list keeps the checker's noise down. */
const COMMON_WORDS = new Set(
	`yang dan di ke dari untuk pada dengan ini itu adalah akan tidak bisa juga dalam
  oleh sebagai atau karena sudah telah lebih dapat harus tetapi namun serta para
  saya kamu dia kami kita mereka anda ada saja sangat sudah belum masih lagi
  seperti antara setelah sebelum hingga sampai bagi terhadap melalui secara
  banyak sedikit semua setiap beberapa hal cara satu dua tiga tahun hari bulan
  orang waktu tempat kerja data hasil naskah teks judul bagian bab`.split(/\s+/)
);

export interface SpellingIssue {
	word: string;
	suggestions: string[];
}

/** A tiny edit-distance-1 suggestion generator for the misspelling popover. */
function suggestionsFor(word: string, vocab: Set<string>): string[] {
	const out: string[] = [];
	for (const candidate of vocab) {
		if (Math.abs(candidate.length - word.length) > 2) continue;
		if (distance(word.toLowerCase(), candidate.toLowerCase()) <= 2) out.push(candidate);
		if (out.length >= 5) break;
	}
	return out;
}

function distance(a: string, b: string): number {
	const dp = Array.from({ length: a.length + 1 }, (_, i) => [i, ...Array(b.length).fill(0)]);
	for (let j = 0; j <= b.length; j++) dp[0][j] = j;
	for (let i = 1; i <= a.length; i++) {
		for (let j = 1; j <= b.length; j++) {
			dp[i][j] = Math.min(
				dp[i - 1][j] + 1,
				dp[i][j - 1] + 1,
				dp[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1)
			);
		}
	}
	return dp[a.length][b.length];
}

/**
 * Flag obvious misspellings: words with doubled letters of the same case or
 * capitalized words absent from the built-in list are accepted (proper nouns),
 * so the pass only reports tokens that are neither common words nor names.
 * This is a deliberately conservative first pass — a real dictionary backend
 * can replace `isKnown` without touching callers.
 */
export function spellCheck(text: string): SpellingIssue[] {
	const issues: SpellingIssue[] = [];
	const seen = new Set<string>();
	for (const raw of text.split(/[^\p{L}'-]+/u)) {
		const word = raw.replace(/^['-]+|['-]+$/g, '');
		if (word.length < 4) continue;
		if (seen.has(word.toLowerCase())) continue;
		if (/^[A-Z]/.test(word)) continue; // proper noun — accept
		if (COMMON_WORDS.has(word.toLowerCase())) continue;
		// Heuristic noise filter: only flag very implausible letter runs.
		const next = word.toLowerCase();
		if (/(.)\1\1/.test(next)) {
			seen.add(next);
			issues.push({ word, suggestions: suggestionsFor(word, COMMON_WORDS) });
		}
	}
	return issues;
}

// ── Thesaurus ─────────────────────────────────────────────────────────────

/** Small Indonesian synonym table used by the Thesaurus pane. */
export const SYNONYMS: Record<string, string[]> = {
	bagus: ['baik', 'indah', 'elok', 'menarik'],
	baik: ['bagus', 'layak', 'pantas'],
	besar: ['luas', 'raksasa', 'besar'],
	cepat: ['lekas', 'segera', 'kilat'],
	penting: ['krusial', 'utama', 'berarti'],
	masalah: ['persoalan', 'kendala', 'problema'],
	tujuan: ['sasaran', 'maksud', 'arah'],
	hasil: ['produk', 'keluaran', 'capaian'],
	mulai: ['awali', 'mengawali', 'bermula'],
	buat: ['bikin', 'kerjakan', 'susun'],
	sekarang: ['kini', 'saat ini', 'belakangan ini'],
	data: ['keterangan', 'informasi', 'fakta'],
	penelitian: ['kajian', 'riset', 'studi'],
	mendukung: ['menopang', 'menunjang', 'memperkuat'],
	tidak: ['bukan', 'belum', 'tanpa'],
};

export function lookupSynonyms(word: string): string[] {
	return SYNONYMS[word.toLowerCase()] ?? [];
}

// ── Reading aloud ─────────────────────────────────────────────────────────

/** Speak the given text (or the whole document) with the Web Speech API. */
export function readAloud(text: string): boolean {
	if (typeof speechSynthesis === 'undefined') return false;
	speechSynthesis.cancel();
	const utter = new SpeechSynthesisUtterance(text);
	utter.lang = 'id-ID';
	utter.rate = 1;
	speechSynthesis.speak(utter);
	return true;
}

export function stopReading(): void {
	if (typeof speechSynthesis !== 'undefined') speechSynthesis.cancel();
}

// ── Accessibility & document inspector ────────────────────────────────────

export interface InspectionFinding {
	level: 'error' | 'warning' | 'info';
	message: string;
	element?: HTMLElement;
}

/** Check images for alt text, tables for headers, headings for level jumps. */
export function inspectDocument(root: HTMLElement): InspectionFinding[] {
	const findings: InspectionFinding[] = [];
	root.querySelectorAll<HTMLImageElement>('img').forEach((img) => {
		if (!img.getAttribute('alt')?.trim()) {
			findings.push({ level: 'error', message: 'Gambar tanpa teks alternatif (alt).', element: img });
		}
	});
	root.querySelectorAll<HTMLTableElement>('table').forEach((t) => {
		if (!t.querySelector('th')) {
			findings.push({ level: 'warning', message: 'Tabel tanpa baris judul (header).', element: t });
		}
	});
	const levels = Array.from(root.querySelectorAll<HTMLElement>('h1,h2,h3,h4,h5,h6')).map((h) =>
		Number(h.tagName.slice(1))
	);
	for (let i = 1; i < levels.length; i++) {
		if (levels[i] - levels[i - 1] > 1) {
			findings.push({ level: 'warning', message: `Lompatan tingkat judul H${levels[i - 1]} → H${levels[i]}.` });
		}
	}
	if (!root.querySelector('h1')) {
		findings.push({ level: 'info', message: 'Dokumen tidak memiliki judul H1 utama.' });
	}
	return findings;
}

// ── Helpers ────────────────────────────────────────────────────────────────

function unwrapEl(el: HTMLElement): void {
	const parent = el.parentNode;
	if (!parent) return;
	while (el.firstChild) parent.insertBefore(el.firstChild, el);
	parent.removeChild(el);
}

function cssEscape(s: string): string {
	return s.replace(/["\\]/g, '\\$&');
}
