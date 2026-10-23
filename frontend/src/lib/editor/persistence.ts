/**
 * persistence — autosave, crash recovery, version history and document
 * properties for Naskah Studio.
 *
 * Word keeps four things beside a document: the current text, an autosaved
 * copy that survives a crash (the "Recover Unsaved Documents" bin), a version
 * history, and the document properties (title, author, subject, keywords).
 * This module mirrors all four with localStorage, under one namespaced prefix,
 * so a page reload or a tab crash never loses a manuscript.
 */

import { notify } from '$lib/stores/notify.svelte';

const PREFIX = 'omnigensi.naskah';
const MAX_VERSIONS = 20;

export interface DocProperties {
	title: string;
	author: string;
	subject: string;
	keywords: string;
	comments: string;
}

export interface Version {
	at: number;
	html: string;
	title: string;
	words: number;
}

export const DEFAULT_PROPERTIES: DocProperties = {
	title: 'Naskah Tanpa Judul',
	author: '',
	subject: '',
	keywords: '',
	comments: '',
};

function key(name: string): string {
	return `${PREFIX}.${name}.v2`;
}

function safeGet<T>(name: string, fallback: T): T {
	try {
		const raw = localStorage.getItem(key(name));
		return raw ? (JSON.parse(raw) as T) : fallback;
	} catch {
		return fallback;
	}
}

function safeSet(name: string, value: unknown): boolean {
	try {
		localStorage.setItem(key(name), JSON.stringify(value));
		return true;
	} catch (e) {
		// Quota exceeded is the common failure: try to make room by trimming versions.
		try {
			const versions = safeGet<Version[]>('versions', []).slice(-5);
			localStorage.setItem(key('versions'), JSON.stringify(versions));
			localStorage.setItem(key(name), JSON.stringify(value));
			return true;
		} catch {
			notify.fromError(e, 'Penyimpanan lokal penuh — simpan ke berkas');
			return false;
		}
	}
}

// ── Draft & recovery ──────────────────────────────────────────────────────

export interface Draft {
	html: string;
	title: string;
	at: number;
}

/** Save the working draft (autosave tick + every explicit save). */
export function saveDraft(html: string, title: string): void {
	safeSet('draft', { html, title, at: Date.now() } satisfies Draft);
}

/** Read the working draft, or null on first run. */
export function loadDraft(): Draft | null {
	return safeGet<Draft | null>('draft', null);
}

/**
 * Move the draft into the recovery bin before starting a new document, so
 * "Recover Unsaved Documents" can bring it back.
 */
export function stashRecovery(html: string, title: string): void {
	const bin = safeGet<Draft[]>('recovery', []);
	bin.unshift({ html, title, at: Date.now() });
	safeSet('recovery', bin.slice(0, 10));
}

/** Everything in the recovery bin. */
export function listRecovery(): Draft[] {
	return safeGet<Draft[]>('recovery', []);
}

export function clearRecovery(at?: number): void {
	const bin = at === undefined ? [] : listRecovery().filter((d) => d.at !== at);
	safeSet('recovery', bin);
}

// ── Version history ───────────────────────────────────────────────────────

/** Record a checkpoint, skipping duplicates of the latest text. */
export function pushVersion(html: string, title: string): void {
	const versions = safeGet<Version[]>('versions', []);
	if (versions.length && versions[versions.length - 1].html === html) return;
	const words = html.replace(/<[^>]+>/g, ' ').trim().split(/\s+/).filter(Boolean).length;
	versions.push({ at: Date.now(), html, title, words });
	safeSet('versions', versions.slice(-MAX_VERSIONS));
}

export function listVersions(): Version[] {
	return safeGet<Version[]>('versions', []);
}

export function restoreVersion(at: number): Version | null {
	return listVersions().find((v) => v.at === at) ?? null;
}

// ── Document properties ───────────────────────────────────────────────────

export function loadProperties(): DocProperties {
	return { ...DEFAULT_PROPERTIES, ...safeGet<Partial<DocProperties>>('properties', {}) };
}

export function saveProperties(props: DocProperties): void {
	safeSet('properties', props);
}

// ── Autosave timer ────────────────────────────────────────────────────────

export interface Autosaver {
	/** Mark the document dirty; the timer persists it on the next tick. */
	touch: () => void;
	/** Persist immediately (Ctrl+S). */
	flush: () => void;
	stop: () => void;
}

/**
 * Start an autosave loop. `snapshot()` returns the current text and title so
 * the saver always stores the latest state, not the state at start time.
 */
export function startAutosave(
	snapshot: () => { html: string; title: string },
	intervalMs = 20000
): Autosaver {
	let dirty = false;
	let timer: ReturnType<typeof setInterval> | null = null;

	const flush = () => {
		const { html, title } = snapshot();
		saveDraft(html, title);
		dirty = false;
	};

	timer = setInterval(() => {
		if (dirty) flush();
	}, intervalMs);

	return {
		touch: () => {
			dirty = true;
		},
		flush,
		stop: () => {
			if (timer) clearInterval(timer);
			timer = null;
		},
	};
}
