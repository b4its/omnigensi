/**
 * API client shared by every web surface and mirrored by the mobile app.
 *
 * Base URL resolution order (first non-empty wins):
 *   1. `PUBLIC_API_URL` build-time env var (set per deployment / device)
 *   2. same-origin when the page is served from a non-dev host
 *   3. `http://localhost:8123` for local development
 *
 * Set `PUBLIC_API_URL` to the LAN address of this machine (e.g.
 * `http://192.168.1.10:8123`) when opening the UI from a phone or tablet.
 */

const ENV_API_URL = (import.meta.env.PUBLIC_API_URL as string | undefined)?.trim();

function resolveApiBase(): string {
	if (ENV_API_URL) {
		return ENV_API_URL.replace(/\/+$/, '');
	}
	if (typeof window === 'undefined') {
		// SSR: relative URLs are resolved against the request origin.
		return '';
	}
	const { hostname, origin } = window.location;
	const isLocalDev = hostname === 'localhost' || hostname === '127.0.0.1';
	// Served by the API itself (or a reverse proxy on the same origin).
	if (!isLocalDev) {
		return origin;
	}
	return 'http://localhost:8123';
}

const API_BASE = resolveApiBase();

export { API_BASE };

export interface RequestOptions extends RequestInit {
	/** Query string parameters appended to the endpoint. */
	params?: Record<string, string | number | boolean | undefined | null>;
	/** Per-request timeout in milliseconds (default 20s). */
	timeoutMs?: number;
	/** Number of retries for transient failures (default 1). */
	retries?: number;
}

/** Error carrying the backend's machine-readable code and HTTP status. */
export class ApiError extends Error {
	code?: string;
	status?: number;
	retryable: boolean;

	constructor(message: string, status?: number, code?: string) {
		super(message);
		this.name = 'ApiError';
		this.status = status;
		this.code = code;
		this.retryable = status === undefined || status >= 500 || status === 429;
	}
}

const DEFAULT_TIMEOUT_MS = 20_000;

/** localStorage key mirrored by the auth store. */
const TOKEN_KEY = 'omnigensi_session_token';

/**
 * Reads the bearer token directly from localStorage.
 *
 * Imported lazily rather than from the auth store to avoid a circular
 * dependency (the store itself calls apiFetch).
 */
function sessionToken(): string | null {
	if (typeof localStorage === 'undefined') return null;
	try {
		return localStorage.getItem(TOKEN_KEY);
	} catch {
		return null;
	}
}

function isAbortError(err: unknown): boolean {
	return err instanceof DOMException && err.name === 'AbortError';
}

function buildUrl(endpoint: string, params?: RequestOptions['params']): string {
	const url = `${API_BASE}${endpoint}`;
	if (!params) return url;
	const search = new URLSearchParams();
	for (const [key, value] of Object.entries(params)) {
		if (value !== undefined && value !== null && value !== '') {
			search.append(key, String(value));
		}
	}
	const qs = search.toString();
	return qs ? `${url}?${qs}` : url;
}

export async function apiFetch<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
	const { params, headers: extraHeaders, timeoutMs, retries, ...rest } = options;
	const url = buildUrl(endpoint, params);
	const headers: Record<string, string> = {
		'Content-Type': 'application/json',
		...(extraHeaders as Record<string, string> | undefined)
	};

	// Native clients may not keep cookies, so the bearer token is the primary
	// mechanism; the cookie still works for plain browser usage.
	const token = sessionToken();
	if (token && !headers.Authorization) {
		headers.Authorization = `Bearer ${token}`;
	}

	const maxAttempts = (retries ?? 1) + 1;
	let lastError: unknown;

	for (let attempt = 1; attempt <= maxAttempts; attempt++) {
		// A hung request on a flaky mobile network would otherwise block the
		// caller forever and leave the UI stuck in a loading state.
		const controller = new AbortController();
		const timer = setTimeout(() => controller.abort(), timeoutMs ?? DEFAULT_TIMEOUT_MS);
		// Chain an externally provided signal so callers can still cancel.
		if (rest.signal) {
			const external = rest.signal;
			if (external.aborted) controller.abort();
			else external.addEventListener('abort', () => controller.abort(), { once: true });
		}

		try {
			const res = await fetch(url, {
				...rest,
				headers,
				signal: controller.signal,
				credentials: 'include'
			});

			if (!res.ok) {
				let errorMsg = `API Request failed with status ${res.status}`;
				let code: string | undefined;
				try {
					const errJson = await res.json();
					// The backend normalises every error to `detail: string`, but
					// tolerate the legacy shape for older deployments.
					if (errJson.detail) {
						errorMsg =
							typeof errJson.detail === 'string'
								? errJson.detail
								: JSON.stringify(errJson.detail);
					}
					code = errJson.code;
				} catch {
					/* non-JSON body */
				}
				const error = new ApiError(errorMsg, res.status, code);
				if (res.status === 401) {
					error.retryable = false;
					window.dispatchEvent(new CustomEvent('omnigensi:unauthorized'));
				}
				throw error;
			}
			if (res.status === 204) {
				return {} as T;
			}
			return (await res.json()) as T;
		} catch (err) {
			lastError = isAbortError(err)
				? new ApiError('Request timed out - check the backend connection')
				: err;
			const retryable = lastError instanceof ApiError ? lastError.retryable : true;
			if (attempt >= maxAttempts || !retryable) break;
			// Linear backoff: 400ms, 800ms, ...
			await new Promise((r) => setTimeout(r, 400 * attempt));
		} finally {
			clearTimeout(timer);
		}
	}

	throw lastError instanceof Error ? lastError : new ApiError('Network request failed');
}

