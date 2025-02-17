"""
These commands need to create LocalRepo -> no GH token required
"""

import os
import subprocess
from os import getcwd
from pathlib import Path
from shutil import which

import click
from click import ClickException

from alpa.config import MetadataConfig
from alpa.repository.branch import LocalRepoBranch, AlpaRepoBranch

from alpa.messages import NO_PRE_COMMIT

pkg_name = click.argument("name", type=str)


@click.command("show-history")
@click.option(
    "-o",
    "--oneline",
    is_flag=True,
    show_default=True,
    default=False,
    help="Each commit is displayed as one line",
)
def show_history(oneline: bool) -> None:
    """Show git history of current package"""
    params = []
    if oneline:
        params.append("--oneline")

    local_repo = LocalRepoBranch(Path(getcwd()))
    click.echo(local_repo.get_history_of_branch(local_repo.branch, params))


@click.command("switch")
@pkg_name
def switch(name: str) -> None:
    """Switch to specified package"""
    LocalRepoBranch(Path(getcwd())).switch_to_package(name)


@click.command("commit")
@click.option(
    "-m",
    "--message",
    type=str,
    default="",
    help="Your commit message not longer than 80 characters.",
)
def commit(message: str) -> None:
    """Commit your changes in your package's repository"""
    if len(message) > 80:
        raise ClickException("Message longer than 80 characters")

    LocalRepoBranch(Path(getcwd())).commit(message)


@click.command("add")
@click.argument("to_add", type=str, required=True)
def add(to_add: str) -> None:
    """Add files to git history. Basically calls `git add <input>`"""
    LocalRepoBranch(Path(getcwd())).add(to_add)


def _skip_pre_commit_checks_for_non_rpm_os() -> None:
    process = subprocess.run(
        ["rpm", "--help"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    if process.returncode != 0:
        # no special pre-commit hooks for non-RPM OS :/
        disabled_checks = ["source0-uses-version-macro", "check-packit-file"]
        click.secho(
            "Warning! You don't have RPM based OS, these checks are "
            f"disabled: {disabled_checks}",
            fg="yellow",
        )
        os.environ["SKIP"] = ",".join(disabled_checks)


@click.command("push")
@click.option(
    "-p",
    "--pull-request",
    is_flag=True,
    show_default=True,
    default=False,
    help="This will create pull request on GitHub for you.",
)
@click.option("-n", "--no-verify", is_flag=True, help="Do not run pre-commit")
def push(pull_request: bool, no_verify: bool) -> None:
    """Pushes your commited changes to the Alpa repo so you can make PR"""
    if not no_verify:
        if which("pre-commit") is None:
            click.secho(NO_PRE_COMMIT, fg="red", err=True)
            return

        _skip_pre_commit_checks_for_non_rpm_os()
        ret = subprocess.run(["pre-commit", "run", "--all-files"])
        if ret.returncode != 0:
            # pre-commit already gives info about fail
            return

    repo_path = Path(getcwd())
    local_repo = LocalRepoBranch(repo_path)
    local_repo.push(local_repo.branch)

    if not pull_request:
        return

    alpa = AlpaRepoBranch(repo_path)
    pr = alpa.gh_repo.create_pr(
        title=f"[alpa-cli] Create update of package {local_repo.package}",
        body=(
            "This PR was created automatically via alpa-cli for "
            f"user {alpa.gh_api.gh_user}"
        ),
        source_branch=f"{local_repo.feat_branch}",
        target_branch=local_repo.package,
    )
    click.echo(f"PR#{pr.number} created. URL: {pr.html_url}")


@click.command("pull")
def pull() -> None:
    """Pull last recent changes of package you are on from Alpa repo"""
    local_repo = LocalRepoBranch(Path(getcwd()))
    local_repo.pull(local_repo.branch)


@click.command("list")
@click.option("-p", "--pattern", type=str, default="", help="Optional pattern to match")
def list_(pattern: str) -> None:
    """List all packages or packages matching regex"""
    for pkg in LocalRepoBranch(Path(getcwd())).get_packages(pattern):
        click.echo(pkg)


# TODO: please implement me
# @click.command("genspec")
# @click.option(
#     "--lang",
#     type=Choice(["python", "java"], case_sensitive=False),
#     required=True,
#     help="Choose the programming language for which the generator is designed",
# )
# @click.option(
#     "-t",
#     "--test",
#     default=False,
#     help=(
#         "Send package with generated spec file to "
#         "packit to test whether build will succeed."
#     ),
# )
# def genspec(lang: str, test: bool) -> None:
#     """This command uses some existing spec file generators for you"""
#     raise NotImplementedError("Not implemented yet (1.0 goal)")


@click.command("create-packit-config")
@click.option(
    "--override",
    is_flag=True,
    show_default=True,
    default=False,
    help="Override packit config file",
)
def create_packit_config(override: bool) -> None:
    """Creates packit config based on metadata.yaml file in package"""
    if not LocalRepoBranch(Path(getcwd())).create_packit_config(override):
        raise ClickException(
            "Packit file already exists. To override it use --override flag."
        )


@click.command("mockbuild")
@click.option(
    "--chroot",
    type=str,
    default="",
    help="Override chroots specified in metadata.yaml by one specific chroot",
)
def mockbuild(chroot: str) -> None:
    """
    Uses mock tool to build package. WARNING: works only on rpm-based systems.

    Builds for all chroots specified in metadata.yaml. Can be overriden by --chroot
     option which does build against one specified chroot.
    """
    from alpa.upstream_integration import UpstreamIntegration

    if chroot:
        chroots = [chroot]
    else:
        chroots = MetadataConfig.get_config().chroots

    UpstreamIntegration(Path(getcwd())).mockbuild(chroots)


@click.command("get-pkg-archive")
def get_pkg_archive() -> None:
    """Gets archive from package config. WARNING: works only on rpm-based systems."""
    from specfile import Specfile
    from alpa.upstream_integration import UpstreamIntegration

    specfile_path = None
    cwd = Path(getcwd())
    for file in cwd.iterdir():
        if str(file).endswith(".spec"):
            specfile_path = file

    if specfile_path is None:
        raise ClickException(f"No specfile found in {cwd}")

    specfile = Specfile(specfile_path)
    with specfile.sources() as sources:
        source0 = min(sources, key=lambda src: src.number)

    UpstreamIntegration.download_upstream_source(
        source0.expanded_location,
        f"{specfile.expanded_name}-{specfile.expanded_version}",
    )
