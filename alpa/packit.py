"""
Class that generates packit.yaml config based on other configs like
Alpa repo or package metadata config
"""

from os import getcwd
from pathlib import Path

from yaml import dump

from alpa.config import AlpaRepoConfig, MetadataConfig

from alpa.constants import PACKIT_CONFIG_NAMES


class Packit:
    def __init__(self, package_name: str) -> None:
        self.package_name = package_name
        self.working_dir = Path(getcwd())
        self.metadata = MetadataConfig.get_config(self.working_dir)
        self.alpa_repo_config = AlpaRepoConfig.get_config()

    def get_packit_config(self) -> dict:
        targets_with_arch = []
        for arch in self.metadata.arch:
            for target in self.metadata.targets:
                targets_with_arch.append(f"{target}-{arch}")

        jobs = [
            {
                "job": "copr_build",
                "trigger": "pull_request",
                "targets": targets_with_arch,
                "owner": self.alpa_repo_config.copr_owner,
                "project": f"{self.alpa_repo_config.copr_repo}-pull-requests",
            },
            {
                "job": "copr_build",
                "trigger": "commit",
                "branch": self.package_name,
                "targets": targets_with_arch,
                "owner": self.alpa_repo_config.copr_owner,
                "project": self.alpa_repo_config.copr_repo,
            },
        ]

        if self.metadata.autoupdate is not None:
            autoupdate_dict = {
                "job": "copr_build",
                "trigger": "commit",
                "branch": f"__alpa_autoupdate_{self.package_name}",
                "targets": targets_with_arch,
                "owner": self.alpa_repo_config.copr_owner,
                "project": f"{self.alpa_repo_config.copr_repo}-pull-requests",
            }
            jobs.append(autoupdate_dict)

        return {
            "specfile_path": f"{self.package_name}.spec",
            "srpm_build_deps": ["pip"],
            "actions": {
                "create-archive": [
                    "pip install pyalpa",
                    'bash -c "alpa get-pkg-archive"',
                    'bash -c "ls -1 ./*.tar.gz"',
                ],
            },
            "jobs": jobs,
        }

    def packit_config_file_exists(self) -> bool:
        for packit_config_name in PACKIT_CONFIG_NAMES:
            files_in_dir = [
                file.name for file in self.working_dir.iterdir() if file.is_file()
            ]
            if packit_config_name in files_in_dir:
                return True

        return False

    def create_packit_config(self, override: bool = False) -> None:
        if not override and self.packit_config_file_exists():
            raise FileExistsError("Packit configuration file already exists")

        with open(".packit.yaml", "w") as packit_yaml:
            packit_yaml.write(dump(self.get_packit_config(), sort_keys=False))
