// 工作区卡片：name/slug/status badge/port/role/创建时间 + 启停/暂停/恢复/删除/打开
// 按状态机 canPerformAction 禁用非法操作
import {
  ExternalLink,
  Pause,
  Play,
  Square,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { StatusBadge } from "@/components/StatusBadge";
import {
  canDelete,
  canOpen,
  canPerformAction,
} from "@/lib/workspace";
import type { Workspace, WorkspaceAction } from "@/types";

export interface WorkspaceCardProps {
  workspace: Workspace;
  onAction: (id: string, action: WorkspaceAction) => void;
  onDelete: (id: string) => void;
  busy?: boolean;
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("zh-CN", { hour12: false });
  } catch {
    return iso;
  }
}

export function WorkspaceCard({
  workspace,
  onAction,
  onDelete,
  busy,
}: WorkspaceCardProps) {
  const { id, name, slug, status, external_port, role, created_at } = workspace;
  const isBusy = busy ? id : undefined;

  return (
    <Card data-testid={`workspace-card-${slug}`}>
      <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-3">
        <div className="space-y-1">
          <CardTitle className="text-base">{name}</CardTitle>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <code className="rounded bg-muted px-1.5 py-0.5">{slug}</code>
            <span>·</span>
            <span>{role}</span>
          </div>
        </div>
        <StatusBadge status={status} />
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="flex flex-wrap gap-x-6 gap-y-1 text-muted-foreground">
          <span>端口：{external_port}</span>
          <span>创建：{formatDate(created_at)}</span>
        </div>
        {status === "error" && workspace.error_message && (
          <div
            className="rounded border border-destructive/50 bg-destructive/10 p-2 text-xs text-destructive"
            data-testid="ws-error-message"
          >
            {workspace.error_message}
          </div>
        )}
        <div
          className="flex flex-wrap gap-2 pt-1"
          data-testid="ws-actions"
        >
          <ActionButton
            testId={`ws-open-${slug}`}
            disabled={!canOpen(status)}
            onClick={() => window.open(`/ws/${slug}/`, "_blank")}
            variant="outline"
            size="sm"
            icon={<ExternalLink className="h-4 w-4" />}
          >
            打开
          </ActionButton>

          <ActionButton
            testId={`ws-start-${slug}`}
            disabled={!canPerformAction(status, "start") || isBusy === id}
            onClick={() => onAction(id, "start")}
            variant="default"
            size="sm"
            icon={<Play className="h-4 w-4" />}
          >
            启动
          </ActionButton>

          <ActionButton
            testId={`ws-stop-${slug}`}
            disabled={!canPerformAction(status, "stop") || isBusy === id}
            onClick={() => onAction(id, "stop")}
            variant="outline"
            size="sm"
            icon={<Square className="h-4 w-4" />}
          >
            停止
          </ActionButton>

          <ActionButton
            testId={`ws-pause-${slug}`}
            disabled={!canPerformAction(status, "pause") || isBusy === id}
            onClick={() => onAction(id, "pause")}
            variant="outline"
            size="sm"
            icon={<Pause className="h-4 w-4" />}
          >
            暂停
          </ActionButton>

          <ActionButton
            testId={`ws-resume-${slug}`}
            disabled={!canPerformAction(status, "resume") || isBusy === id}
            onClick={() => onAction(id, "resume")}
            variant="outline"
            size="sm"
            icon={<Play className="h-4 w-4" />}
          >
            恢复
          </ActionButton>

          <ActionButton
            testId={`ws-delete-${slug}`}
            disabled={!canDelete(status) || isBusy === id}
            onClick={() => onDelete(id)}
            variant="destructive"
            size="sm"
            icon={<Trash2 className="h-4 w-4" />}
          >
            删除
          </ActionButton>
        </div>
      </CardContent>
    </Card>
  );
}

interface ActionButtonProps {
  testId: string;
  disabled?: boolean;
  onClick: () => void;
  variant: "default" | "outline" | "destructive" | "secondary" | "ghost" | "link";
  size: "sm" | "default" | "lg" | "icon";
  icon: React.ReactNode;
  children: React.ReactNode;
}

function ActionButton({
  testId,
  disabled,
  onClick,
  variant,
  size,
  icon,
  children,
}: ActionButtonProps) {
  return (
    <Button
      type="button"
      variant={variant}
      size={size}
      disabled={disabled}
      onClick={onClick}
      data-testid={testId}
    >
      {icon}
      {children}
    </Button>
  );
}
