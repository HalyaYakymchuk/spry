import { beforeEach, describe, expect, it } from "vitest";

import {
  getIdToken,
  isAuthConfigured,
  MOCK_TOKEN,
  MOCK_USER,
  signOut,
  useSession,
} from "@/lib/auth";

describe("auth", () => {
  const originalEnv = process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID;

  beforeEach(() => {
    localStorage.clear();
    process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID = originalEnv;
  });

  describe("when Cognito is configured", () => {
    it("reports auth as configured", () => {
      process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID = "test-client-id";
      expect(isAuthConfigured()).toBe(true);
    });

    it("returns stored token if present", async () => {
      process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID = "test-client-id";
      localStorage.setItem("peach_id_token", "real-user-token");
      await expect(getIdToken()).resolves.toBe("real-user-token");
    });

    it("returns null if not signed in", async () => {
      process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID = "test-client-id";
      await expect(getIdToken()).resolves.toBeNull();
    });

    it("returns null session if not signed in", () => {
      process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID = "test-client-id";
      expect(useSession()).toBeNull();
    });
  });

  describe("when Cognito is not configured", () => {
    it("reports auth as not configured", () => {
      delete process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID;
      expect(isAuthConfigured()).toBe(false);
    });

    it("falls back to mock token when no token in storage", async () => {
      delete process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID;
      await expect(getIdToken()).resolves.toBe(MOCK_TOKEN);
    });

    it("falls back to mock user session", () => {
      delete process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID;
      expect(useSession()).toEqual(MOCK_USER);
    });
  });

  describe("signOut", () => {
    it("clears stored token and user", () => {
      localStorage.setItem("peach_id_token", "token-to-clear");
      localStorage.setItem("peach_user", JSON.stringify(MOCK_USER));
      signOut();
      expect(localStorage.getItem("peach_id_token")).toBeNull();
      expect(localStorage.getItem("peach_user")).toBeNull();
    });
  });
});