/** Pagination window matching the backend `limit`/`offset` query params. */
export interface PageParams {
	limit?: number;
	offset?: number;
}

export interface SystemStats {
	providers: number;
	providers_active: number;
	agents: number;
	workflows: number;
	executions: {
		total: number;
		completed: number;
		failed: number;
		running: number;
		pending: number;
		waiting_approval: number;
		cancelled: number;
	};
	total_tokens: number;
	estimated_cost_usd: number;
	mcp_servers: number;
	mcp_servers_enabled: number;
	tools_available: number;
	generated_at: string;
}

export interface ClientConfig {
	service: string;
	version: string;
	api_version: string;
	api_base_path: string;
	base_url: string;
	docs_url: string;
	openapi_url: string;
	streaming: {
		path_template: string;
		content_type: string;
		events: string[];
		keepalive?: string;
	};
	pagination: { params: string[]; default_limit: number; max_limit: number };
	features: Record<string, boolean>;
	limits: Record<string, number>;
}

export const api = {
	// System
	getClientConfig: () => apiFetch<ClientConfig>('/api/v1/config'),
	getStats: () => apiFetch<SystemStats>('/api/v1/stats'),
	checkHealth: () =>
		apiFetch<{ status: string; service: string; version: string }>('/api/v1/health', {
			retries: 0,
			timeoutMs: 5000
		}),

	// Providers
	getProviders: (page?: PageParams) =>
		apiFetch<any[]>('/api/v1/providers', { params: page as Record<string, number> }),
	getProvider: (id: string) => apiFetch<any>(`/api/v1/providers/${id}`),
	createProvider: (data: any, autoSyncModels = false) =>
		apiFetch<any>(
			`/api/v1/providers${autoSyncModels ? '?auto_sync_models=true' : ''}`,
			{ method: 'POST', body: JSON.stringify(data), timeoutMs: 40_000 }
		),
	updateProvider: (id: string, data: any) =>
		apiFetch<any>(`/api/v1/providers/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
	deleteProvider: (id: string) =>
		apiFetch<void>(`/api/v1/providers/${id}`, { method: 'DELETE' }),
	getProviderModels: (id: string) => apiFetch<any[]>(`/api/v1/providers/${id}/models`),

	/** Discover and store every model the provider reports. */
	syncProviderModels: (id: string) =>
		apiFetch<{
			ok: boolean;
			provider_id: string;
			discovered: number;
			added: number;
			updated: number;
			marked_unavailable: number;
			total_stored: number;
			checked_url?: string | null;
			latency_ms: number;
			error?: string | null;
		}>(`/api/v1/providers/${id}/models/sync`, {
			method: 'POST',
			timeoutMs: 30_000
		}),

	/** Models already stored for this provider (no live call). */
	getProviderModelRegistry: (id: string) =>
		apiFetch<any[]>(`/api/v1/providers/${id}/model-registry`),

	/** Choose which stored model the provider should use by default. */
	setDefaultProviderModel: (id: string, modelId: string) =>
		apiFetch<any>(`/api/v1/providers/${id}/default-model`, {
			method: 'PUT',
			body: JSON.stringify({ model_id: modelId })
		}),

	/** Probe unsaved credentials during registration. */
	discoverDraftModels: (data: {
		base_url: string;
		api_key?: string;
		provider_type?: string;
	}) =>
		apiFetch<{
			ok: boolean;
			models: { id: string; name?: string | null; context_length?: number | null }[];
			checked_url?: string | null;
			latency_ms: number;
			error?: string | null;
		}>('/api/v1/providers/discover-draft', {
			method: 'POST',
			body: JSON.stringify(data),
			timeoutMs: 30_000
		}),

	/** Chat completion against unsaved credentials. */
	testDraftChat: (data: {
		base_url: string;
		api_key?: string;
		provider_type?: string;
		model_id: string;
		prompt?: string;
	}) =>
		apiFetch<{
			ok: boolean;
			model_id: string;
			response_text?: string | null;
			latency_ms: number;
			prompt_tokens?: number | null;
			completion_tokens?: number | null;
			error?: string | null;
		}>('/api/v1/providers/chat-test-draft', {
			method: 'POST',
			body: JSON.stringify(data),
			timeoutMs: 70_000,
			retries: 0
		}),

	/** Run a real completion to prove key + model + routing work. */
	testProviderChat: (id: string, modelId?: string, prompt?: string) =>
		apiFetch<{
			ok: boolean;
			model_id: string;
			response_text?: string | null;
			latency_ms: number;
			status_code?: number | null;
			prompt_tokens?: number | null;
			completion_tokens?: number | null;
			checked_url?: string | null;
			error?: string | null;
		}>(`/api/v1/providers/${id}/chat-test`, {
			method: 'POST',
			body: JSON.stringify({
				model_id: modelId,
				prompt: prompt ?? 'Reply with the single word: OK'
			}),
			timeoutMs: 70_000,
			retries: 0
		}),
	testProvider: (id: string) =>
		apiFetch<{
			ok: boolean;
			status_code?: number | null;
			checked_url?: string | null;
			model_count: number;
			latency_ms: number;
			error?: string | null;
		}>(`/api/v1/providers/${id}/test`, { method: 'POST', timeoutMs: 15_000 }),

	// Agents
	getAgents: (page?: PageParams) =>
		apiFetch<any[]>('/api/v1/agents', { params: page as Record<string, number> }),
	getAgent: (id: string) => apiFetch<any>(`/api/v1/agents/${id}`),
	createAgent: (data: any) =>
		apiFetch<any>('/api/v1/agents', { method: 'POST', body: JSON.stringify(data) }),
	updateAgent: (id: string, data: any) =>
		apiFetch<any>(`/api/v1/agents/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
	deleteAgent: (id: string) => apiFetch<void>(`/api/v1/agents/${id}`, { method: 'DELETE' }),
	testAgent: (id: string, prompt: string, maxTokens?: number) =>
		apiFetch<{
			ok: boolean;
			agent_id: string;
			agent_name: string;
			model_name: string;
			provider_name?: string | null;
			response_text?: string | null;
			latency_ms: number;
			prompt_tokens?: number | null;
			completion_tokens?: number | null;
			error?: string | null;
		}>(`/api/v1/agents/${id}/test`, {
			method: 'POST',
			body: JSON.stringify({ prompt, max_tokens: maxTokens }),
			timeoutMs: 90_000,
			retries: 0
		}),
	duplicateAgent: (id: string, name?: string) =>
		apiFetch<any>(`/api/v1/agents/${id}/duplicate`, {
			method: 'POST',
			body: JSON.stringify(name ? { name } : {})
		}),

	// Tools
	getTools: () => apiFetch<any[]>('/api/v1/tools'),
	executeTool: (toolId: string, args: Record<string, any>) =>
		apiFetch<{ ok: boolean; tool_id: string; result?: any; error?: string | null }>(
			`/api/v1/tools/${encodeURIComponent(toolId)}/execute`,
			{ method: 'POST', body: JSON.stringify({ arguments: args }), timeoutMs: 60_000 }
		),

	// Workflows
	getWorkflows: (page?: PageParams & { q?: string }) =>
		apiFetch<any[]>('/api/v1/workflows', {
			params: page as Record<string, string | number>
		}),
	validateWorkflowGraph: (data: { name: string; graph_schema: any; max_revisions?: number }) =>
		apiFetch<{
			valid: boolean;
			summary: string;
			node_count: number;
			edge_count: number;
			entry_point?: string | null;
			issues: { code: string; message: string; node_id?: string; edge_index?: number; field?: string }[];
		}>('/api/v1/workflows/validate', { method: 'POST', body: JSON.stringify(data) }),
	validateSavedWorkflow: (id: string) =>
		apiFetch<{
			valid: boolean;
			summary: string;
			issues: { code: string; message: string; node_id?: string; edge_index?: number; field?: string }[];
		}>(`/api/v1/workflows/${id}/validate`),
	duplicateWorkflow: (id: string, name?: string) =>
		apiFetch<any>(`/api/v1/workflows/${id}/duplicate`, {
			method: 'POST',
			body: JSON.stringify(name ? { name } : {})
		}),
	getWorkflow: (id: string) => apiFetch<any>(`/api/v1/workflows/${id}`),
	createWorkflow: (data: any) =>
		apiFetch<any>('/api/v1/workflows', { method: 'POST', body: JSON.stringify(data) }),
	updateWorkflow: (id: string, data: any) =>
		apiFetch<any>(`/api/v1/workflows/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
	deleteWorkflow: (id: string) =>
		apiFetch<void>(`/api/v1/workflows/${id}`, { method: 'DELETE' }),
	executeWorkflow: (id: string, taskPrompt: string) =>
		apiFetch<any>(`/api/v1/workflows/${id}/execute`, {
			method: 'POST',
			body: JSON.stringify({ task_prompt: taskPrompt })
		}),

	// Executions
	getExecutions: (page?: PageParams & { status?: string; workflow_id?: string }) =>
		apiFetch<any[]>('/api/v1/executions', {
			params: page as Record<string, string | number>
		}),
	getExecution: (id: string) => apiFetch<any>(`/api/v1/executions/${id}`),
	/**
	 * URL used by EventSource, which cannot set headers.
	 *
	 * A short-lived stream ticket replaces the session token so the long-lived
	 * credential never appears in URLs, access logs or Referer headers. Call
	 * `api.createStreamTicket()` first and pass the ticket here.
	 */
	getExecutionStreamUrl: (id: string, ticket?: string | null) => {
		const suffix = ticket ? `?token=${encodeURIComponent(ticket)}` : '';
		return `${API_BASE}/api/v1/executions/${id}/stream${suffix}`;
	},

	/** Exchanges the current session for a short-lived URL credential. */
	createStreamTicket: () =>
		apiFetch<{ ticket: string; expires_at: number }>('/api/v1/auth/stream-ticket', {
			method: 'POST',
			retries: 0
		}),
	approveTool: (id: string, toolCallId: string, approved: boolean, notes?: string) =>
		apiFetch<any>(`/api/v1/executions/${id}/approve-tool`, {
			method: 'POST',
			body: JSON.stringify({ tool_call_id: toolCallId, approved, notes })
		}),
	retryExecution: (id: string) =>
		apiFetch<any>(`/api/v1/executions/${id}/retry`, { method: 'POST' }),
	deleteExecution: (id: string) =>
		apiFetch<void>(`/api/v1/executions/${id}`, { method: 'DELETE' }),
	cancelExecution: (id: string) =>
		apiFetch<{ success: boolean; status: string; message: string }>(
			`/api/v1/executions/${id}/cancel`,
			{ method: 'POST' }
		),

	// MCP
	getMCPServers: () => apiFetch<any[]>('/api/v1/mcp/servers'),
	registerMCPServer: (data: any) =>
		apiFetch<any>('/api/v1/mcp/servers', { method: 'POST', body: JSON.stringify(data) }),
	updateMCPServer: (serverName: string, data: any) =>
		apiFetch<any>(`/api/v1/mcp/servers/${encodeURIComponent(serverName)}`, {
			method: 'PUT',
			body: JSON.stringify(data)
		}),
	toggleMCPServer: (serverName: string, enabled: boolean) =>
		apiFetch<any>(`/api/v1/mcp/servers/${encodeURIComponent(serverName)}`, {
			method: 'PATCH',
			body: JSON.stringify({ enabled })
		}),
	deleteMCPServer: (serverName: string) =>
		apiFetch<void>(`/api/v1/mcp/servers/${encodeURIComponent(serverName)}`, {
			method: 'DELETE'
		}),
	getMCPServerTools: (serverName: string) =>
		apiFetch<{ server: string; tools: any[] }>(
			`/api/v1/mcp/servers/${encodeURIComponent(serverName)}/tools`
		),
	executeMCPTool: (serverName: string, toolName: string, args: Record<string, any>) =>
		apiFetch<{ status: string; result: any; message?: string }>(
			`/api/v1/mcp/servers/${encodeURIComponent(serverName)}/tools/${encodeURIComponent(toolName)}/execute`,
			{ method: 'POST', body: JSON.stringify({ arguments: args }) }
		),

	// Files
	getFileDownloadUrl: (filepath: string, ticket?: string | null) => {
		const suffix = ticket ? `?token=${encodeURIComponent(ticket)}` : '';
		return `${API_BASE}/api/v1/files/${filepath.split('/').map(encodeURIComponent).join('/')}${suffix}`;
	},

	// Device pairing helper: probes a candidate base URL (used by mobile setup)
	probeBaseUrl: async (baseUrl: string): Promise<boolean> => {
		try {
			const res = await fetch(`${baseUrl.replace(/\/+$/, '')}/api/v1/health`);
			return res.ok;
		} catch {
			return false;
		}
	}
};
