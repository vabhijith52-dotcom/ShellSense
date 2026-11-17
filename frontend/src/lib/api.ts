/**
 * ShellSense Typed API Client
 * Enforces per-launch session token Authorization headers and loopback communication.
 */

declare global {
  interface Window {
    pywebview?: {
      api?: {
        get_session_token: () => Promise<string>;
        get_api_port: () => Promise<number>;
      };
    };
  }
}

let cachedToken: string | null = null;
let apiBaseUrl = typeof window !== "undefined" ? `${window.location.origin}/api/v1` : "http://127.0.0.1:5173/api/v1";

export async function ensureToken(): Promise<string | null> {
  if (cachedToken) {
    return cachedToken;
  }

  if (typeof window === "undefined") {
    return null;
  }

  // 1. Check meta tag injected by FastAPI app.py
  const metaToken = document.querySelector('meta[name="shellsense-session-token"]')?.getAttribute("content");
  if (metaToken) {
    cachedToken = metaToken;
    try {
      sessionStorage.setItem("shellsense_token", metaToken);
    } catch {
      // ignore storage restriction
    }
    return metaToken;
  }

  // 2. Check sessionStorage
  try {
    const stored = sessionStorage.getItem("shellsense_token");
    if (stored) {
      cachedToken = stored;
      return stored;
    }
  } catch {
    // ignore
  }

  // 3. Check URL query parameters (browser fallback or web launch)
  const urlParams = new URLSearchParams(window.location.search);
  const tokenFromUrl = urlParams.get("token");
  if (tokenFromUrl) {
    cachedToken = tokenFromUrl;
    try {
      sessionStorage.setItem("shellsense_token", tokenFromUrl);
    } catch {
      // ignore
    }
    // Clean token from address bar to prevent leaking into Referer headers
    window.history.replaceState({}, document.title, window.location.pathname);
    return tokenFromUrl;
  }

  // 4. Check pywebview bridge if already present
  if (window.pywebview?.api?.get_session_token) {
    try {
      const token = await window.pywebview.api.get_session_token();
      if (token) {
        cachedToken = token;
        const port = await window.pywebview.api.get_api_port();
        apiBaseUrl = `http://127.0.0.1:${port}/api/v1`;
        try {
          sessionStorage.setItem("shellsense_token", token);
        } catch {
          // ignore
        }
        return token;
      }
    } catch {
      // Fallback
    }
  }

  // 5. Wait briefly for pywebviewready event
  const tokenFromReady = await new Promise<string | null>((resolve) => {
    let resolved = false;
    const onReady = async () => {
      if (resolved) return;
      resolved = true;
      window.removeEventListener("pywebviewready", onReady);
      if (window.pywebview?.api?.get_session_token) {
        try {
          const token = await window.pywebview.api.get_session_token();
          if (token) {
            const port = await window.pywebview.api.get_api_port();
            apiBaseUrl = `http://127.0.0.1:${port}/api/v1`;
          }
          resolve(token);
          return;
        } catch {
          // ignore
        }
      }
      resolve(null);
    };

    window.addEventListener("pywebviewready", onReady);
    setTimeout(() => {
      if (!resolved) {
        resolved = true;
        window.removeEventListener("pywebviewready", onReady);
        resolve(null);
      }
    }, 600);
  });

  if (tokenFromReady) {
    cachedToken = tokenFromReady;
    try {
      sessionStorage.setItem("shellsense_token", tokenFromReady);
    } catch {
      // ignore
    }
    return tokenFromReady;
  }

  return cachedToken;
}

export async function initApiClient(): Promise<void> {
  await ensureToken();
}

export function setDevToken(token: string, port = 5173): void {
  cachedToken = token;
  apiBaseUrl = `http://127.0.0.1:${port}/api/v1`;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = await ensureToken();
  const headers = new Headers(options.headers || {});
  headers.set("Content-Type", "application/json");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = response.statusText;
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errJson.message || errorDetail;
    } catch {
      // ignore
    }
    throw new Error(errorDetail);
  }

  return response.json() as Promise<T>;
}

export const api = {
  chat: {
    send: (text: string) =>
      request<any>("/chat/messages", {
        method: "POST",
        body: JSON.stringify({ text }),
      }),
  },
  plans: {
    get: (id: string) => request<any>(`/plans/${id}`),
    approve: (id: string, planHash: string, confirmationInput?: string) =>
      request<any>(`/plans/${id}/approve`, {
        method: "POST",
        body: JSON.stringify({
          plan_hash: planHash,
          confirmation_input: confirmationInput || null,
        }),
      }),
    deny: (id: string) => request<any>(`/plans/${id}/deny`, { method: "POST" }),
  },
  system: {
    getInfo: () => request<any>("/system/info"),
    getMonitorHistory: (range = 600) =>
      request<any>(`/monitor/history?range_seconds=${range}`),
  },
  files: {
    list: (path = "") => request<any>(`/files?path=${encodeURIComponent(path)}`),
    createPlan: (action: string, sources: string[], destination?: string) =>
      request<any>("/files/plan", {
        method: "POST",
        body: JSON.stringify({ action, sources, destination }),
      }),
  },
  processes: {
    list: (limit = 100) => request<any>(`/processes?limit=${limit}`),
    createPlan: (action: string, pids: number[]) =>
      request<any>("/processes/plan", {
        method: "POST",
        body: JSON.stringify({ action, pids }),
      }),
  },
  tasks: {
    list: (status?: string) =>
      request<any>(`/tasks${status ? `?status_filter=${status}` : ""}`),
    get: (id: string) => request<any>(`/tasks/${id}`),
    cancel: (id: string) => request<any>(`/tasks/${id}/cancel`, { method: "POST" }),
  },
  history: {
    list: (limit = 50, offset = 0, opType?: string, rangeDays?: number) => {
      let query = `?limit=${limit}&offset=${offset}`;
      if (opType) query += `&op_type=${opType}`;
      if (rangeDays) query += `&range_days=${rangeDays}`;
      return request<any>(`/history${query}`);
    },
    get: (id: number) => request<any>(`/history/${id}`),
  },
  settings: {
    get: () => request<any>("/settings"),
    update: (data: any) =>
      request<any>("/settings", {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
  },
  permissions: {
    get: () => request<any>("/permissions"),
    grant: (data: {
      capabilities: string[];
      folder_roots: string[];
      confirmation_phrase: string;
      nonce: string;
    }) =>
      request<any>("/permissions/grant", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    revoke: () => request<any>("/permissions/revoke", { method: "POST" }),
  },
};
