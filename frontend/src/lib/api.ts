const API_BASE = (typeof window !== 'undefined' && window.location.hostname !== 'localhost')
  ? '' 
  : 'http://localhost:8000';

export async function apiFetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  const res = await fetch(url, { ...options, headers });
  if (!res.ok) {
    let errorMsg = `API Request failed with status ${res.status}`;
    try {
      const errJson = await res.json();
      if (errJson.detail) {
        errorMsg = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
      }
    } catch (_) {}
    throw new Error(errorMsg);
  }
  if (res.status === 204) {
    return {} as T;
  }
  return res.json();
}

export const api = {
  // Providers
  getProviders: () => apiFetch<any[]>('/api/v1/providers'),
  getProvider: (id: string) => apiFetch<any>(`/api/v1/providers/${id}`),
  createProvider: (data: any) => apiFetch<any>('/api/v1/providers', { method: 'POST', body: JSON.stringify(data) }),
  updateProvider: (id: string, data: any) => apiFetch<any>(`/api/v1/providers/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteProvider: (id: string) => apiFetch<void>(`/api/v1/providers/${id}`, { method: 'DELETE' }),
  getProviderModels: (id: string) => apiFetch<any[]>(`/api/v1/providers/${id}/models`),

  // Agents
  getAgents: () => apiFetch<any[]>('/api/v1/agents'),
  getAgent: (id: string) => apiFetch<any>(`/api/v1/agents/${id}`),
  createAgent: (data: any) => apiFetch<any>('/api/v1/agents', { method: 'POST', body: JSON.stringify(data) }),
  updateAgent: (id: string, data: any) => apiFetch<any>(`/api/v1/agents/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteAgent: (id: string) => apiFetch<void>(`/api/v1/agents/${id}`, { method: 'DELETE' }),

  // Tools
  getTools: () => apiFetch<any[]>('/api/v1/tools'),

  // Workflows
  getWorkflows: () => apiFetch<any[]>('/api/v1/workflows'),
  getWorkflow: (id: string) => apiFetch<any>(`/api/v1/workflows/${id}`),
  createWorkflow: (data: any) => apiFetch<any>('/api/v1/workflows', { method: 'POST', body: JSON.stringify(data) }),
  updateWorkflow: (id: string, data: any) => apiFetch<any>(`/api/v1/workflows/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteWorkflow: (id: string) => apiFetch<void>(`/api/v1/workflows/${id}`, { method: 'DELETE' }),
  executeWorkflow: (id: string, taskPrompt: string) =>
    apiFetch<any>(`/api/v1/workflows/${id}/execute`, {
      method: 'POST',
      body: JSON.stringify({ task_prompt: taskPrompt }),
    }),

  // Executions
  getExecutions: () => apiFetch<any[]>('/api/v1/executions'),
  getExecution: (id: string) => apiFetch<any>(`/api/v1/executions/${id}`),
  getExecutionStreamUrl: (id: string) => `${API_BASE}/api/v1/executions/${id}/stream`,
  approveTool: (id: string, toolCallId: string, approved: boolean, notes?: string) =>
    apiFetch<any>(`/api/v1/executions/${id}/approve-tool`, {
      method: 'POST',
      body: JSON.stringify({ tool_call_id: toolCallId, approved, notes }),
    }),

  // MCP
  getMCPServers: () => apiFetch<any[]>('/api/v1/mcp/servers'),
  registerMCPServer: (data: any) => apiFetch<any>('/api/v1/mcp/servers', { method: 'POST', body: JSON.stringify(data) }),
  getMCPServerTools: (serverName: string) => apiFetch<any>(`/api/v1/mcp/servers/${serverName}/tools`),

  // Health
  checkHealth: () => apiFetch<any>('/health'),
};
