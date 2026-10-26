import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import AuthGuard from "./AuthGuard";
import { authApi } from "../api/modules/auth";
import { setAuthToken } from "../api/request";

vi.mock("../api/config", () => ({
  DSM_NATIVE: true,
  getAppUrl: (path: string) => `/octop${path}`,
}));
vi.mock("../api/modules/auth", () => ({
  authApi: { getAuthStatus: vi.fn(), me: vi.fn(), getDsmSession: vi.fn() },
}));
vi.mock("../api/request", () => ({
  setAuthToken: vi.fn(),
  clearAuthToken: vi.fn(),
  getAuthToken: () => "dsm-bound-token",
}));
vi.mock("../utils/locale", () => ({
  applyUserLocale: vi.fn(() => Promise.resolve()),
}));

function mount() {
  return render(
    <MemoryRouter initialEntries={["/chat"]}>
      <Routes>
        <Route
          path="/chat"
          element={
            <AuthGuard>
              <div>protected-shell</div>
            </AuthGuard>
          }
        />
        <Route path="/login" element={<div>dsm-sign-in</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("DSM bootstrap", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    vi.mocked(authApi.getAuthStatus).mockResolvedValue({
      setup_required: false,
    } as never);
    vi.mocked(authApi.me).mockResolvedValue({
      id: 1,
      username: "alice",
      role: "admin",
    } as never);
  });

  it("uses the DSM session before rendering any protected content", async () => {
    vi.mocked(authApi.getDsmSession).mockResolvedValue({
      access_token: "dsm-bound-token",
      user_id: 1,
    });
    mount();
    expect(await screen.findByText("protected-shell")).toBeInTheDocument();
    expect(authApi.getDsmSession).toHaveBeenCalledOnce();
    expect(setAuthToken).toHaveBeenCalledWith("dsm-bound-token", false);
  });

  it("sends a rejected identity to DSM sign-in instead of showing an offline error", async () => {
    vi.mocked(authApi.getDsmSession).mockRejectedValue(new Error("forbidden"));
    mount();
    expect(await screen.findByText("dsm-sign-in")).toBeInTheDocument();
    expect(setAuthToken).not.toHaveBeenCalled();
    expect(authApi.me).not.toHaveBeenCalled();
  });

  it("does not install a late bootstrap response after unmount", async () => {
    let resolve!: (value: { access_token: string; user_id: number }) => void;
    vi.mocked(authApi.getDsmSession).mockReturnValue(
      new Promise((done) => {
        resolve = done;
      }),
    );
    const view = mount();
    view.unmount();
    await act(async () => {
      resolve({ access_token: "old-session", user_id: 1 });
    });
    expect(setAuthToken).not.toHaveBeenCalled();
    expect(authApi.getAuthStatus).not.toHaveBeenCalled();
  });
});
