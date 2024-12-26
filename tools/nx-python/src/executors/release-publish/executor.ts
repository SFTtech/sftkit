import { ExecutorContext, joinPathFragments, output } from "@nx/devkit";
import { execSync } from "node:child_process";
import { ReleaseExecutorSchema } from "./schema";

const LARGE_BUFFER = 1024 * 1000000;

export default async function runExecutor(options: ReleaseExecutorSchema, context: ExecutorContext) {
  /**
   * We need to check both the env var and the option because the executor may have been triggered
   * indirectly via dependsOn, in which case the env var will be set, but the option will not.
   */
  const isDryRun = process.env.NX_DRY_RUN === "true" || options.dryRun || false;

  if (!context.projectName) {
    throw new Error("project name is empty");
  }

  const projectConfig = context.projectsConfigurations?.projects[context.projectName];

  if (!projectConfig) {
    throw new Error("could not find a project config");
  }

  const packageRoot = joinPathFragments(context.root, options.packageRoot ?? projectConfig.root);

  const command = "pdm publish";

  try {
    output.logSingleLine(`Running "${command}"...`);

    if (isDryRun) {
      output.logSingleLine("Would publish to https://pypi.org, but '[dry-run]' was set");
    } else {
      execSync(command, {
        maxBuffer: LARGE_BUFFER,
        cwd: packageRoot,
        stdio: "inherit",
      });

      output.logSingleLine("Published to https://pypi.org");
    }

    return {
      success: true,
    };
  } catch (err) {
    output.logSingleLine(`Error running pdm publish: ${err}`);
    return {
      success: false,
    };
  }
}
