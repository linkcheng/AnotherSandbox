// 路由根：受保护路由（useCurrentUser 未登录→/login）+ 顶部栏 + OAuth 回流 error 处理
import { type ReactNode, Suspense, lazy } from "react";
import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useCurrentUser, useLogout } from "@/hooks/useSession";

// 路由懒加载（按需分块）
const Login = lazy(() => import("@/pages/Login"));
const Workspaces = lazy(() => import("@/pages/Workspaces"));
const CreateWizard = lazy(() => import("@/pages/CreateWizard"));

function FullScreenLoader() {
  return (
    <div className="flex min-h-screen items-center justify-center text-muted-foreground">
      加载中…
    </div>
  );
}

// 受保护路由包装
function RequireAuth({ children }: { children: ReactNode }) {
  const { user, isLoading } = useCurrentUser();
  const location = useLocation();

  if (isLoading) return <FullScreenLoader />;
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}

// 顶部栏：display_name/email + 登出
function TopBar() {
  const { user } = useCurrentUser();
  const logout = useLogout();

  return (
    <header className="flex h-14 items-center justify-between border-b bg-card px-6">
      <div className="flex items-center gap-6">
        <Link to="/workspaces" className="text-lg font-semibold">
          MySandbox
        </Link>
        <nav className="flex items-center gap-4 text-sm text-muted-foreground">
          <Link to="/workspaces" className="hover:text-foreground">
            工作区
          </Link>
          <Link to="/create" className="hover:text-foreground">
            新建
          </Link>
        </nav>
      </div>
      <div className="flex items-center gap-3 text-sm">
        <span className="text-muted-foreground" data-testid="user-display">
          {user?.display_name ?? user?.email ?? "用户"}
        </span>
        <Button variant="ghost" size="sm" onClick={logout} data-testid="logout">
          登出
        </Button>
      </div>
    </header>
  );
}

function ProtectedLayout({ children }: { children: ReactNode }) {
  return (
    <RequireAuth>
      <div className="flex min-h-screen flex-col">
        <TopBar />
        <main className="flex-1">{children}</main>
      </div>
    </RequireAuth>
  );
}

export default function App() {
  return (
    <Suspense fallback={<FullScreenLoader />}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <ProtectedLayout>
              <Navigate to="/workspaces" replace />
            </ProtectedLayout>
          }
        />
        <Route
          path="/workspaces"
          element={
            <ProtectedLayout>
              <Workspaces />
            </ProtectedLayout>
          }
        />
        <Route
          path="/create"
          element={
            <ProtectedLayout>
              <CreateWizard />
            </ProtectedLayout>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
