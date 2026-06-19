// 统一 fetch wrapper：cookie 鉴权 + 401 refresh 拦截 + 统一 ApiError
// 来源：frontend-api-contract §3/§5、research R3
import type { ApiErrorBody } from "@/types";

export const API_BASE = "/api/v1";
export const REFRESH_URL = "/api/v1/auth/refresh"; // refresh cookie 的 Path=/api/v1/auth/refresh
export const LOGIN_PATH = "/login";

export class ApiError extends Error {
  code: string;
  status: number;
  detail?: unknown;

  constructor(code: string, message: string, status: number, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.detail = detail;
  }
}

async function parseBody(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return undefined;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return undefined;
  }
}

function throwError(status: number, body: unknown): never {
  const errBody = body as ApiErrorBody | undefined;
  const code = errBody?.error?.code ?? "unknown_error";
  const message =
    errBody?.error?.message ?? `请求失败（HTTP ${status}）`;
  throw new ApiError(code, message, status, errBody?.error?.detail);
}

interface RequestOpts {
  method?: string;
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined>;
  // 内部：已尝试过 refresh，避免递归
  _retried?: boolean;
}

function buildUrl(path: string, query?: RequestOpts["query"]): string {
  const url = path.startsWith("http") || path.startsWith("/api/")
    ? path
    : `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
  if (!query) return url;
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v !== undefined && v !== null) params.append(k, String(v));
  }
  const qs = params.toString();
  return qs ? `${url}?${qs}` : url;
}

async function doFetch<T>(
  url: string,
  opts: RequestOpts,
): Promise<T> {
  const headers: Record<string, string> = {
    "X-Requested-With": "XMLHttpRequest",
  };
  let body: BodyInit | undefined;
  if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }

  const res = await fetch(url, {
    method: opts.method ?? "GET",
    headers,
    body,
    credentials: "include",
  });

  if (res.status === 401 && !opts._retried) {
    // 401 拦截：尝试 refresh 一次再重试原请求
    const refreshed = await tryRefresh();
    if (refreshed) {
      return doFetch<T>(url, { ...opts, _retried: true });
    }
    // refresh 也失败 → 重定向登录
    redirectToLogin();
    throw new ApiError("unauthenticated", "未登录或会话已过期", 401);
  }

  if (!res.ok) {
    const parsed = await parseBody(res);
    throwError(res.status, parsed);
  }

  if (res.status === 204) return undefined as T;
  const parsed = await parseBody(res);
  return parsed as T;
}

// 调用 /api/v1/auth/refresh（refresh cookie 的 Path 限定）
export async function tryRefresh(): Promise<boolean> {
  try {
    const res = await fetch(REFRESH_URL, {
      method: "POST",
      headers: { "X-Requested-With": "XMLHttpRequest" },
      credentials: "include",
    });
    return res.ok;
  } catch {
    return false;
  }
}

export function redirectToLogin(): void {
  if (typeof window !== "undefined" && window.location.pathname !== LOGIN_PATH) {
    window.location.href = LOGIN_PATH;
  }
}

export async function apiRequest<T>(path: string, opts: RequestOpts = {}): Promise<T> {
  const url = buildUrl(path, opts.query);
  return doFetch<T>(url, opts);
}
