"""
Config class for Alpa repository.
"""

import subprocess
from enum import Enum
from pathlib import Path
from typing import Optional

from yaml import safe_load

from alpa.constants import ALPA_CONFIG_FILE_NAMES
from alpa.exceptions import AlpaConfException
from alpa.config.base import Config


class AlpaRepoType(str, Enum):
    branch = "branch"
    # TODO: in the future `subdirectory = "subdirectory"`


class AlpaRepoConfig(Config):
    def __init__(
        self,
        repo_type: AlpaRepoType,
        copr_owner: str,
        copr_repo: str,
        allow_foreign_contributing: bool = False,
        targets: Optional[set[str]] = None,
        arch: Optional[set[str]] = None,
    ) -> None:
        self.repo_type = repo_type
        self.copr_owner = copr_owner
        self.copr_repo = copr_repo

        # optional parameters
        self.allow_foreign_contributing = allow_foreign_contributing
        self.targets = targets
        self.arch = arch

    @classmethod
    def _config_from_dict(cls, d: dict) -> "AlpaRepoConfig":
        for mandatory_key in ["repo_type", "copr_owner", "copr_repo"]:
            cls._check_for_mandatory_key(d, mandatory_key, "alpa.yaml")

        targets = d.get("targets")
        if targets is not None:
            targets = set(targets)

        arch = d.get("arch")
        if arch is not None:
            arch = set(arch)

        return AlpaRepoConfig(
            repo_type=AlpaRepoType[d["repo_type"]],
            copr_owner=d["copr_owner"],
            copr_repo=d["copr_repo"],
            allow_foreign_contributing=d.get("allow_foreign_contributing", False),
            targets=targets,
            arch=arch,
        )

    @classmethod
    def _load_alpa_config(cls, pwd: Path) -> Optional["AlpaRepoConfig"]:
        config_file_path = cls.get_config_file_path(pwd, ALPA_CONFIG_FILE_NAMES)
        if config_file_path is None:
            return None

        with open(config_file_path) as alpa_config_file:
            return cls._config_from_dict(safe_load(alpa_config_file.read()))

    @classmethod
    def get_config(cls) -> "AlpaRepoConfig":
        process = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if process.returncode != 0:
            raise AlpaConfException(process.stderr)

        alpa_config = cls._load_alpa_config(Path(process.stdout.decode().strip()))
        if alpa_config is None:
            raise FileNotFoundError("No alpa config file in git root found")

        return alpa_config
