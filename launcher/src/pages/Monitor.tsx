// 监控页：workspace 选择器 + 状态卡 + AuditTable（10s 轮询由 useAuditEvents 提供）
// 来源：frontend-api-contract §3、tasks T051
import { useState } from "react";
import { useWorkspaces } from "@/api/workspaces";
import { useAuditEvents } from "@/api/audit";
import { AuditTable } from "@/components/AuditTable";
import { StatusBadge } from "@/components/StatusBadge";
import type { Workspace } from "@/types";

const PAGE_SIZE = 20;

export default function Monitor() {
  const ws = useWorkspaces();
  const [selectedId, setSelectedId] = useState<string>("");
  const [page, setPage] = useState(1);

  const selected: Workspace | undefined = ws.data?.find(
    (w) => w.id === selectedId,
  );
  const audit = useAuditEvents(selectedId || null, {
    page,
    pageSize: PAGE_SIZE,
  });

  function onSelect(id: string) {
    setSelectedId(id);
    setPage(1); // 切换 workspace 重置到第一页
  }

  return (
    <div className="container py-8">
      <h1 className="mb-6 text-2xl font-semibold">监控</h1>

      <div className="mb-6 flex items-center gap-3">
        <label htmlFor="workspace-select" className="text-sm">
          工作区
        </label>
        <select
          id="workspace-select"
          className="h-9 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          value={selectedId}
          onChange={(e) => onSelect(e.target.value)}
          data-testid="workspace-select"
        >
          <option value="">请选择工作区…</option>
          {ws.data?.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}（{w.slug}）
            </option>
          ))}
        </select>
      </div>

      {!selectedId && (
        <div
          className="py-16 text-center text-muted-foreground"
          data-testid="monitor-empty"
        >
          请先选择一个工作区以查看监控数据。
        </div>
      )}

      {selected && (
        <div className="space-y-6">
          <div
            className="rounded-lg border bg-card p-4"
            data-testid="monitor-status-card"
          >
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
              <span className="text-lg font-semibold">{selected.name}</span>
              <StatusBadge status={selected.status} />
              <span className="text-muted-foreground">
                端口：{selected.external_port}
              </span>
              <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                {selected.slug}
              </code>
            </div>
            {selected.status === "error" && selected.error_message && (
              <div
                className="mt-3 rounded border border-destructive/50 bg-destructive/10 p-2 text-xs text-destructive"
                data-testid="monitor-error-message"
              >
                {selected.error_message}
              </div>
            )}
          </div>

          <div>
            <h2 className="mb-3 text-lg font-semibold">审计事件</h2>
            <AuditTable
              data={audit.data}
              isLoading={audit.isLoading}
              isError={audit.isError}
              error={audit.error}
              page={page}
              onPageChange={setPage}
              pageSize={PAGE_SIZE}
            />
          </div>
        </div>
      )}
    </div>
  );
}
