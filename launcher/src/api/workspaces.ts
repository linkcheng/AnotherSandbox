// workspace react-query hooks：列表（5s 轮询）/ 详情 / 创建 / 操作 / 删除
// mutation 后 invalidate 相关 query（不可变缓存更新）
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type {
  CreateWorkspacePayload,
  Page,
  Workspace,
  WorkspaceAction,
} from "@/types";

export const WORKSPACES_KEY = ["workspaces"] as const;
const POLL_INTERVAL = 5000;

// GET /api/v1/workspaces — 列表 5s 轮询
export function useWorkspaces() {
  return useQuery<Workspace[]>({
    queryKey: WORKSPACES_KEY,
    queryFn: () => apiRequest<Workspace[]>("/workspaces"),
    refetchInterval: POLL_INTERVAL,
    refetchOnWindowFocus: true,
  });
}

// GET /api/v1/workspaces/{id} — 详情 5s 轮询
export function useWorkspace(id: string | null | undefined) {
  return useQuery<Workspace>({
    queryKey: ["workspace", id],
    queryFn: () => apiRequest<Workspace>(`/workspaces/${id}`),
    enabled: Boolean(id),
    refetchInterval: POLL_INTERVAL,
  });
}

// POST /api/v1/workspaces — 创建
export function useCreateWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateWorkspacePayload) =>
      apiRequest<Workspace>("/workspaces", { method: "POST", body: payload }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: WORKSPACES_KEY });
    },
  });
}

// POST /api/v1/workspaces/{id}/{action} — start/stop/pause/resume
export function useWorkspaceAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      action,
    }: {
      id: string;
      action: WorkspaceAction;
    }) =>
      apiRequest<Workspace>(`/workspaces/${id}/${action}`, {
        method: "POST",
      }),
    // 乐观更新：先就地改状态，失败回滚
    onMutate: async ({ id, action }) => {
      await qc.cancelQueries({ queryKey: WORKSPACES_KEY });
      const prev = qc.getQueryData<Workspace[]>(WORKSPACES_KEY);
      const nextStatus = actionToOptimisticStatus(action);
      if (prev && nextStatus) {
        qc.setQueryData<Workspace[]>(
          WORKSPACES_KEY,
          prev.map((w) => (w.id === id ? { ...w, status: nextStatus } : w)),
        );
      }
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) qc.setQueryData(WORKSPACES_KEY, ctx.prev);
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: WORKSPACES_KEY });
    },
  });
}

// DELETE /api/v1/workspaces/{id}
export function useDeleteWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiRequest<void>(`/workspaces/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: WORKSPACES_KEY });
    },
  });
}

// 操作 → 乐观状态映射
function actionToOptimisticStatus(
  action: WorkspaceAction,
): Workspace["status"] | null {
  switch (action) {
    case "start":
      return "starting";
    case "stop":
      return "stopped";
    case "pause":
      return "paused";
    case "resume":
      return "starting";
    default:
      return null;
  }
}

export type WorkspacesPage = Page<Workspace>;
