// 与 orchestrator REST API 契约对齐的 TS 类型
// 来源：specs/003-sandbox-p3-launcher/contracts/frontend-api-contract.md §2

// 鉴权 / 用户
export type Provider = "github" | "google";

export interface User {
  id: string;
  email: string;
  display_name: string | null;
  avatar_url: string | null;
}

export interface OAuthAccount {
  provider: Provider;
  email: string | null;
  created_at: string; // ISO 8601 UTC
}

export interface OAuthAccountsResponse {
  accounts: OAuthAccount[];
}

// Workspace（对齐 P2 workspace schema）
export type WorkspaceStatus =
  | "created"
  | "starting"
  | "running"
  | "paused"
  | "stopped"
  | "deleted"
  | "error";

export type Role = "owner" | "collaborator" | "viewer";

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  status: WorkspaceStatus;
  external_port: number;
  role: Role;
  created_at: string; // ISO 8601 UTC
  last_active_at: string | null;
  error_message: string | null; // error 状态可读信息（FR-018）
}

export interface CreateWorkspacePayload {
  name: string;
  slug: string;
  template?: string;
}

export type WorkspaceAction = "start" | "stop" | "pause" | "resume";

// 审计（对齐 P2 audit schema）
export type AuditType =
  | "shell.exec"
  | "fs.write"
  | "browser.action"
  | "gui.action";

export interface AuditEvent {
  id: string;
  workspace_id: string;
  type: AuditType;
  actor_user_id: string | null;
  created_at: string; // ISO 8601 UTC
  summary: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

// 统一错误
export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    detail?: unknown;
  };
}

// OAuth 登录错误码（回流 ?error 参数）
export type OAuthErrorCode = "oauth_failed" | "oauth_unreachable";
