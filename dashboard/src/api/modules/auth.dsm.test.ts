import { afterEach, describe, expect, it, vi } from "vitest";
import { authApi } from "./auth";
import { request } from "../request";

vi.mock("../request", () => ({ request: vi.fn() }));

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

describe("DSM session handshake", () => {
  it("passes the current DSM CSRF token only in the bootstrap header", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response(
          JSON.stringify({ success: true, SynoToken: "synthetic-csrf" }),
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    const session = { access_token: "octop-session", user_id: 7 };
    vi.mocked(request).mockResolvedValue(session);
    expect(await authApi.getDsmSession()).toEqual(session);
    expect(fetchMock).toHaveBeenCalledWith("/webman/login.cgi", {
      credentials: "same-origin",
      cache: "no-store",
      redirect: "error",
    });
    expect(request).toHaveBeenCalledWith("/auth/dsm/session", {
      cache: "no-store",
      headers: { "X-Syno-Token": "synthetic-csrf" },
    });
  });

  it.each([
    { success: false, SynoToken: "synthetic-csrf" },
    { success: true },
    { success: true, SynoToken: "" },
  ])("rejects invalid DSM login responses", async (body) => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify(body))),
    );
    await expect(authApi.getDsmSession()).rejects.toThrow(
      "DSM session is unavailable",
    );
    expect(request).not.toHaveBeenCalled();
  });
});
