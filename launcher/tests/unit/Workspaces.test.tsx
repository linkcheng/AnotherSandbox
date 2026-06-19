// Workspaces 列表测试：msw 列表展示 + 启停 mutation + 乐观更新
import { describe, expect, it, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import Workspaces from "@/pages/Workspaces";
import { resetWorkspaces } from "../msw/handlers";

function newClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchInterval: false, gcTime: 0 },
    },
  });
}

function renderWorkspaces() {
  return render(
    <QueryClientProvider client={newClient()}>
      <MemoryRouter>
        <Workspaces />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Workspaces 列表", () => {
  beforeEach(() => resetWorkspaces());

  it("展示 mock 工作区卡片（name/slug/端口）", async () => {
    renderWorkspaces();
    expect(await screen.findByTestId("workspace-card-demo")).toBeInTheDocument();
    expect(screen.getByTestId("workspace-card-paused-box")).toBeInTheDocument();
    expect(screen.getByText(/端口：30001/)).toBeInTheDocument();
  });

  it("运行中工作区可停止（乐观：状态切 stopped）", async () => {
    const user = userEvent.setup();
    renderWorkspaces();
    await screen.findByTestId("workspace-card-demo");
    const stopBtn = await screen.findByTestId("ws-stop-demo");
    expect(stopBtn).not.toBeDisabled();
    await user.click(stopBtn);
    await waitFor(() => {
      expect(screen.getByTestId("workspace-card-demo")).toHaveTextContent(
        "已停止",
      );
    });
  });

  it("paused 工作区可启动（乐观 starting → mock 最终 running）", async () => {
    const user = userEvent.setup();
    renderWorkspaces();
    await screen.findByTestId("workspace-card-paused-box");
    const startBtn = await screen.findByTestId("ws-start-paused-box");
    expect(startBtn).not.toBeDisabled();
    await user.click(startBtn);
    await waitFor(() => {
      expect(screen.getByTestId("workspace-card-paused-box")).toHaveTextContent(
        "运行中",
      );
    });
  });

  it("running 工作区删除按钮禁用（不可删运行中）", async () => {
    renderWorkspaces();
    await screen.findByTestId("workspace-card-demo");
    expect(screen.getByTestId("ws-delete-demo")).toBeDisabled();
  });

  it("顶部有「新建工作区」入口", async () => {
    renderWorkspaces();
    await screen.findByTestId("workspace-card-demo");
    expect(screen.getByTestId("goto-create")).toBeInTheDocument();
  });
});
