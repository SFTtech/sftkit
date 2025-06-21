/* eslint-disable */
import { type Config } from "jest";

const config: Config = {
  displayName: "components",
  preset: "../../jest.preset.ts",
  transform: {
    "^.+\\.[tj]sx?$": [
      "@swc/jest",
      {
        jsc: {
          parser: { syntax: "typescript", tsx: true },
          transform: { react: { runtime: "automatic" } },
        },
      },
    ],
  },
  moduleFileExtensions: ["ts", "tsx", "js", "jsx"],
  coverageDirectory: "../../coverage/web/components",
};

export = config;
