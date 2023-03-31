"""
Set of commands that helps with integration of Alpa
repository.
"""
import subprocess
from os import getcwd, environ
from pathlib import Path
import re
from subprocess import call
from tempfile import NamedTemporaryFile
from typing import List, Optional
from urllib.parse import urlparse

from click import UsageError, ClickException
import click
from git import Repo, Remote, GitCommandError

from alpa.config.packit import PackitConfig
from alpa.constants import (
    ALPA_FEAT_BRANCH,
    ALPA_FEAT_BRANCH_PREFIX,
    MAIN_BRANCH,
    ORIGIN_NAME,
    UPSTREAM_NAME,
    PackageRequest,
)
from alpa.gh import GithubAPI, GithubRepo
from alpa.messages import (
    CLONED_REPO_IS_NOT_FORK,
    NO_WRITE_ACCESS_ERR,
    NOT_IN_PREDEFINED_STATE,
)


class LocalRepo:
    def __init__(self, repo_path: Path) -> None:
        self.repo_path = repo_path
        # TODO: this will differ in the future with repo_path
        self.repo_root_path = repo_path
        self.local_repo = Repo(str(self.repo_path))
        self.git_cmd = self.local_repo.git

        if not self._is_repo_in_predefined_state():
            raise ClickException(NOT_IN_PREDEFINED_STATE)

    @property
    def remote_associated_with_current_branch(self) -> str:
        return self.local_repo.active_branch.tracking_branch().remote_name

    @property
    def branch(self) -> str:
        return self.local_repo.active_branch.name

    @property
    def package(self) -> str:
        return self.branch.lstrip(ALPA_FEAT_BRANCH_PREFIX)

    @staticmethod
    def get_feat_branch_of_package(package: str) -> str:
        return ALPA_FEAT_BRANCH.format(pkgname=package)

    @property
    def feat_branch(self) -> str:
        return ALPA_FEAT_BRANCH.format(pkgname=self.package)

    def show_remote_branches(self, remote: str) -> List[str]:
        lines = [
            line.strip()
            for line in self.git_cmd.remote("--verbose", "show", remote).split("\n")
        ]
        # TODO: do a better job
        remote_branch_line = ["Remote branch:", "Remote branches:"]
        start = -1
        for line_to_match in remote_branch_line:
            if line_to_match in lines:
                start = lines.index(line_to_match)
                break

        if start == -1:
            return []

        # TODO: do a better job
        possible_start_of_local_stuff = [
            "Local branch configured for 'git pull':",
            "Local branches configured for 'git pull':",
            "Local ref configured for 'git push':",
            "Local refs configured for 'git push':",
        ]
        end = -1
        for line_to_match in possible_start_of_local_stuff:
            if line_to_match in lines:
                end = lines.index(line_to_match)
                break

        if end == -1:
            end = len(lines)

        lines_with_remote_branches = lines[start + 1 : end]
        return [line.split()[0] for line in lines_with_remote_branches]

    def get_packages(self, regex: str) -> List[str]:
        # self.local_repo.remote(name=UPSTREAM_NAME).refs don't work on every case
        refs_without_main = filter(
            lambda ref: ref != "main", self.show_remote_branches(UPSTREAM_NAME)
        )
        if regex == "":
            return list(refs_without_main)

        pattern = re.compile(regex)
        return [ref for ref in refs_without_main if pattern.match(ref)]

    def _is_repo_in_predefined_state(self) -> bool:
        remotes_name_set = {remote.name for remote in self.local_repo.remotes}
        return remotes_name_set == {ORIGIN_NAME, UPSTREAM_NAME}

    @property
    def untracked_files(self) -> list[str]:
        return self.local_repo.untracked_files

    def _get_dirty_files(self, staged: bool) -> list[str]:
        result = []
        status_output = self.git_cmd.status("--porcelain=1").split("\n")
        for line in status_output:
            file = line.split()[-1]
            if line.startswith("MM"):
                result.append(file)
                continue

            if not staged and line.startswith(" M"):
                result.append(file)
                continue

            if staged and line.startswith("M "):
                result.append(file)
                continue

        return result

    @property
    def modified_files(self) -> list[str]:
        return self._get_dirty_files(False)

    @property
    def files_to_be_committed(self) -> list[str]:
        return self._get_dirty_files(True)

    @staticmethod
    def _format_files_to_status(files: list[str], msg: str) -> str:
        if not files:
            return ""

        output = msg + "\n"
        output += "\n".join(files)
        return output + "\n"

    def get_status_output(self) -> str:
        output = self._format_files_to_status(
            self.files_to_be_committed, "Files to commit:"
        )
        output += self._format_files_to_status(self.modified_files, "Modified files:")
        output += self._format_files_to_status(self.untracked_files, "Untracked files:")
        return output

    def branch_exists(self, branch: str) -> bool:
        for ref in self.local_repo.references:
            if ref.name == branch:
                return True

        return False

    def switch_to_package(self, package: str) -> None:
        if self.local_repo.is_dirty():
            click.echo(
                "Repo is dirty, please commit your changes before switching to"
                f" another package.\n {self.get_status_output()}"
            )
            return None

        feat_branch = self.get_feat_branch_of_package(package)
        branch_to_switch = feat_branch if self.branch_exists(feat_branch) else package
        try:
            click.echo(self.git_cmd.switch(branch_to_switch))
        except GitCommandError:
            # switching to the package for the first time
            click.echo(f"Switching to the package {package} for the first time")
            click.echo(self.git_cmd.fetch(UPSTREAM_NAME, branch_to_switch))
            click.echo(self.git_cmd.switch(branch_to_switch))

    def get_history_of_branch(self, branch: str, *params: List[str]) -> str:
        return self.git_cmd.log("--decorate", "--graph", *params, branch)

    @staticmethod
    def _get_message_from_editor() -> str:
        with NamedTemporaryFile(suffix=".alpa.tmp") as temp_file:
            call([environ.get("EDITOR", "vim"), temp_file.name])
            temp_file.seek(0)
            output = temp_file.read()
            if isinstance(output, (bytes, bytearray)):
                return output.decode("utf-8")

            return output

    def _ensure_feature_branch(self) -> None:
        if self.branch != self.package:
            return None

        click.echo("Switching to feature branch")
        self.git_cmd.switch("-c", self.feat_branch)

    def commit(self, message: str, pre_commit: bool) -> bool:
        if pre_commit:
            ret = subprocess.run(["pre-commit", "run", "--all-files"])
            if ret.returncode != 0:
                return False

        self._ensure_feature_branch()
        index = self.local_repo.index
        if message:
            index.commit(message)
        else:
            index.commit(self._get_message_from_editor())

        return True

    def add(self, files: List[str]) -> None:
        self._ensure_feature_branch()
        # FIXME: alpa add . acts weird
        self.git_cmd.add(files)

    def pull(self, branch: str) -> None:
        click.echo(self.git_cmd.pull(UPSTREAM_NAME, branch))

    def push(self, branch: str) -> None:
        click.echo(self.git_cmd.push(ORIGIN_NAME, branch))

    def _get_full_reponame(self) -> str:
        for remote in self.local_repo.remotes:
            if remote.name == ORIGIN_NAME:
                return remote.url.split(":")[-1].rstrip(".git")

        return ""

    def create_packit_config(self, override: bool) -> bool:
        packit_conf = PackitConfig(self.package)
        if packit_conf.packit_config_file_exists() and not override:
            return False

        packit_conf.create_packit_config()
        return True


