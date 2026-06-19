// msw handlers：mock orchestrator REST API（/api/v1/...）
import { http, HttpResponse, delay } from "msw";
import type {
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
];
