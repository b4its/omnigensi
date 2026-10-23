/**
 * commandRegistry — the "Tell Me" search index.
 *
 * Wordcraft's central design idea is that *every* action is a named command:
 * the ribbon, keyboard shortcuts, the command search and the MCP server all
 * call the same registry. Naskah Studio mirrors that for the browser: each
 * ribbon action registers a `Command` with the tabs it appears on, and the
 * search box in the title bar can run any of them by name or tab.
 *
 * The registry is plain data; the page fills it once and the search dialog
 * becomes a thin fuzzy filter over it.
 */

export interface Command {
	/** Stable id, e.g. `format.smallCaps`. */
	id: string;
	/** Human label shown in the search results, Indonesian. */
	label: string;
	/** Ribbon tab the command lives on. */
	tab: string;
	/** Ribbon group inside the tab. */
	group: string;
	/** Extra keywords for search ("tebal", "bold", "b"). */
	keywords?: string[];
	/** Keyboard shortcut hint, purely presentational. */
	shortcut?: string;
	/** The action. */
	run: () => void;
}

export class CommandRegistry {
	#commands = new Map<string, Command>();

	register(cmd: Command): void {
		this.#commands.set(cmd.id, cmd);
	}

	registerAll(cmds: Command[]): void {
		for (const c of cmds) this.register(c);
	}

	get(id: string): Command | undefined {
		return this.#commands.get(id);
	}

	all(): Command[] {
		return [...this.#commands.values()];
	}

	/** Fuzzy-ish search: every query token must appear in the haystack. */
	search(query: string): Command[] {
		const q = query.trim().toLowerCase();
		const list = this.all();
		if (!q) return list;
		const tokens = q.split(/\s+/);
		return list
			.map((cmd) => {
				const hay = [cmd.label, cmd.tab, cmd.group, cmd.id, ...(cmd.keywords ?? [])]
					.join(' ')
					.toLowerCase();
				if (!tokens.every((t) => hay.includes(t))) return null;
				// Prefer prefix matches on the label for ordering.
				const score = cmd.label.toLowerCase().startsWith(q) ? 0 : hay.indexOf(q);
				return { cmd, score };
			})
			.filter((x): x is { cmd: Command; score: number } => x !== null)
			.sort((a, b) => a.score - b.score)
			.map((x) => x.cmd);
	}

	/** Group commands by tab for the search result headers. */
	byTab(): Map<string, Command[]> {
		const groups = new Map<string, Command[]>();
		for (const cmd of this.all()) {
			const list = groups.get(cmd.tab) ?? [];
			list.push(cmd);
			groups.set(cmd.tab, list);
		}
		return groups;
	}
}

/** The process-wide registry; the editor page populates it on mount. */
export const commandRegistry = new CommandRegistry();
