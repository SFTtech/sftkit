import { defineConfig } from "eslint/config";

export default defineConfig([
  {
    extends: ["../../.eslintrc.json"],
    ignorePatterns: ["!**/*"],
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
      {
        files: ["*.json"],
        parser: "jsonc-eslint-parser",
        rules: {
          "@nx/dependency-checks": "error",
        },
      },
      {
        files: ["./package.json", "./executors.json", "./generators.json"],
        parser: "jsonc-eslint-parser",
        rules: {
          "@nx/nx-plugin-checks": "error",
        },
      },
    ],
  },
]);
