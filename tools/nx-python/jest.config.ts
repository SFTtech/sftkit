/* eslint-disable */
export default {
  displayName: "nx-python",
  preset: "../../jest.preset.ts",
  transform: {
    "^.+\\.[tj]s$": ["ts-jest", { tsconfig: "<rootDir>/tsconfig.spec.json" }],
  },
  moduleFileExtensions: ["ts", "js", "html"],
  coverageDirectory: "../../coverage/tools/nx-python",
};
