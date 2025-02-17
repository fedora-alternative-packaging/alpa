"""
Set of commands that helps with integration of Alpa
repository.
"""

import logging
import subprocess
from abc import ABC, abstractmethod
from json import dumps
from os import getcwd
from pathlib import Path
from typing import Optional, Iterable
from urllib.parse import urlparse

from click import UsageError, ClickException
import click

from alpa.packit import Packit
from alpa.constants import (
    ALPA_FEAT_BRANCH,
    ALPA_FEAT_BRANCH_PREFIX,
    ORIGIN_NAME,
    UPSTREAM_NAME,
    RequestEnum,
    REQUEST_LABEL,
    DELETE_PACKAGE_REQUEST_TITLE,
    CREATE_PACKAGE_REQUEST_TITLE,
)
from alpa.gh import GithubAPI, GithubRepo
from alpa.git import GitCMD
from alpa.messages import (
    CLONED_REPO_IS_NOT_FORK,
    NOT_IN_PREDEFINED_STATE,
    CLONED_REPO_IS_FORK,
    NO_PERMISSION_FOR_ALPA_REPO,
)


logger = logging.getLogger(__name__)


class LocalRepo(ABC):
    def __init__(self, repo_path: Path) -> None:
        self.repo_path = repo_path
        self.git = GitCMD(str(self.repo_path))
        self.git_cmd = self.git.git_cmd

        if not self._is_repo_in_predefined_state():
            raise ClickException(NOT_IN_PREDEFINED_STATE)

        # do it after predefined state is checked since this depends on it
        # (see comment in the _should_be_fork)
        self.remote_name = UPSTREAM_NAME if self._should_be_fork() else ORIGIN_NAME
        logger.debug(f"Remote name for this repository is set to {self.remote_name}")

        # lazy properties
        self._namespace: Optional[str] = None
        self._repo_name: Optional[str] = None

    @abstractmethod
    def get_packages(self, regex: str = "") -> list[str]:
        pass

    @abstractmethod
    def switch_to_package(self, package: str) -> None:
        pass

    @abstractmethod
    def _ensure_feature_branch(self) -> None:
        pass

    @abstractmethod
    def get_history_of_package(self, package: str) -> str:
        pass

    @property
    @abstractmethod
    def package(self) -> str:
        pass

    @abstractmethod
    def create_packit_config(self, override: bool) -> bool:
        pass

    @property
    def branch(self) -> str:
        return self.git_cmd(["rev-parse", "--abbrev-ref", "HEAD"]).stdout

    @staticmethod
    def get_feat_branch_of_package(package: str) -> str:
        return ALPA_FEAT_BRANCH.format(pkgname=package)

    @property
    def feat_branch(self) -> str:
        return ALPA_FEAT_BRANCH.format(pkgname=self.package)

    @staticmethod
    def _get_relevant_remote_refs(remote_refs: Iterable[str]) -> list[str]:
        relevant_refs = []
        for ref in remote_refs:
            parsed_ref = ref.split("/")[-1]
            if not parsed_ref.startswith(ALPA_FEAT_BRANCH_PREFIX):
                logger.debug(f"Relevant remote ref found: {parsed_ref}")
                relevant_refs.append(parsed_ref)

        return relevant_refs

    def get_remote_branches(self, remote: str) -> list[str]:
        lines = [
            line.strip()
            for line in self.git_cmd(
                ["remote", "--verbose", "show", remote]
            ).stdout.split("\n")
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

    @property
    def remotes(self) -> set[str]:
        return set(self.git_cmd(["remote"]).stdout.split())

    def _is_repo_in_predefined_state(self) -> bool:
        return self.remotes == {ORIGIN_NAME, UPSTREAM_NAME} or self.remotes == {
            ORIGIN_NAME
        }

    def _should_be_fork(self) -> bool:
        # if repo is prepared via alpa-cli, fork should have 2 remotes and non-fork 1
        return len(self.remotes) > 1

    @property
    def untracked_files(self) -> list[str]:
        return self.git_cmd(["ls-files", "-o", "--exclude-standard"]).stdout.split()

    def _get_dirty_files(self, staged: bool) -> list[str]:
        result = []
        status_output = self.git_cmd(["status", "--porcelain=1"]).stdout
        if not status_output:
            return []

        for line in status_output.split("\n"):
            if line == "":
                # some empty line in the output
                continue

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

    def is_dirty(self) -> bool:
        return self.git_cmd(["status", "--porcelain"]).stdout != ""

    @property
    def modified_files(self) -> list[str]:
        return self._get_dirty_files(False)

    @property
    def files_to_be_committed(self) -> list[str]:
        return self._get_dirty_files(True)

    @property
    def namespace(self) -> str:
        if self._namespace is not None:
            return self._namespace

        self._namespace = self.full_reponame().split("/")[0]
        logger.debug(f"Setting namespace to {self._namespace}")
        return self._namespace

    @property
    def repo_name(self) -> str:
        if self._repo_name is not None:
            return self._repo_name

        self._repo_name = self.full_reponame().split("/")[1]
        logger.debug(f"Setting repo name to {self._repo_name}")
        return self._repo_name

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
        branches = self.git_cmd(["branch"]).stdout.split()
        for ref in branches:
            if ref.strip() == branch:
                return True

        logger.debug(f"Branch {branch} does not exist in {branches}")
        return False

    def get_history_of_branch(self, branch: str, params: list[str]) -> str:
        return self.git_cmd(["log", "--decorate", "--graph"] + params + [branch]).stdout

    def commit(self, message: str) -> bool:
        packit_conf = Packit(self.package)
        if not packit_conf.packit_config_file_exists():
            packit_conf.create_packit_config()
            self.git_cmd(["add", ".packit.yaml"])
            self.git_cmd(
                [
                    "commit",
                    "-m",
                    "alpa: automatically add .packit.yaml config to the package",
                    ".packit.yaml",
                ]
            )

        self._ensure_feature_branch()
        if message:
            self.git_cmd(["commit", "-m", message])
        else:
            self.git_cmd(["commit"])

        return True

    def add(self, to_add: str) -> None:
        self._ensure_feature_branch()
        self.git_cmd(["add"] + to_add.split())

    def pull(self, branch: str) -> None:
        click.echo(self.git_cmd(["pull", self.remote_name, branch]).stderr_and_stdout)

    def push(self, branch: str, force: bool = False) -> None:
        # you always want to push to origin, even from a fork
        cmd = ["push", ORIGIN_NAME, branch]
        if force:
            cmd.append("--force")

        click.echo(self.git_cmd(cmd).stderr_and_stdout)

    @staticmethod
    def _parse_reponame_from_url(url: str) -> str:
        without_git_suffix = url.removesuffix(".git")
        if without_git_suffix.startswith("https://") or without_git_suffix.startswith(
            "http://"
        ):
            logger.info(f"Git remote url is in https form {without_git_suffix}")
            split = without_git_suffix.split("/")
            return f"{split[-2]}/{split[-1]}"

        return without_git_suffix.split(":")[-1]

    def full_reponame(self) -> str:
        logger.debug(f"Trying to find {self.remote_name} in {self.remotes}")
        for remote in self.remotes:
            if remote == self.remote_name:
                remote_url = self.git_cmd(
                    ["config", "--get", f"remote.{remote}.url"]
                ).stdout
                logger.debug(
                    f"Remote {remote} found. Parsing its remote url {remote_url}"
                )
                return self._parse_reponame_from_url(remote_url)

        logger.debug("There are no remotes in this repo")
        return ""

    @property
    def git_root(self) -> Path:
        return Path(self.git.git_root)

    def is_branch_merged(self, branch: str) -> bool:
        ret = self.git_cmd(["fetch", self.remote_name, branch])
        return ret.retval != 0 and "couldn't find remote ref" in ret.stderr


class AlpaRepo(LocalRepo):
    def __init__(self, repo_path: Path, gh_api: Optional[GithubAPI] = None) -> None:
        super().__init__(repo_path)

        self.gh_api = gh_api or GithubAPI(self.repo_name)
        self.gh_repo = self.gh_api.get_repo(self.namespace, self.repo_name)

    @abstractmethod
    def create_package(self, package: str) -> None:
        pass

    def _request_package_action(self, request_type: RequestEnum, pkg: str) -> None:
        ensured_upstream = self.gh_repo.get_root_repo()
        upstream_namespace = ensured_upstream.namespace
        issue_repo = self.gh_api.get_repo(upstream_namespace, self.gh_repo.repo_name)

        if request_type == RequestEnum.delete:
            title = DELETE_PACKAGE_REQUEST_TITLE.format(package_name=pkg)
        else:
            title = CREATE_PACKAGE_REQUEST_TITLE.format(package_name=pkg)

        body = {
            "request_type": request_type,
            "user": self.gh_api.gh_user,
            "package": pkg,
        }
        issue = issue_repo.create_issue(title, dumps(body))
        issue.add_to_labels(REQUEST_LABEL)

    def request_package(self, package_name: str) -> None:
        self._request_package_action(RequestEnum.create, package_name)

    def request_package_delete(self, package: str) -> None:
        self._request_package_action(RequestEnum.delete, package)

    @staticmethod
    def _prepare_cloned_repo(where_to_clone: str, gh_repo: GithubRepo) -> None:
        if not gh_repo.is_fork:
            return

        upstream_clone_url = gh_repo.upstream_clone_url
        assert upstream_clone_url is not None
        subprocess.run(
            ["git", "remote", "add", UPSTREAM_NAME, upstream_clone_url],
            cwd=where_to_clone,
        )

    @staticmethod
    def _get_repo_name_from_url(repo_url: str) -> str:
        return repo_url.split("/")[-1].removesuffix(".git")

    @staticmethod
    def _check_for_permission_and_fork(
        clone_fork: bool, gh_repo: GithubRepo
    ) -> tuple[bool, str]:
        if clone_fork and not gh_repo.is_fork:
            return False, CLONED_REPO_IS_NOT_FORK

        if not clone_fork and gh_repo.is_fork:
            return False, CLONED_REPO_IS_FORK

        if not gh_repo.is_fork and not gh_repo.has_write_access(gh_repo.api_user):
            return False, NO_PERMISSION_FOR_ALPA_REPO

        return True, ""

    @classmethod
    def clone(cls, url: str, clone_fork: bool) -> None:
        # in case of `@` in url -> remove the `git@` prefix form it
        repo_path = urlparse(url.split("@")[-1]).path
        parsed_repo_path = repo_path.strip("/").strip(".git")
        namespace, repo_name = parsed_repo_path.split("/")
        api = GithubAPI(repo_name)
        gh_repo = api.get_repo(namespace, repo_name)

        check_result, stderr = cls._check_for_permission_and_fork(clone_fork, gh_repo)
        if not check_result:
            raise UsageError(stderr)

        cwd = getcwd()
        where_to_clone = f"{cwd}/{cls._get_repo_name_from_url(url)}"
        subprocess.run(["git", "clone", url, where_to_clone], cwd=cwd)
        cls._prepare_cloned_repo(where_to_clone, gh_repo)