class AlpaRepo(LocalRepo):
    def __init__(self, repo_path: Path, gh_api: Optional[GithubAPI] = None) -> None:
        super().__init__(repo_path)

        self.gh_api = gh_api or GithubAPI()
        namespace, repo_name = self._get_full_reponame().split("/")
        self.gh_repo = self.gh_api.get_repo(namespace, repo_name)

    def create_package(self, package: str) -> None:
        upstream = self.gh_repo.get_upstream()
        if upstream and not upstream.has_write_access(self.gh_api.gh_user):
            raise ClickException(NO_WRITE_ACCESS_ERR)

        self.git_cmd.switch(MAIN_BRANCH)
        self.git_cmd.switch("-c", package)
        self.git_cmd.push(UPSTREAM_NAME, package)
        click.echo(f"Package {package} created")

    def request_package(self, package_name: str) -> None:
        upstream = self.gh_repo.get_root_repo()
        upstream_namespace = upstream.namespace
        issue_repo = self.gh_api.get_repo(upstream_namespace, self.gh_repo.repo_name)
        issue = issue_repo.create_issue(
            PackageRequest.TITLE.value.format(package_name=package_name),
            PackageRequest.BODY.value.format(
                user=self.gh_api.gh_user,
                package_name=package_name,
                repo_name=self.gh_repo.repo_name,
            ),
        )
        issue.add_to_labels(PackageRequest.LABEL)

    def delete_package(self) -> None:
        pass

    @staticmethod
    def _prepare_cloned_repo(local_repo: Repo, gh_repo: GithubRepo) -> None:
        Remote.create(local_repo, UPSTREAM_NAME, gh_repo.upstream_clone_url)

    @staticmethod
    def _get_repo_name_from_url(repo_url: str) -> str:
        return repo_url.split("/")[-1].rstrip(".git")

    @classmethod
    def clone(cls, url: str) -> None:
        # in case of `@` in url -> remove the `git@` prefix form it
        repo_path = urlparse(url.split("@")[-1]).path
        parsed_repo_path = repo_path.strip("/").strip(".git")
        namespace, repo_name = parsed_repo_path.split("/")
        api = GithubAPI()
        gh_repo = api.get_repo(namespace, repo_name)
        if not gh_repo.is_fork():
            raise UsageError(CLONED_REPO_IS_NOT_FORK)

        cloned_repo = Repo.clone_from(
            url, f"{getcwd()}/{cls._get_repo_name_from_url(url)}"
        )
        cls._prepare_cloned_repo(cloned_repo, gh_repo)
