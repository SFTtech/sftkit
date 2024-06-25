import { CreateNodesResult, CreateNodesV2, ProjectConfiguration } from "@nx/devkit";
import { dirname, join } from "path";
import { loadPyprojectToml } from "./utils/pyproject-toml";
import * as fs from "node:fs";

export const createNodes: CreateNodesV2 = [
  "*/**/pyproject.toml",
  async (projectFiles) => {
    const results: Array<[file: string, result: CreateNodesResult]> = [];

    await Promise.all(
      projectFiles.map((projectFile) => {
        const root = dirname(projectFile);
        const pyproject = loadPyprojectToml(projectFile);

        const pythonPackage = {
          name: pyproject.project!.name!,
          pyprojectToml: pyproject,
          projectRoot: dirname(projectFile),
        };

        if (!fs.existsSync(join(pythonPackage.projectRoot, "project.json"))) {
          return {};
        }

        const projects: Record<string, ProjectConfiguration> = {};
        projects[root] = {
          root,
          name: pythonPackage.name,
          targets: {
            "nx-release-publish": {
              dependsOn: ["^nx-release-publish"],
              executor: "@sftkit/nx-python:release-publish",
              options: {},
            },
          },
          release: {
            version: {
              generator: "@sftkit/nx-python:release-version",
            },
          },
        };

        results.push([projectFile, { projects }]);
      })
    );
    return results;
  },
];
