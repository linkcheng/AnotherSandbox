// CreateWizard 测试：步骤流转 + 非法 slug 拦截 + 提交成功
import { describe, expect, it, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import CreateWizard from "@/pages/CreateWizard";
import { resetWorkspaces } from "../msw/handlers";

function WorkspacesStub() {
  return <div data-testid="workspaces-stub">workspaces</div>;
}

function renderWizard() {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: {
            queries: { retry: false, refetchInterval: false, gcTime: 0 },
          },
        })
      }
    >
      <MemoryRouter initialEntries={["/create"]}>
        <Routes>
          <Route path="/create" element={<CreateWizard />} />
          <Route path="/workspaces" element={<WorkspacesStub />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("CreateWizard 向导", () => {
  beforeEach(() => resetWorkspaces());

  it("步骤 1 → 2 → 3 → 提交成功 → 跳 /workspaces", async () => {
    const user = userEvent.setup();
    renderWizard();
    expect(screen.getByTestId("wizard-step-template")).toBeInTheDocument();
    await user.click(screen.getByTestId("wizard-next"));

    expect(screen.getByTestId("wizard-step-slug")).toBeInTheDocument();
    await user.type(screen.getByTestId("slug-input"), "new-box");
    await user.click(screen.getByTestId("wizard-next"));

    expect(screen.getByTestId("wizard-step-confirm")).toBeInTheDocument();
    await user.click(screen.getByTestId("wizard-submit"));

    expect(await screen.findByTestId("workspaces-stub")).toBeInTheDocument();
  });

  it("非法 slug 时「下一步」禁用且展示错误", async () => {
    const user = userEvent.setup();
    renderWizard();
    await user.click(screen.getByTestId("wizard-next"));
    await user.type(screen.getByTestId("slug-input"), "AB!");
    expect(screen.getByTestId("slug-error")).toBeInTheDocument();
    expect(screen.getByTestId("wizard-next")).toBeDisabled();
  });

  it("保留词 slug 拒绝", async () => {
    const user = userEvent.setup();
    renderWizard();
    await user.click(screen.getByTestId("wizard-next"));
    await user.type(screen.getByTestId("slug-input"), "api");
    expect(screen.getByTestId("slug-error")).toBeInTheDocument();
  });

  it("合法 slug 显示「slug 可用」", async () => {
    const user = userEvent.setup();
    renderWizard();
    await user.click(screen.getByTestId("wizard-next"));
    await user.type(screen.getByTestId("slug-input"), "my-sandbox");
    expect(screen.getByTestId("slug-ok")).toBeInTheDocument();
    expect(screen.getByTestId("wizard-next")).not.toBeDisabled();
  });

  it("上一步可回退", async () => {
    const user = userEvent.setup();
    renderWizard();
    await user.click(screen.getByTestId("wizard-next"));
    expect(screen.getByTestId("wizard-step-slug")).toBeInTheDocument();
    await user.click(screen.getByTestId("wizard-prev"));
    expect(screen.getByTestId("wizard-step-template")).toBeInTheDocument();
  });
});
