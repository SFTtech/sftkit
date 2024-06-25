import { logger, Tree } from "@nx/devkit";
import TOML from '@ltd/j-toml';
import * as fs from "fs";

export interface BuildSystem {
  requires?: string[];
  build_backend?: string;
  backend_path?: string[];
}

export interface Readme {
  file?: string;
  text?: string;
  content_type?: string;
}

export interface License {
  file?: string;
  text?: string;
}

export interface Contributor {
  name?: string;
  email?: string;
}

export interface Project {
  name?: string;
  version?: string;
  description?: string;
  readme?: string | Readme;
  license?: string | License;
  authors?: Contributor[];
  maintainers?: Contributor[];
  keywords?: string[];
  classifiers?: string[];
  urls?: Record<string, string>;
  requires_python?: string;
  dependencies?: string[],
  optional_dependencies?: string[],
  scripts?: Record<string, string>;
  gui_scripts?: Record<string, string>;
  entry_points?: Record<string, Record<string, string>>;
  dynamic?: string[]
}

export interface PyprojectToml {
  build_system?: BuildSystem;
  project?: Project;
  tool?: Record<string, Record<string, any>>;
  [key: string]: any;
}

export function loadPyprojectTomlWithTree(tree: Tree, projectRoot: string, projectName: string): PyprojectToml {
  const pyprojectTomlString = tree.read(projectRoot + "/pyproject.toml")?.toString();
  if (!pyprojectTomlString) {
    logger.error(`Cannot find a pyproject.toml file in the ${projectName}`);
    throw new Error();
  }

  return parsePyprojectToml(pyprojectTomlString);
}

export function loadPyprojectToml(pyprojectTomlPath: string): PyprojectToml {
  const pyprojectTomlString = fs.readFileSync(pyprojectTomlPath).toString();
  return parsePyprojectToml(pyprojectTomlString);
}

export function parsePyprojectToml(pyprojectString: string) {
    return TOML.parse(pyprojectString, {
    x: { comment: true },
  }) as unknown as PyprojectToml;
}

export function stringifyPyprojectToml(pyprojectToml: PyprojectToml) {
  const tomlString = TOML.stringify(pyprojectToml, {
    newlineAround: 'section',
    indent: 4,
  });
  // the following is a very, very dirty hack for dealing with j-toml not being able to configure the type of quotation

  if (Array.isArray(tomlString)) {
    return tomlString.join('\n').replace(/'/g, '"');
  }

  return tomlString.toString().replace(/'/g, '"');
}

export function modifyPyprojectToml(
  toml: PyprojectToml,
  section: string,
  key: string,
  value: string | object | Array<any> | (() => any)
) {
  toml[section] ??= TOML.Section({});
  toml[section][key] =
    typeof value === 'object' && !Array.isArray(value)
      ? TOML.inline(value as any)
      : typeof value === 'function'
      ? value()
      : value;
}

export function modifyCargoNestedTable(
  toml: PyprojectToml,
  section: string,
  key: string,
  value: object
) {
  toml[section] ??= {};
  toml[section][key] = TOML.Section(value as any);
}
