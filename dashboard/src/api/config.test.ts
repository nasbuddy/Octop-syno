import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe("DSM application base", () => {
  it("keeps HTTP, WebSocket and public assets on the DSM path", async () => {
    vi.stubEnv("BASE_URL", "/octop/");
    vi.stubEnv("VITE_DSM_AUTH", "1");
    vi.stubGlobal("BASE_URL", "");
    const { DSM_NATIVE, getApiUrl, getWsUrl, getAppUrl } = await import(
      "./config"
    );
    expect(DSM_NATIVE).toBe(true);
    expect(getApiUrl("/auth/me")).toBe("/octop/api/auth/me");
    expect(getWsUrl("/agents/a/chat/ws")).toBe(
      `ws://${window.location.host}/octop/api/agents/a/chat/ws`,
    );
    expect(getAppUrl("/experts/avatars/a.svg")).toBe(
      "/octop/experts/avatars/a.svg",
    );
    expect(getAppUrl("/octop/chat")).toBe("/octop/chat");
    expect(getAppUrl("https://example.com/image.png")).toBe(
      "https://example.com/image.png",
    );
    const { OCTOP_EMPTY_MASCOT_SRC } = await import("../assets/mascot");
    expect(OCTOP_EMPTY_MASCOT_SRC).toBe("/octop/octop-mascot-empty.png");
  });

  it("preserves regular deployments and explicit API origins", async () => {
    vi.stubEnv("BASE_URL", "/");
    vi.stubEnv("VITE_DSM_AUTH", "");
    vi.stubGlobal("BASE_URL", "https://api.example.com");
    const { DSM_NATIVE, getApiUrl, getWsUrl, getAppUrl } = await import(
      "./config"
    );
    expect(DSM_NATIVE).toBe(false);
    expect(getAppUrl("/chat")).toBe("/chat");
    const { OCTOP_EMPTY_MASCOT_SRC } = await import("../assets/mascot");
    expect(OCTOP_EMPTY_MASCOT_SRC).toBe("/octop-mascot-empty.png");
    expect(getApiUrl("/auth/me")).toBe("https://api.example.com/api/auth/me");
    expect(getWsUrl("/notifications/ws")).toBe(
      "wss://api.example.com/api/notifications/ws",
    );
  });
});
