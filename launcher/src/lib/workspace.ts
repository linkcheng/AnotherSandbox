// workspace 纯函数：slug 校验 / 状态→徽章 variant / 操作合法性状态机
import type { BadgeProps } from "@/components/ui/badge";
import type { WorkspaceAction, WorkspaceStatus } from "@/types";

// slug 规则：3-32 位，小写字母数字与连字符，首尾须为字母数字
const SLUG_REGEX = /^[a-z0-9][a-z0-9-]{1,30}[a-z0-9]$/;
const RESERVED_SLUGS = new Set([
  "api",
  "ws",
  "admin",
  "login",
  "logout",
  "create",
  "workspaces",
  "monitor",
  "auth",
]);

export type SlugValidation = {
  ok: boolean;
  reason?: string;
};

// 校验 slug：格式 + 长度 + 保留词
export function validateSlug(slug: string): SlugValidation {
  if (!slug) return { ok: false, reason: "slug 不能为空" };
  if (slug.length < 3) return { ok: false, reason: "slug 至少 3 位" };
  if (slug.length > 32) return { ok: false, reason: "slug 至多 32 位" };
  if (!SLUG_REGEX.test(slug)) {
    return {
      ok: false,
      reason: "slug 只能含小写字母、数字与连字符，且首尾为字母数字",
    };
  }
  if (RESERVED_SLUGS.has(slug.toLowerCase())) {
    return { ok: false, reason: "该 slug 为系统保留，请换一个" };
  }
  if (slug.includes("--")) {
    return { ok: false, reason: "slug 不允许连续连字符" };
  }
  return { ok: true };
}

// 状态 → shadcn badge variant（仅取其类型）
type Variant = NonNullable<BadgeProps["variant"]>;

export function statusToVariant(status: WorkspaceStatus): Variant {
  switch (status) {
    case "running":
      return "success";
    case "starting":
      return "warning";
    case "paused":
    case "stopped":
      return "secondary";
    case "error":
      return "destructive";
    case "created":
      return "outline";
    case "deleted":
    default:
      return "outline";
  }
}

export const STATUS_LABEL: Record<WorkspaceStatus, string> = {
  created: "已创建",
  starting: "启动中",
  running: "运行中",
  paused: "已暂停",
  stopped: "已停止",
  deleted: "已删除",
  error: "错误",
};

// 状态机：某状态下允许哪些操作（WorkspaceCard 按此禁用按钮）
const ACTION_MATRIX: Record<WorkspaceAction, WorkspaceStatus[]> = {
  start: ["created", "stopped", "paused"],
  stop: ["running", "starting", "paused"],
  pause: ["running"],
  resume: ["paused"],
};

export function canPerformAction(
  status: WorkspaceStatus,
  action: WorkspaceAction,
): boolean {
  if (status === "deleted" || status === "error") return false;
  return ACTION_MATRIX[action].includes(status);
}

// 是否可删除（已创建/已停止/出错 的可删；运行中不可）
export function canDelete(status: WorkspaceStatus): boolean {
  return ["created", "stopped", "error"].includes(status);
}

// 是否可打开（仅 running 状态）
export function canOpen(status: WorkspaceStatus): boolean {
  return status === "running";
}
