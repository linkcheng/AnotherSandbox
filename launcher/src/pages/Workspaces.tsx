// 工作区列表：useWorkspaces 5s 轮询 + 新建入口 + 空/错/loading 态 + 启停/删除
import { Link } from "react-router-dom";
import { Plus, AlertCircle, Inbox } from "lucide-react";
import { Button } from "@/components/ui/button";
import { WorkspaceCard } from "@/components/WorkspaceCard";
import { ApiError } from "@/api/client";
import {
  useDeleteWorkspace,
  useWorkspaces,
  useWorkspaceAction,
} from "@/api/workspaces";
import type { WorkspaceAction } from "@/types";

export default function Workspaces() {
  const list = useWorkspaces();
  const action = useWorkspaceAction();
  const del = useDeleteWorkspace();
  const busyId = action.isPending
    ? action.variables?.id
    : del.isPending
      ? del.variables
      : undefined;

  function onAction(id: string, a: WorkspaceAction) {
    action.mutate({ id, action: a });
  }
  function onDelete(id: string) {
    if (window.confirm("确认删除该工作区？此操作不可恢复。")) {
      del.mutate(id);
    }
  }

  return (
    <div className="container py-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">工作区</h1>
        <Button asChild>
          <Link to="/create" data-testid="goto-create">
            <Plus className="h-4 w-4" />
            新建工作区
          </Link>
        </Button>
      </div>

      {list.isLoading && (
        <div
          className="py-16 text-center text-muted-foreground"
          data-testid="ws-loading"
        >
          加载工作区…
        </div>
      )}

      {list.isError && (
        <div
          className="flex items-center gap-2 rounded-md border border-destructive/50 bg-destructive/10 p-4 text-destructive"
          data-testid="ws-error"
          role="alert"
        >
          <AlertCircle className="h-5 w-5" />
          <span>
            {list.error instanceof ApiError
              ? list.error.message
              : "加载工作区失败，请稍后重试。"}
          </span>
        </div>
      )}

      {!list.isLoading && !list.isError &&
        (list.data && list.data.length > 0 ? (
          <div
            className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
            data-testid="ws-grid"
          >
            {list.data.map((w) => (
              <WorkspaceCard
                key={w.id}
                workspace={w}
                onAction={onAction}
                onDelete={onDelete}
                busy={busyId === w.id}
              />
            ))}
          </div>
        ) : (
          <div
            className="flex flex-col items-center justify-center gap-3 py-20 text-muted-foreground"
            data-testid="ws-empty"
          >
            <Inbox className="h-10 w-10" />
            <p>还没有工作区，点击右上角「新建」开始。</p>
          </div>
        ))}
    </div>
  );
}
