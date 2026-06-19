// 审计事件 react-query hook：GET /audit?workspace=&limit=&offset=
// 10s 轮询（R7），分页（page/pageSize → offset），enabled 仅当 workspaceId 存在
// 来源：frontend-api-contract §3、research R7
import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { AuditEvent, Page } from "@/types";

const POLL_INTERVAL = 10000;
const DEFAULT_PAGE_SIZE = 20;

export interface UseAuditEventsOpts {
  page?: number; // 1-based
  pageSize?: number;
}

// useAuditEvents(workspaceId, { page, pageSize }) → Page<AuditEvent>
export function useAuditEvents(
  workspaceId: string | null | undefined,
  opts: UseAuditEventsOpts = {},
) {
  const page = Math.max(1, opts.page ?? 1);
  const pageSize = Math.max(1, opts.pageSize ?? DEFAULT_PAGE_SIZE);
  const offset = (page - 1) * pageSize;

  return useQuery<Page<AuditEvent>>({
    queryKey: ["audit", workspaceId, page],
    queryFn: () =>
      apiRequest<Page<AuditEvent>>("/audit", {
        query: {
          workspace: workspaceId as string,
          limit: pageSize,
          offset,
        },
      }),
    enabled: Boolean(workspaceId),
    refetchInterval: POLL_INTERVAL,
    refetchOnWindowFocus: true,
  });
}
