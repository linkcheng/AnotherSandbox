// 认证相关 API：本地登录/注册/OAuth 入口
// OAuth /login 是整页 302，前端用 window.location 跳转，不经 fetch
import { apiRequest } from "@/api/client";
import type { Provider, User } from "@/types";

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload {
  email: string;
  password: string;
  display_name?: string;
}

// POST /api/v1/auth/login — 后端 Set-Cookie（HttpOnly）
export async function login(payload: LoginPayload): Promise<User> {
  return apiRequest<User>("/auth/login", {
    method: "POST",
    body: payload,
  });
}

// POST /api/v1/auth/register — 后端 Set-Cookie
export async function register(payload: RegisterPayload): Promise<User> {
  return apiRequest<User>("/auth/register", {
    method: "POST",
    body: payload,
  });
}

// GET /api/v1/me — 取当前用户（cookie 鉴权）
export async function fetchMe(): Promise<User> {
  return apiRequest<User>("/me");
}

// OAuth 发起 URL（整页跳转，后端 302 到 IdP）
export function oauthLoginUrl(provider: Provider, redirect = "/workspaces"): string {
  return `/api/v1/auth/oauth/${provider}/login?redirect=${encodeURIComponent(redirect)}`;
}

// 发起 OAuth 登录（整页跳转）
export function startOAuthLogin(provider: Provider, redirect = "/workspaces"): void {
  if (typeof window !== "undefined") {
    window.location.href = oauthLoginUrl(provider, redirect);
  }
}

// 登出：P3 暂无 logout 端点，前端清状态 + 重定向登录页
export async function logout(): Promise<void> {
  if (typeof window !== "undefined") {
    window.location.href = "/login";
  }
}
