declare global {
  interface Window {
    investnet?: {
      backendPort: () => Promise<number>;
      openFile: (opts?: { filters?: { name: string; extensions: string[] }[] }) => Promise<string | null>;
      openExternal: (url: string) => Promise<void>;
      openMailto: (p: { to?: string; subject?: string; body?: string }) => Promise<void>;
    };
  }
}

let cachedBase: string | null = null;

export async function apiBase(): Promise<string> {
  if (cachedBase) return cachedBase;
  if (window.investnet) {
    const port = await window.investnet.backendPort();
    cachedBase = `http://127.0.0.1:${port}/api/v1`;
  } else {
    cachedBase = (import.meta as any).env.VITE_API_BASE || 'http://127.0.0.1:8000/api/v1';
  }
  return cachedBase;
}

export async function api<T = any>(path: string, init: RequestInit = {}): Promise<T> {
  const base = await apiBase();
  const r = await fetch(`${base}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init.headers || {}) },
  });
  if (!r.ok) {
    const text = await r.text().catch(() => '');
    throw new Error(`HTTP ${r.status}: ${text}`);
  }
  if (r.status === 204) return undefined as any;
  return r.json();
}

export async function streamTask(taskId: number, onEvent: (ev: any) => void): Promise<void> {
  const base = await apiBase();
  return new Promise((resolve, reject) => {
    const es = new EventSource(`${base}/tasks/${taskId}/stream`);
    es.addEventListener('snapshot', (e: MessageEvent) => onEvent(JSON.parse(e.data)));
    es.addEventListener('update', (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      onEvent(data);
      if (data.done || data.failed) { es.close(); resolve(); }
    });
    es.addEventListener('error', () => { es.close(); reject(new Error('SSE error')); });
  });
}
