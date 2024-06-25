import { ExecutorContext, joinPathFragments, output } from "@nx/devkit";
import { execSync } from "node:child_process";
import { ReleaseExecutorSchema } from "./schema";
import chalk from "chalk";

const LARGE_BUFFER = 1024 * 1000000;


export default async function runExecutor(
  options: ReleaseExecutorSchema,
  context: ExecutorContext,
) {
  /**
   * We need to check both the env var and the option because the executor may have been triggered
   * indirectly via dependsOn, in which case the env var will be set, but the option will not.
   */
  const isDryRun = process.env.NX_DRY_RUN === "true" || options.dryRun || false;

  const projectConfig =
    context.projectsConfigurations!.projects[context.projectName!]!;

  const packageRoot = joinPathFragments(
    context.root,
    options.packageRoot ?? projectConfig.root,
  );

  const pdmPublishCommandSegments = [
    `pdm publish`,
  ];

  try {
    const command = pdmPublishCommandSegments.join(" ");
    output.logSingleLine(`Running "${command}"...`);

    if (isDryRun) {
      console.log(`Would publish to https://pypi.org, but ${chalk.red("'[dry-run]'")}'[dry-run]' was set`);
    } else {

      execSync(command, {
        maxBuffer: LARGE_BUFFER,
        cwd: packageRoot,
        stdio: "inherit",
      });

      console.log("");
      console.log(`Published to https://pypi.org`);
    }

    return {
      success: true,
    };
  } catch (err: any) {
    return {
      success: false,
    };
  }
}