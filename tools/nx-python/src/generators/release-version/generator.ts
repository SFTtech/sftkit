/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable @typescript-eslint/no-non-null-assertion */
import {
  formatFiles,
  joinPathFragments,
  output,
  ProjectGraph,
  ProjectGraphDependency,
  ProjectGraphProjectNode,
  Tree,
  workspaceRoot,
} from "@nx/devkit";
import { relative } from "node:path";
import { IMPLICIT_DEFAULT_RELEASE_GROUP } from "nx/src/command-line/release/config/config";
import { getFirstGitCommit, getLatestGitTagForPattern } from "nx/src/command-line/release/utils/git";
import {
  resolveSemverSpecifierFromConventionalCommits,
  resolveSemverSpecifierFromPrompt,
} from "nx/src/command-line/release/utils/resolve-semver-specifier";
import { deriveNewSemverVersion, isValidSemverSpecifier } from "nx/src/command-line/release/utils/semver";
import { validReleaseVersionPrefixes } from "nx/src/command-line/release/version";
import { interpolate } from "nx/src/tasks-runner/utils";
import { prerelease } from "semver";
import {
  parsePyprojectToml,
  loadPyprojectTomlWithTree,
  stringifyPyprojectToml,
  PyprojectToml,
} from "../../utils/pyproject-toml";
import { ReleaseVersionGeneratorSchema } from "./schema";
import { ReleaseVersionGeneratorResult, VersionData } from "nx/src/command-line/release/version-legacy";

