// 纯函数测试：validateSlug / statusToVariant / canPerformAction
import { describe, expect, it } from "vitest";
import {
  canDelete,
  canOpen,
  canPerformAction,
  statusToVariant,
  validateSlug,
} from "@/lib/workspace";

describe("validateSlug", () => {
  it.each(["demo", "my-sandbox", "ws-001", "abc"])("合法 slug 通过：%s", (s) => {
    expect(validateSlug(s).ok).toBe(true);
  });

  it.each(["", "ab", "Abc", "demo!", "-demo", "demo-", "demo--box"])(
    "非法 slug 拒绝：%s",
    (s) => {
      expect(validateSlug(s).ok).toBe(false);
      expect(validateSlug(s).reason).toBeTruthy();
    },
  );

  it("超长 slug 拒绝", () => {
    expect(validateSlug("a".repeat(33)).ok).toBe(false);
  });

  it("保留词拒绝", () => {
    expect(validateSlug("api").ok).toBe(false);
    expect(validateSlug("create").ok).toBe(false);
  });
});

describe("statusToVariant", () => {
  it("running → success", () => {
    expect(statusToVariant("running")).toBe("success");
  });
  it("starting → warning", () => {
    expect(statusToVariant("starting")).toBe("warning");
  });
  it("error → destructive", () => {
    expect(statusToVariant("error")).toBe("destructive");
  });
  it("paused/stopped → secondary", () => {
    expect(statusToVariant("paused")).toBe("secondary");
    expect(statusToVariant("stopped")).toBe("secondary");
  });
});

describe("canPerformAction", () => {
  it("created 可启动，不可停止/暂停", () => {
    expect(canPerformAction("created", "start")).toBe(true);
    expect(canPerformAction("created", "stop")).toBe(false);
    expect(canPerformAction("created", "pause")).toBe(false);
  });
  it("running 可停止/暂停，不可再 start", () => {
    expect(canPerformAction("running", "stop")).toBe(true);
    expect(canPerformAction("running", "pause")).toBe(true);
    expect(canPerformAction("running", "start")).toBe(false);
  });
  it("paused 可 start/resume，不可 pause", () => {
    expect(canPerformAction("paused", "start")).toBe(true);
    expect(canPerformAction("paused", "resume")).toBe(true);
    expect(canPerformAction("paused", "pause")).toBe(false);
  });
  it("error/deleted 一切操作禁止", () => {
    expect(canPerformAction("error", "start")).toBe(false);
    expect(canPerformAction("deleted", "stop")).toBe(false);
  });
});

describe("canDelete / canOpen", () => {
  it("created/stopped/error 可删；running/paused/starting 不可", () => {
    expect(canDelete("created")).toBe(true);
    expect(canDelete("stopped")).toBe(true);
    expect(canDelete("error")).toBe(true);
    expect(canDelete("running")).toBe(false);
    expect(canDelete("starting")).toBe(false);
  });
  it("仅 running 可打开", () => {
    expect(canOpen("running")).toBe(true);
    expect(canOpen("paused")).toBe(false);
  });
});
