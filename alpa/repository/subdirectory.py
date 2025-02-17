"""
Classes for communication with Alpa subdirectory type of git
"""

from pathlib import Path
from typing import Optional

from alpa.gh import GithubAPI

from alpa.repository.base import LocalRepo, AlpaRepo


class LocalRepoSubdirectory(LocalRepo):
    def __init__(self, repo_path: Path) -> None:
        super().__init__(repo_path)
        raise NotImplementedError("Please implement me.")

    def create_packit_config(self, override: bool) -> bool:
        raise NotImplementedError("Please implement me.")

    @property
    def package(self) -> str:
        raise NotImplementedError("Please implement me.")

    def _ensure_feature_branch(self) -> None:
        raise NotImplementedError("Please implement me.")

    def get_history_of_package(self, package: str) -> str:
        raise NotImplementedError("Please implement me.")

    def get_packages(self, regex: str = "") -> list[str]:
        raise NotImplementedError("Please implement me.")

    def switch_to_package(self, package: str) -> None:
        raise NotImplementedError("Please implement me.")


class AlpaRepoSubdirectory(AlpaRepo, LocalRepoSubdirectory):
    def __init__(self, repo_path: Path, gh_api: Optional[GithubAPI] = None) -> None:
        super().__init__(repo_path, gh_api)
        raise NotImplementedError("Please implement me.")

    def create_package(self, package: str) -> None:
        raise NotImplementedError("Please implement me.")

    def request_package_delete(self, package_name: str) -> None:
        raise NotImplementedError("Please implement me.")

    def delete_package(self, package: str) -> bool:
        raise NotImplementedError("Please implement me.")