export async function releaseVersionGenerator(
  tree: Tree,
  options: ReleaseVersionGeneratorSchema
): Promise<ReleaseVersionGeneratorResult> {
  try {
    const versionData: VersionData = {};

    // If the user provided a specifier, validate that it is valid semver or a relative semver keyword
    if (options.specifier) {
      if (!isValidSemverSpecifier(options.specifier)) {
        throw new Error(
          `The given version specifier "${options.specifier}" is not valid. You provide an exact version or a valid semver keyword such as "major", "minor", "patch", etc.`
        );
      }
      // The node semver library classes a leading `v` as valid, but we want to ensure it is not present in the final version
      options.specifier = options.specifier.replace(/^v/, "");
    }

    if (options.versionPrefix && validReleaseVersionPrefixes.indexOf(options.versionPrefix) === -1) {
      throw new Error(
        `Invalid value for version.generatorOptions.versionPrefix: "${options.versionPrefix}"

Valid values are: ${validReleaseVersionPrefixes.map((s) => `"${s}"`).join(", ")}`
      );
    }

    if (options.firstRelease) {
      // always use disk as a fallback for the first release
      options.fallbackCurrentVersionResolver = "disk";
    }

    const projects = options.projects;

    const resolvePackageRoot = createResolvePackageRoot(options.packageRoot);

    // Resolve any custom package roots for each project upfront as they will need to be reused during dependency resolution
    const projectNameToPackageRootMap = new Map<string, string>();
    for (const project of projects) {
      projectNameToPackageRootMap.set(project.name, resolvePackageRoot(project));
    }

    let currentVersion: string | undefined = undefined;
    let currentVersionResolvedFromFallback = false;

    // only used for options.currentVersionResolver === 'git-tag', but
    // must be declared here in order to reuse it for additional projects
    let latestMatchingGitTag: { tag: string; extractedVersion: string } | null | undefined = undefined;

    // if specifier is undefined, then we haven't resolved it yet
    // if specifier is null, then it has been resolved and no changes are necessary
    let specifier: string | null | undefined = options.specifier ? options.specifier : undefined;

    for (const project of projects) {
      const projectName = project.name;
      const packageRoot = projectNameToPackageRootMap.get(projectName);
      if (!packageRoot) {
        throw new Error(
          `The project "${projectName}" does not have a packageRoot available. Please report this issue on https://github.com/nrwl/nx`
        );
      }

      const pyprojectTomlPath = joinPathFragments(packageRoot, "pyproject.toml");
      const workspaceRelativePyprojectTomlPath = relative(workspaceRoot, pyprojectTomlPath);

      const log = (msg: string) => {
        console.log(projectName + " " + msg);
      };

      if (!tree.exists(pyprojectTomlPath)) {
        throw new Error(
          `The project "${projectName}" does not have a pyproject.toml available at ${workspaceRelativePyprojectTomlPath}.

To fix this you will either need to add a pyproject.toml file at that location, or configure "release" within your nx.json to exclude "${projectName}" from the current release group, or amend the packageRoot configuration to point to where the pyproject.toml should be.`
        );
      }

      output.logSingleLine(`Running release version for project: ${project.name}`);

      const pyprojectTomlContents = tree.read(pyprojectTomlPath)!.toString("utf-8");
      const data: PyprojectToml = parsePyprojectToml(pyprojectTomlContents);
      const pkg = data.project;

      log(`🔍 Reading data for python package "${pkg!.name}" from ${workspaceRelativePyprojectTomlPath}`);

      const packageName = pkg!.name;
      const currentVersionFromDisk = pkg!.version;

      switch (options.currentVersionResolver) {
        case "disk":
          currentVersion = currentVersionFromDisk;
          log(`📄 Resolved the current version as ${currentVersion} from ${pyprojectTomlPath}`);
          break;
        case "git-tag": {
          if (
            !currentVersion ||
            // We always need to independently resolve the current version from git tag per project if the projects are independent
            options.releaseGroup.projectsRelationship === "independent"
          ) {
            const releaseTagPattern = options.releaseGroup.releaseTagPattern;
            latestMatchingGitTag = await getLatestGitTagForPattern(releaseTagPattern, {
              projectName: project.name,
            });
            if (!latestMatchingGitTag) {
              if (options.fallbackCurrentVersionResolver === "disk") {
                log(
                  `📄 Unable to resolve the current version from git tag using pattern "${releaseTagPattern}". Falling back to the version on disk of ${currentVersionFromDisk}`
                );
                currentVersion = currentVersionFromDisk;
                currentVersionResolvedFromFallback = true;
              } else {
                throw new Error(
                  `No git tags matching pattern "${releaseTagPattern}" for project "${project.name}" were found. You will need to create an initial matching tag to use as a base for determining the next version. Alternatively, you can use the --first-release option or set "release.version.generatorOptions.fallbackCurrentVersionResolver" to "disk" in order to fallback to the version on disk when no matching git tags are found.`
                );
              }
            } else {
              currentVersion = latestMatchingGitTag.extractedVersion;
              log(`📄 Resolved the current version as ${currentVersion} from git tag "${latestMatchingGitTag.tag}".`);
            }
          } else {
            if (currentVersionResolvedFromFallback) {
              log(`📄 Using the current version ${currentVersion} already resolved from disk fallback.`);
            } else {
              log(
                // In this code path we know that latestMatchingGitTag is defined, because we are not relying on the fallbackCurrentVersionResolver, so we can safely use the non-null assertion operator
                `📄 Using the current version ${currentVersion} already resolved from git tag "${
                  latestMatchingGitTag!.tag
                }".`
              );
            }
          }
          break;
        }
        default:
          throw new Error(`Invalid value for options.currentVersionResolver: ${options.currentVersionResolver}`);
      }

      if (options.specifier) {
        log(`📄 Using the provided version specifier "${options.specifier}".`);
      }

      /**
       * If we are versioning independently then we always need to determine the specifier for each project individually, except
       * for the case where the user has provided an explicit specifier on the command.
       *
       * Otherwise, if versioning the projects together we only need to perform this logic if the specifier is still unset from
       * previous iterations of the loop.
       *
       * NOTE: In the case that we have previously determined via conventional commits that no changes are necessary, the specifier
       * will be explicitly set to `null`, so that is why we only check for `undefined` explicitly here.
       */
      if (
        specifier === undefined ||
        (options.releaseGroup.projectsRelationship === "independent" && !options.specifier)
      ) {
        const specifierSource = options.specifierSource;
        switch (specifierSource) {
          case "conventional-commits": {
            if (options.currentVersionResolver !== "git-tag") {
              throw new Error(
                `Invalid currentVersionResolver "${options.currentVersionResolver}" provided for release group "${options.releaseGroup.name}". Must be "git-tag" when "specifierSource" is "conventional-commits"`
              );
            }

            const affectedProjects =
              options.releaseGroup.projectsRelationship === "independent" ? [projectName] : projects.map((p) => p.name);

            // latestMatchingGitTag will be undefined if the current version was resolved from the disk fallback.
            // In this case, we want to use the first commit as the ref to be consistent with the changelog command.
            const previousVersionRef = latestMatchingGitTag
              ? latestMatchingGitTag.tag
              : options.fallbackCurrentVersionResolver === "disk"
                ? await getFirstGitCommit()
                : undefined;

            if (!previousVersionRef) {
              // This should never happen since the checks above should catch if the current version couldn't be resolved
              throw new Error(
                `Unable to determine previous version ref for the projects ${affectedProjects.join(
                  ", "
                )}. This is likely a bug in Nx.`
              );
            }

            specifier = await resolveSemverSpecifierFromConventionalCommits(
              previousVersionRef,
              options.projectGraph,
              affectedProjects,
              options.conventionalCommitsConfig!
            );

            if (!specifier) {
              log(`🚫 No changes were detected using git history and the conventional commits standard.`);
              break;
            }

            // TODO: reevaluate this logic/workflow for independent projects
            //
            // Always assume that if the current version is a prerelease, then the next version should be a prerelease.
            // Users must manually graduate from a prerelease to a release by providing an explicit specifier.
            if (prerelease(currentVersion ?? "")) {
              specifier = "prerelease";
              log(`📄 Resolved the specifier as "${specifier}" since the current version is a prerelease.`);
            } else {
              log(
                `📄 Resolved the specifier as "${specifier}" using git history and the conventional commits standard.`
              );
            }
            break;
          }
          case "prompt": {
            // Only add the release group name to the log if it is one set by the user, otherwise it is useless noise
            const maybeLogReleaseGroup = (log: string): string => {
              if (options.releaseGroup.name === IMPLICIT_DEFAULT_RELEASE_GROUP) {
                return log;
              }
              return `${log} within release group "${options.releaseGroup.name}"`;
            };
            if (options.releaseGroup.projectsRelationship === "independent") {
              specifier = await resolveSemverSpecifierFromPrompt(
                `${maybeLogReleaseGroup(`What kind of change is this for project "${projectName}"`)}?`,
                `${maybeLogReleaseGroup(`What is the exact version for project "${projectName}"`)}?`
              );
            } else {
              specifier = await resolveSemverSpecifierFromPrompt(
                `${maybeLogReleaseGroup(
                  `What kind of change is this for the ${projects.length} matched projects(s)`
                )}?`,
                `${maybeLogReleaseGroup(`What is the exact version for the ${projects.length} matched project(s)`)}?`
              );
            }
            break;
          }
          default:
            throw new Error(
              `Invalid specifierSource "${specifierSource}" provided. Must be one of "prompt" or "conventional-commits"`
            );
        }
      }

      // Resolve any local package dependencies for this project (before applying the new version or updating the versionData)
      // const localPackageDependencies = resolveLocalPackageDependencies(
      //   tree,
      //   options.projectGraph,
      //   projects,
      //   projectNameToPackageRootMap,
      //   resolvePackageRoot,
      //   // includeAll when the release group is independent, as we may be filtering to a specific subset of projects, but we still want to update their dependents
      //   options.releaseGroup.projectsRelationship === "independent"
      // );
      //
      // const dependentProjects = Object.values(localPackageDependencies)
      //   .flat()
      //   .filter((localPackageDependency) => {
      //     return localPackageDependency.target === project.name;
      //   });

      if (!currentVersion) {
        throw new Error(
          `The current version for project "${project.name}" could not be resolved. Please report this on https://github.com/nrwl/nx`
        );
      }

      versionData[projectName] = {
        currentVersion,
        dependentProjects: [],
        newVersion: null, // will stay as null in the final result in the case that no changes are detected
      };

      if (!specifier) {
        log(`🚫 Skipping versioning "${packageName}" as no changes were detected.`);
        continue;
      }

      const newVersion = deriveNewSemverVersion(currentVersion, specifier, options.preid);
      versionData[projectName].newVersion = newVersion;

      pkg!.version = newVersion;
      tree.write(pyprojectTomlPath, stringifyPyprojectToml(data));

      log(`✍️  New version ${newVersion} written to ${workspaceRelativePyprojectTomlPath}`);

      // if (dependentProjects.length > 0) {
      //   log(
      //     `✍️  Applying new version ${newVersion} to ${dependentProjects.length} ${
      //       dependentProjects.length > 1 ? "packages which depend" : "package which depends"
      //     } on ${project.name}`
      //   );
      // }

      // for (const dependentProject of dependentProjects) {
      //   const dependentPackageRoot = projectNameToPackageRootMap.get(dependentProject.source);
      //   if (!dependentPackageRoot) {
      //     throw new Error(
      //       `The dependent project "${dependentProject.source}" does not have a packageRoot available. Please report this issue on https://github.com/nrwl/nx`
      //     );
      //   }
      //   const dependentPkg = loadPyprojectTomlWithTree(tree, dependentPackageRoot, dependentProject.source);
      //
      //   // Auto (i.e.infer existing) by default
      //   let versionPrefix = options.versionPrefix ?? "auto";
      //   let updatedDependencyData: string | Record<string, string> = "";
      //
      //   for (const [dependencyName, dependencyData] of Object.entries(
      //     dependentPkg[dependentProject.dependencyCollection] ?? {}
      //   )) {
      //     if (dependencyName !== dependentProject.target) {
      //       continue;
      //     }
      //
      //     // For auto, we infer the prefix based on the current version of the dependent
      //     if (versionPrefix === "auto") {
      //       versionPrefix = ""; // we don't want to end up printing auto
      //
      //       if (currentVersion) {
      //         const dependencyVersion = typeof dependencyData === "string" ? dependencyData : dependencyData.version;
      //         const prefixMatch = dependencyVersion.match(/^[~^=]/);
      //         if (prefixMatch) {
      //           versionPrefix = prefixMatch[0];
      //         } else {
      //           versionPrefix = "";
      //         }
      //
      //         // In python the default version prefix/behavior is ^, so a ^ may have been inferred by pyproject metadata via no prefix or an explicit ^.
      //         if (versionPrefix === "^") {
      //           if (!dependencyData.version.startsWith("^")) {
      //             versionPrefix = "";
      //           }
      //         }
      //       }
      //     }
      //     const newVersionWithPrefix = `${versionPrefix}${newVersion}`;
      //     updatedDependencyData =
      //       typeof dependencyData === "string"
      //         ? newVersionWithPrefix
      //         : {
      //             ...dependencyData,
      //             version: newVersionWithPrefix,
      //           };
      //     break;
      //   }
      //
      //   const pyprojectTomlToUpdate = joinPathFragments(dependentPackageRoot, "pyproject.toml");
      //
      //   modifyPyprojectToml(
      //     dependentPkg,
      //     dependentProject.dependencyCollection,
      //     dependentProject.target,
      //     updatedDependencyData
      //   );
      //
      //   tree.write(pyprojectTomlToUpdate, stringifyPyprojectToml(dependentPkg));
      // }
    }

    /**
     * Ensure that formatting is applied so that version bump diffs are as minimal as possible
     * within the context of the user's workspace.
     */
    await formatFiles(tree);

    // Return the version data so that it can be leveraged by the overall version command
    return {
      data: versionData,
      callback: async () => {
        return [];
      },
    };
  } catch (e: any) {
    if (process.env.NX_VERBOSE_LOGGING === "true") {
      output.error({
        title: e.message,
      });
      // Dump the full stack trace in verbose mode
      console.error(e);
    } else {
      output.error({
        title: e.message,
      });
    }
    process.exit(1);
  }
}

