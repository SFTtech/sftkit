#!/usr/bin/python3

# Build the Debian packages using Docker images.
#
# This script builds the Docker images and then executes them sequentially, each
# one building a Debian package for the targeted operating system. It is
# designed to be a "single command" to produce all the images.
#
# By default, builds for all known distributions, but a list of distributions
# can be passed on the commandline for debugging.

# Taken from https://github.com/matrix-org/synapse/blob/develop/debian/build_virtualenv, released under Apache 2

import os
import signal
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional, Sequence

DISTS = (
    "debian:bookworm",
    "debian:trixie",
)


class Builder:
    def __init__(
        self,
        project_root: Path,
        project_name: str,
        docker_executable: str,
        redirect_stdout=False,
        docker_build_args: Optional[Sequence[str]] = None,
    ):
        self.project_root = project_root
        self.project_name = project_name
        self.docker_executable = docker_executable
        self.redirect_stdout = redirect_stdout
        self._docker_build_args = tuple(docker_build_args or ())
        self.active_containers: set[str] = set()
        self._lock = threading.Lock()
        self._failed = False

    def run_build(self, dist: str, skip_tests=False):
        """Build deb for a single distribution"""

        if self._failed:
            print("not building %s due to earlier failure" % (dist,))
            raise RuntimeError("failed")

        try:
            self._inner_build(dist, skip_tests)
        except Exception as e:
            print("build of %s failed: %s" % (dist, e), file=sys.stderr)
            self._failed = True
            raise

    def _inner_build(self, dist: str, skip_tests=False):
        tag = dist.split(":", 1)[1]

        # Make the dir where the debs will live.
        #
        # Note that we deliberately put this outside the source tree, otherwise
        # we tend to get source packages which are full of debs. (We could hack
        # around that with more magic in the build_debian.sh script, but that
        # doesn't solve the problem for natively-run dpkg-buildpakage).
        debsdir = os.path.join(self.project_root, "../debs")
        os.makedirs(debsdir, exist_ok=True)

        if self.redirect_stdout:
            logfile = os.path.join(debsdir, "%s.buildlog" % (tag,))
            print("building %s: directing output to %s" % (dist, logfile))
            stdout = open(logfile, "w", encoding="utf-8")
        else:
            stdout = None

        # first build a docker image for the build environment
        build_args = (
            (
                self.docker_executable,
                "build",
                "--tag",
                "dh-venv-builder:" + tag,
                "--build-arg",
                "distro=" + dist,
                "-f",
                "docker/dhvirtualenv.Dockerfile",
            )
            + self._docker_build_args
            + (".",)
        )

        subprocess.check_call(
            build_args,
            stdout=stdout,
            stderr=subprocess.STDOUT,
            cwd=self.project_root,
        )

        container_name = f"{self.project_name}_build_{tag}"
        with self._lock:
            self.active_containers.add(container_name)

        # then run the build itself
        subprocess.check_call(
            [
                self.docker_executable,
                "run",
                "--rm",
                "--name",
                container_name,
                "--volume=" + debsdir + ":/debs",
                "-e",
                "TARGET_USERID=%i" % (os.getuid(),),
                "-e",
                "TARGET_GROUPID=%i" % (os.getgid(),),
                "-e",
                "DEB_BUILD_OPTIONS=%s" % ("nocheck" if skip_tests else ""),
                "dh-venv-builder:" + tag,
            ],
            stdout=stdout,
            stderr=subprocess.STDOUT,
        )

        with self._lock:
            self.active_containers.remove(container_name)

        if stdout is not None:
            stdout.close()
            print("Completed build of %s" % (dist,))

    def kill_containers(self):
        with self._lock:
            active = list(self.active_containers)

        for c in active:
            print("killing container %s" % (c,))
            subprocess.run(
                [
                    self.docker_executable,
                    "kill",
                    c,
                ],
                stdout=subprocess.DEVNULL,
                check=True,
            )
            with self._lock:
                self.active_containers.remove(c)


def run_builds(builder: Builder, dists, jobs=1, skip_tests=False):
    def sig(signum, _frame):
        del signum  # unused

        print("Caught SIGINT")
        builder.kill_containers()

    signal.signal(signal.SIGINT, sig)

    with ThreadPoolExecutor(max_workers=jobs) as e:
        res = e.map(lambda dist: builder.run_build(dist, skip_tests), dists)

    # make sure we consume the iterable so that exceptions are raised.
    for _ in res:
        pass


def build_debian_packages(
    project_root: Path,
    project_name: str,
    distributions: list[str],
    jobs: int,
    docker_executable: str,
    no_check: bool,
    docker_build_args: list[str],
):
    global_builder = Builder(
        project_root=project_root,
        project_name=project_name,
        docker_executable=docker_executable,
        redirect_stdout=jobs > 1,
        docker_build_args=docker_build_args,
    )
    run_builds(
        global_builder,
        dists=distributions,
        jobs=jobs,
        skip_tests=no_check,
    )
