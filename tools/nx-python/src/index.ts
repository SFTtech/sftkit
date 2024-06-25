import { NxPlugin } from "@nx/devkit";
import { createNodes } from "./graph";

const nxPlugin: NxPlugin = {
  name: "@sftkit/nx-python",
  createNodesV2: createNodes,
};

export = nxPlugin;