export default releaseVersionGenerator;

function createResolvePackageRoot(customPackageRoot?: string) {
  return (projectNode: ProjectGraphProjectNode): string => {
    // Default to the project root if no custom packageRoot
    if (!customPackageRoot) {
      return projectNode.data.root;
    }
    return interpolate(customPackageRoot, {
      workspaceRoot: "",
      projectRoot: projectNode.data.root,
      projectName: projectNode.name,
    });
  };
}

interface LocalPackageDependency extends ProjectGraphDependency {
  dependencyCollection: "dependencies" | "dev-dependencies";
}

function resolveLocalPackageDependencies(
  tree: Tree,
  projectGraph: ProjectGraph,
  filteredProjects: ProjectGraphProjectNode[],
  projectNameToPackageRootMap: Map<string, string>,
  resolvePackageRoot: (projectNode: ProjectGraphProjectNode) => string,
  includeAll = false
): Record<string, LocalPackageDependency[]> {
  const localPackageDependencies: Record<string, LocalPackageDependency[]> = {};

  const projects = includeAll ? Object.values(projectGraph.nodes) : filteredProjects;

  for (const projectNode of projects) {
    // Resolve the Cargo.toml path for the project, taking into account any custom packageRoot settings
    let packageRoot = projectNameToPackageRootMap.get(projectNode.name);
    // packageRoot wasn't added to the map yet, try to resolve it dynamically
    if (!packageRoot && includeAll) {
      packageRoot = resolvePackageRoot(projectNode);
      if (!packageRoot) {
        continue;
      }
      // Append it to the map for later use within the release version generator
      projectNameToPackageRootMap.set(projectNode.name, packageRoot);
    }
    const projectDeps = projectGraph.dependencies[projectNode.name];
    if (!projectDeps) {
      continue;
    }
    const localPackageDepsForProject = [];
    for (const dep of projectDeps) {
      const depProject = projectGraph.nodes[dep.target];
      if (!depProject) {
        continue;
      }
      const depProjectRoot = projectNameToPackageRootMap.get(dep.target);
      if (!depProjectRoot) {
        throw new Error(
          `The project "${dep.target}" does not have a packageRoot available. Please report this issue on https://github.com/nrwl/nx`
        );
      }
      const pyprojectToml = loadPyprojectTomlWithTree(tree, resolvePackageRoot(projectNode), projectNode.name);
      const dependencies = pyprojectToml.dependencies ?? {};
      const devDependencies = pyprojectToml["dev-dependencies"] ?? {};
      const dependencyCollection: "dependencies" | "dev-dependencies" | null = dependencies[depProject.name]
        ? "dependencies"
        : devDependencies[depProject.name]
          ? "dev-dependencies"
          : null;
      if (!dependencyCollection) {
        throw new Error(
          `The project "${projectNode.name}" does not have a local dependency on "${depProject.name}" in its Cargo.toml`
        );
      }
      localPackageDepsForProject.push({
        ...dep,
        dependencyCollection,
      });
    }

    localPackageDependencies[projectNode.name] = localPackageDepsForProject;
  }

  return localPackageDependencies;
}
