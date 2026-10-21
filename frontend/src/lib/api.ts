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
	const headers = {
		'Content-Type': 'application/json',
		...(extraHeaders || {})
	};

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
			const res = await fetch(url, { ...rest, headers, signal: controller.signal });

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
				throw new ApiError(errorMsg, res.status, code);
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
	createProvider: (data: any) =>
		apiFetch<any>('/api/v1/providers', { method: 'POST', body: JSON.stringify(data) }),
	updateProvider: (id: string, data: any) =>
		apiFetch<any>(`/api/v1/providers/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
	deleteProvider: (id: string) =>
		apiFetch<void>(`/api/v1/providers/${id}`, { method: 'DELETE' }),
	getProviderModels: (id: string) => apiFetch<any[]>(`/api/v1/providers/${id}/models`),
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

	// Tools
	getTools: () => apiFetch<any[]>('/api/v1/tools'),

	// Workflows
	getWorkflows: (page?: PageParams) =>
		apiFetch<any[]>('/api/v1/workflows', { params: page as Record<string, number> }),
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
	getExecutionStreamUrl: (id: string) => `${API_BASE}/api/v1/executions/${id}/stream`,
	approveTool: (id: string, toolCallId: string, approved: boolean, notes?: string) =>
		apiFetch<any>(`/api/v1/executions/${id}/approve-tool`, {
			method: 'POST',
			body: JSON.stringify({ tool_call_id: toolCallId, approved, notes })
		}),
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
	getFileDownloadUrl: (filepath: string) =>
		`${API_BASE}/api/v1/files/${filepath.split('/').map(encodeURIComponent).join('/')}`,

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
