// 审计事件表格：shadcn Table + type 徽标 + actor/时间/摘要 + 空/错/loading 态 + 分页
// 来源：frontend-api-contract §2、tasks T052
import { AlertCircle, Inbox } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ApiError } from "@/api/client";
import type { AuditEvent, AuditType, Page } from "@/types";

const TYPE_VARIANT: Record<
  AuditType,
  "default" | "secondary" | "destructive" | "warning" | "outline"
> = {
  "shell.exec": "default",
  "fs.write": "secondary",
  "browser.action": "warning",
  "gui.action": "outline",
};

function formatTime(iso: string): string {
  try {
    return new Intl.DateTimeFormat("zh-CN", {
      hour12: false,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export interface AuditTableProps {
  data: Page<AuditEvent> | undefined;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  page: number; // 当前页（1-based）
  onPageChange: (page: number) => void;
  pageSize: number;
}

export function AuditTable({
  data,
  isLoading,
  isError,
  error,
  page,
  onPageChange,
  pageSize,
}: AuditTableProps) {
  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  if (isLoading && !data) {
    return (
      <div
        className="py-12 text-center text-muted-foreground"
        data-testid="audit-loading"
      >
        加载审计事件…
      </div>
    );
  }

  if (isError) {
    return (
      <div
        className="flex items-center gap-2 rounded-md border border-destructive/50 bg-destructive/10 p-4 text-destructive"
        data-testid="audit-error"
        role="alert"
      >
        <AlertCircle className="h-5 w-5" />
        <span>
          {error instanceof ApiError
            ? error.message
            : "加载审计事件失败，请稍后重试。"}
        </span>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div
        className="flex flex-col items-center justify-center gap-3 py-16 text-muted-foreground"
        data-testid="audit-empty"
      >
        <Inbox className="h-10 w-10" />
        <p>暂无审计事件。</p>
      </div>
    );
  }

  return (
    <div className="space-y-3" data-testid="audit-table">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-32">类型</TableHead>
            <TableHead className="w-24">操作者</TableHead>
            <TableHead className="w-48">时间</TableHead>
            <TableHead>摘要</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((ev) => (
            <TableRow key={ev.id}>
              <TableCell>
                <Badge
                  variant={TYPE_VARIANT[ev.type]}
                  data-testid={`audit-type-${ev.type}`}
                >
                  {ev.type}
                </Badge>
              </TableCell>
              <TableCell className="font-mono text-xs text-muted-foreground">
                {ev.actor_user_id ?? "系统"}
              </TableCell>
              <TableCell className="whitespace-nowrap text-muted-foreground">
                {formatTime(ev.created_at)}
              </TableCell>
              <TableCell>{ev.summary}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span data-testid="audit-total">共 {total} 条</span>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
            data-testid="audit-prev"
          >
            上一页
          </Button>
          <span>
            {page} / {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => onPageChange(page + 1)}
            data-testid="audit-next"
          >
            下一页
          </Button>
        </div>
      </div>
    </div>
  );
}
