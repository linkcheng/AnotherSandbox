// msw handlers：mock orchestrator REST API（/api/v1/...）
import { http, HttpResponse, delay } from "msw";
import type {
  AuditEvent,
  Page,
  User,
  Workspace,
} from "@/types";

// 合成测试数据（非生产数据）
export const mockUser: User = {
  id: "u_1",
  email: "alice@example.com",
  display_name: "Alice",
  avatar_url: null,
};

export const mockWorkspaces: Workspace[] = [
  {
    id: "ws_1",
    name: "demo",
    slug: "demo",
    status: "running",
    external_port: 30001,
    role: "owner",
    created_at: "2026-06-20T04:00:00Z",
    last_active_at: "2026-06-20T05:00:00Z",
    error_message: null,
  },
  {
    id: "ws_2",
    name: "paused-box",
    slug: "paused-box",
    status: "paused",
    external_port: 30002,
    role: "owner",
    created_at: "2026-06-19T10:00:00Z",
    last_active_at: null,
    error_message: null,
  },
];

// 合成审计事件样例（覆盖 4 类 AuditType，时间倒序）
export const mockAuditEvents: AuditEvent[] = [
  {
    id: "ev_1",
    workspace_id: "ws_1",
    type: "shell.exec",
    actor_user_id: "u_1",
    created_at: "2026-06-20T05:30:00Z",
    summary: "ls -la /workspace",
  },
  {
    id: "ev_2",
    workspace_id: "ws_1",
    type: "fs.write",
    actor_user_id: "u_1",
    created_at: "2026-06-20T05:20:00Z",
    summary: "写入 /workspace/main.py (256B)",
  },
  {
    id: "ev_3",
    workspace_id: "ws_1",
    type: "browser.action",
    actor_user_id: "u_1",
    created_at: "2026-06-20T05:10:00Z",
    summary: "navigate https://example.com",
  },
  {
    id: "ev_4",
    workspace_id: "ws_1",
    type: "gui.action",
    actor_user_id: null,
    created_at: "2026-06-20T05:00:00Z",
    summary: "点击「运行」按钮",
  },
];

// 当前内存态（测试可 mutate 后断言乐观更新）
let workspaces: Workspace[] = [...mockWorkspaces];
export function resetWorkspaces() {
  workspaces = [...mockWorkspaces];
}

export const handlers = [
  // GET /me
  http.get("/api/v1/me", () => HttpResponse.json(mockUser)),

  // POST /auth/login（成功）
  http.post("/api/v1/auth/login", async ({ request }) => {
    const body = (await request.json()) as { email?: string; password?: string };
    if (!body.email || !body.password) {
      return HttpResponse.json(
        { error: { code: "invalid_credentials", message: "邮箱或密码错误" } },
        { status: 401 },
      );
    }
    return HttpResponse.json(mockUser);
  }),

  // POST /auth/register
  http.post("/api/v1/auth/register", async () => HttpResponse.json(mockUser)),

  // GET /workspaces
  http.get("/api/v1/workspaces", () => HttpResponse.json(workspaces)),

  // POST /workspaces
  http.post("/api/v1/workspaces", async ({ request }) => {
    const body = (await request.json()) as { name: string; slug: string };
    const created: Workspace = {
      id: `ws_${Date.now()}`,
      name: body.name,
      slug: body.slug,
      status: "created",
      external_port: 30999,
      role: "owner",
      created_at: "2026-06-20T06:00:00Z",
      last_active_at: null,
      error_message: null,
    };
    workspaces = [...workspaces, created];
    return HttpResponse.json(created, { status: 201 });
  }),

  // POST /workspaces/:id/:action（start/stop/pause/resume）
  http.post("/api/v1/workspaces/:id/:action", async ({ params }) => {
    const id = params.id as string;
    const action = params.action as string;
    await delay(10);
    const statusAfter: Record<string, Workspace["status"]> = {
      start: "running",
      stop: "stopped",
      pause: "paused",
      resume: "running",
    };
    workspaces = workspaces.map((w) =>
      w.id === id ? { ...w, status: statusAfter[action] ?? w.status } : w,
    );
    const found = workspaces.find((w) => w.id === id);
    return HttpResponse.json(found);
  }),

  // DELETE /workspaces/:id
  http.delete("/api/v1/workspaces/:id", ({ params }) => {
    const id = params.id as string;
    workspaces = workspaces.filter((w) => w.id !== id);
    return new HttpResponse(null, { status: 204 });
  }),

  // GET /auth/oauth/accounts
  http.get("/api/v1/auth/oauth/accounts", () =>
    HttpResponse.json({ accounts: [] }),
  ),

  // GET /audit?workspace=&limit=&offset= — 分页 Page<AuditEvent>
  http.get("/api/v1/audit", ({ request }) => {
    const url = new URL(request.url);
    const wsId = url.searchParams.get("workspace") ?? "";
    const limit = Number(url.searchParams.get("limit") ?? "20");
    const offset = Number(url.searchParams.get("offset") ?? "0");
    // ws_1 有 4 条样例；其它 workspace 返回空（验证空态）
    const all = wsId === "ws_1" ? mockAuditEvents : [];
    const items = all.slice(offset, offset + limit);
    const page: Page<AuditEvent> = {
      items,
      total: all.length,
      limit,
      offset,
    };
    return HttpResponse.json(page);
  }),
];
