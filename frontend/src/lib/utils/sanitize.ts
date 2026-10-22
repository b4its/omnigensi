/**
 * Minimal HTML sanitiser for rendered Markdown.
 *
 * Agent output is LLM-generated and therefore untrusted: a prompt-injected
 * model (or a poisoned MCP tool result) could emit `<img onerror=...>` or a
 * `<script>` tag. The session token lives in localStorage, so injected script
 * would be a token-theft path.
 *
 * This is a deliberately small allowlist sanitiser rather than a full HTML
 * parser: it strips every element and attribute that is not explicitly
 * permitted, and drops all `on*` handlers, `javascript:` URLs and inline
 * style. That is sufficient for the Markdown `marked` produces, without
 * pulling in a new dependency.
 */

const ALLOWED_TAGS = new Set([
	'a', 'b', 'blockquote', 'br', 'code', 'dd', 'del', 'div', 'dl', 'dt',
	'em', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'img', 'ins', 'kbd',
	'li', 'mark', 'ol', 'p', 'pre', 's', 'span', 'strong', 'sub', 'sup',
	'table', 'tbody', 'td', 'tfoot', 'th', 'thead', 'tr', 'u', 'ul'
]);

const ALLOWED_ATTRS: Record<string, Set<string>> = {
	a: new Set(['href', 'title']),
	img: new Set(['src', 'alt', 'title']),
	// Marked emits class only for syntax highlighting spans.
	span: new Set(['class']),
	code: new Set(['class']),
	div: new Set(['class']),
	th: new Set(['align']),
	td: new Set(['align'])
};

/** Tags whose *content* must never be rendered. */
const VOID_CONTENT_TAGS = new Set(['script', 'style', 'iframe', 'object', 'embed']);

const SAFE_URL = /^(https?:|mailto:|tel:|#|\/(?!\/))/i;

function isSafeUrl(value: string): boolean {
	const trimmed = value.trim().replace(/[\u0000-\u001f]/g, '');
	if (/^data:/i.test(trimmed)) {
		// Only inline images may use data URIs; they cannot execute script.
		return /^data:image\/(png|jpe?g|gif|webp|svg\+xml);base64,/i.test(trimmed);
	}
	return SAFE_URL.test(trimmed);
}

/**
 * Sanitises an HTML string, keeping only allowlisted tags/attributes.
 * Runs without DOMParser so it is safe during SSR as well.
 */
export function sanitizeHtml(html: string): string {
	if (typeof html !== 'string' || !html) return '';

	let output = html;

	// 1) Remove dangerous elements together with their content.
	for (const tag of VOID_CONTENT_TAGS) {
		const paired = new RegExp(`<${tag}\\b[^>]*>[\\s\\S]*?<\\/${tag}>`, 'gi');
		output = output.replace(paired, '');
		// Self-closing / unterminated variants.
		output = output.replace(new RegExp(`<${tag}\\b[^>]*\\/?>`, 'gi'), '');
	}

	// 2) Walk every remaining tag and rebuild it from the allowlist.
	output = output.replace(/<\/?([a-zA-Z][\w:-]*)([^>]*)>/g, (match, rawTag, rawAttrs) => {
		const tag = String(rawTag).toLowerCase();
		const isClosing = match.startsWith('</');

		if (!ALLOWED_TAGS.has(tag)) {
			return '';
		}
		if (isClosing) {
			return `</${tag}>`;
		}

		const allowed = ALLOWED_ATTRS[tag];
		if (!allowed) {
			return `<${tag}>`;
		}

		const kept: string[] = [];
		const attrPattern = /([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*("[^"]*"|'[^']*'|[^\s"'>]+)/g;
		let attrMatch: RegExpExecArray | null;

		while ((attrMatch = attrPattern.exec(String(rawAttrs))) !== null) {
			const name = attrMatch[1].toLowerCase();
			if (!allowed.has(name)) continue;
			if (name.startsWith('on')) continue;

			let value = attrMatch[2];
			if (
				(value.startsWith('"') && value.endsWith('"')) ||
				(value.startsWith("'") && value.endsWith("'"))
			) {
				value = value.slice(1, -1);
			}
			// Decode nothing; just validate URL-bearing attributes.
			if ((name === 'href' || name === 'src') && !isSafeUrl(value)) continue;

			const escaped = value.replace(/"/g, '&quot;').replace(/</g, '&lt;');
			kept.push(`${name}="${escaped}"`);
		}

		const attrs = kept.length ? ' ' + kept.join(' ') : '';
		return `<${tag}${attrs}>`;
	});

	// 3) Neutralise any leftover bare "javascript:" scheme.
	output = output.replace(/javascript\s*:/gi, '');

	return output;
}
