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
	const { params, headers: extraHeaders, ...rest } = options;
	const url = buildUrl(endpoint, params);
	const headers = {
		'Content-Type': 'application/json',
		...(extraHeaders || {}),
	};

	const res = await fetch(url, { ...rest, headers });
	if (!res.ok) {
		let errorMsg = `API Request failed with status ${res.status}`;
		try {
			const errJson = await res.json();
			// The backend now normalises every error to `detail: string`, but
			// keep tolerating the legacy shape for older deployments.
			if (errJson.detail) {
				errorMsg =
					typeof errJson.detail === 'string'
						? errJson.detail
						: JSON.stringify(errJson.detail);
			}
			const err = new Error(errorMsg) as Error & { code?: string; status?: number };
			err.code = errJson.code;
			err.status = res.status;
			throw err;
		} catch (parsed) {
			if (parsed instanceof Error) throw parsed;
		}
		throw new Error(errorMsg);
	}
	if (res.status === 204) {
		return {} as T;
	}
	return res.json();
}

/** Pagination window matching the backend `limit`/`offset` query params. */
export interface PageParams {
	limit?: number;
	offset?: number;
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
	checkHealth: () =>
		apiFetch<{ status: string; service: string; version: string }>('/api/v1/health'),

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
	getExecutions: (page?: PageParams) =>
		apiFetch<any[]>('/api/v1/executions', { params: page as Record<string, number> }),
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
