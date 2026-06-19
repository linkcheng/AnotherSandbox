// Monitor 监控页测试：workspace 选择 + 审计列表（4 类 type 徽标）+ 分页 + 空态
// msw mock：/workspaces（ws_1/ws_2）、/audit（ws_1 4 条、ws_2 空）
import { describe, expect, it, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import Monitor from "@/pages/Monitor";
import { resetWorkspaces } from "../msw/handlers";

function newClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchInterval: false, gcTime: 0 },
    },
  });
}

function renderMonitor() {
  return render(
    <QueryClientProvider client={newClient()}>
      <MemoryRouter>
        <Monitor />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Monitor 监控页", () => {
  beforeEach(() => resetWorkspaces());

  it("未选 workspace 时提示选择", async () => {
    renderMonitor();
    await waitFor(() => {
      expect(screen.getByTestId("monitor-empty")).toBeInTheDocument();
    });
  });

  it("选择 workspace 后展示审计列表（4 类 type 徽标）", async () => {
    const user = userEvent.setup();
    renderMonitor();
    // 等 workspace 选项加载（option 出现）
    const select = await screen.findByTestId("workspace-select");
    await screen.findByText("demo（demo）");
    await user.selectOptions(select, "ws_1");

    expect(await screen.findByTestId("audit-type-shell.exec")).toBeInTheDocument();
    expect(screen.getByTestId("audit-type-fs.write")).toBeInTheDocument();
    expect(screen.getByTestId("audit-type-browser.action")).toBeInTheDocument();
    expect(screen.getByTestId("audit-type-gui.action")).toBeInTheDocument();

    expect(screen.getByTestId("audit-total")).toHaveTextContent("共 4 条");
    expect(screen.getByText("ls -la /workspace")).toBeInTheDocument();
  });

  it("分页控件存在（上一页禁用 / 总数展示）", async () => {
    const user = userEvent.setup();
    renderMonitor();
    const select = await screen.findByTestId("workspace-select");
    await screen.findByText("demo（demo）");
    await user.selectOptions(select, "ws_1");

    const first = await screen.findByTestId("audit-prev");
    const next = screen.getByTestId("audit-next");
    // 仅 4 条 ≤ pageSize 20，无下一页 → 双向禁用
    expect(first).toBeDisabled();
    expect(next).toBeDisabled();
  });

  it("空态：选择无审计事件的 workspace", async () => {
    const user = userEvent.setup();
    renderMonitor();
    const select = await screen.findByTestId("workspace-select");
    await screen.findByText("paused-box（paused-box）");
    await user.selectOptions(select, "ws_2");

    expect(await screen.findByTestId("audit-empty")).toBeInTheDocument();
  });

  it("选中 workspace 时展示状态卡（端口/状态徽标）", async () => {
    const user = userEvent.setup();
    renderMonitor();
    const select = await screen.findByTestId("workspace-select");
    await screen.findByText("demo（demo）");
    await user.selectOptions(select, "ws_1");

    const card = await screen.findByTestId("monitor-status-card");
    expect(within(card).getByText(/端口：30001/)).toBeInTheDocument();
    expect(within(card).getByText("运行中")).toBeInTheDocument();
  });
});
