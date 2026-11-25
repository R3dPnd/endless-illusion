import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["test/**/*.test.mjs", "src/**/*.test.ts"],
    environment: "node",
    testTimeout: 20000,
  },
});
