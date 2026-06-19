// Login 页测试：本地登录成功 / OAuth 按钮 href / ?error 展示
import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import Login from "@/pages/Login";
import { resetWorkspaces } from "../msw/handlers";

// 用于断言成功后跳转到的占位页
function WorkspacesStub() {
  return <div data-testid="workspaces-stub">workspaces</div>;
}

function renderAt(path: string, initial = path) {
  return render(
    <MemoryRouter initialEntries={[initial]}>
      <Routes>
        <Route path={path} element={<Login />} />
        <Route path="/workspaces" element={<WorkspacesStub />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("Login 页", () => {
  beforeEach(() => {
    resetWorkspaces();
  });

  it("渲染邮箱/密码表单与 OAuth 按钮", () => {
    renderAt("/login");
    expect(screen.getByTestId("email-input")).toBeInTheDocument();
    expect(screen.getByTestId("password-input")).toBeInTheDocument();
    expect(screen.getByTestId("login-submit")).toBeInTheDocument();
  });

  it("OAuth 按钮 href 指向后端 OAuth 入口", () => {
    renderAt("/login");
    const gh = screen.getByTestId("oauth-github");
    const gg = screen.getByTestId("oauth-google");
    expect(gh).toHaveAttribute(
      "href",
      "/api/v1/auth/oauth/github/login?redirect=%2Fworkspaces",
    );
    expect(gg).toHaveAttribute(
      "href",
      "/api/v1/auth/oauth/google/login?redirect=%2Fworkspaces",
    );
  });

  it("本地登录成功后跳转 /workspaces", async () => {
    const user = userEvent.setup();
    renderAt("/login");
    await user.type(screen.getByTestId("email-input"), "alice@example.com");
    await user.type(screen.getByTestId("password-input"), "secret123");
    await user.click(screen.getByTestId("login-submit"));
    expect(await screen.findByTestId("workspaces-stub")).toBeInTheDocument();
  });

  it("?error=oauth_failed 展示错误提示", () => {
    renderAt("/login", "/login?error=oauth_failed");
    expect(screen.getByTestId("oauth-error")).toHaveTextContent(
      "第三方登录失败",
    );
  });

  it("?error=oauth_unreachable 展示服务不可达提示", () => {
    renderAt("/login", "/login?error=oauth_unreachable");
    expect(screen.getByTestId("oauth-error")).toHaveTextContent(
      "登录服务暂不可达",
    );
  });

  it("空字段提交被浏览器原生 required 拦截（不触发请求）", async () => {
    const user = userEvent.setup();
    renderAt("/login");
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    await user.click(screen.getByTestId("login-submit"));
    expect(screen.getByTestId("login-submit")).toBeInTheDocument();
    spy.mockRestore();
  });
});
