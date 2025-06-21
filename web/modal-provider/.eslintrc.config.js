import { defineConfig } from "eslint/config";

export default defineConfig([
  {
    extends: ["plugin:@nx/react", "../../.eslintrc.json"],
    ignorePatterns: ["!**/*", "**/vite.config.*.timestamp*", "**/vitest.config.*.timestamp*"],
    overrides: [
      {
        files: ["*.ts", "*.tsx", "*.js", "*.jsx"],
        rules: {},
      },
      {
        files: ["*.ts", "*.tsx"],
        rules: {},
      },
      {
        files: ["*.js", "*.jsx"],
        rules: {},
      },
    ],
  },
]);
