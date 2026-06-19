// 会话 hook：react-query 包装 GET /me
// 失败（401/网络错误）= 未登录，不抛错只置 isLoading=false + user=undefined
import { useQuery } from "@tanstack/react-query";
import { fetchMe, logout as doLogout } from "@/api/auth";

export const ME_QUERY_KEY = ["me"] as const;

export function useCurrentUser() {
  const query = useQuery({
    queryKey: ME_QUERY_KEY,
    queryFn: fetchMe,
    retry: false,
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });

  return {
    user: query.data,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
    // 是否已确认为未登录（请求结束且无 user）
    isUnauthenticated: !query.isLoading && !query.data,
  };
}

export function useLogout() {
  return () => doLogout();
}
