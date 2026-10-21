/**
 * Session state for the single-password deployment.
 *
 * The backend also sets an httpOnly cookie, but mobile WebViews and native
 * clients may run with cookies disabled, so the bearer token is mirrored in
 * localStorage and sent on every request.
 */

import { apiFetch } from '$lib/api';

const STORAGE_KEY = 'omnigensi_session_token';

class AuthStore {
  /** Null until the first session check resolves. */
  authenticated = $state<boolean | null>(null);
  authEnabled = $state<boolean>(true);
  token = $state<string | null>(null);
  loading = $state<boolean>(true);
  error = $state<string | null>(null);

  constructor() {
    if (typeof localStorage !== 'undefined') {
      this.token = localStorage.getItem(STORAGE_KEY);
    }
  }

  /** Reads the persisted token without touching Svelte state (for api.ts). */
  static readToken(): string | null {
    if (typeof localStorage === 'undefined') return null;
    return localStorage.getItem(STORAGE_KEY);
  }

  private persist(token: string | null) {
    this.token = token;
    if (typeof localStorage === 'undefined') return;
    if (token) localStorage.setItem(STORAGE_KEY, token);
    else localStorage.removeItem(STORAGE_KEY);
  }

  /** Asks the backend whether this client is signed in. */
  async check() {
    this.loading = true;
    this.error = null;
    try {
      const res = await apiFetch<{ authenticated: boolean; auth_enabled: boolean }>(
        '/api/v1/auth/session',
        { retries: 0, timeoutMs: 8000 }
      );
      this.authEnabled = res.auth_enabled;
      this.authenticated = res.authenticated;
      // A stale token that the backend no longer accepts should be dropped.
      if (!res.authenticated && this.token) this.persist(null);
    } catch (err) {
      // A network failure is not the same as "signed out"; let the caller
      // decide how to present it, but do not claim the user is authenticated.
      this.authenticated = false;
      this.error = err instanceof Error ? err.message : 'Unable to reach the backend';
    } finally {
      this.loading = false;
    }
  }

  async login(password: string): Promise<boolean> {
    this.loading = true;
    this.error = null;
    try {
      const res = await apiFetch<{
        authenticated: boolean;
        auth_enabled: boolean;
        token?: string | null;
      }>('/api/v1/auth/login', {
        method: 'POST',
        body: JSON.stringify({ password }),
        retries: 0,
        timeoutMs: 15000
      });
      this.authEnabled = res.auth_enabled;
      this.authenticated = res.authenticated;
      if (res.token) this.persist(res.token);
      return res.authenticated;
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Login failed';
      this.authenticated = false;
      this.persist(null);
      return false;
    } finally {
      this.loading = false;
    }
  }

  async logout() {
    try {
      await apiFetch('/api/v1/auth/logout', { method: 'POST', retries: 0 });
    } catch {
      // Logging out locally must succeed even if the request fails.
    }
    this.persist(null);
    this.authenticated = false;
  }
}

export const auth = new AuthStore();
