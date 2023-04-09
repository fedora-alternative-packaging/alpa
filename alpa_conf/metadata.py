from os import getcwd
from pathlib import Path
from typing import Optional

from pydantic import EmailStr
from pydantic.dataclasses import dataclass
from yaml import safe_load

from alpa_conf.constants import METADATA_FILE_NAMES
from alpa_conf.config_base import Config


@dataclass
class User:
    nick: str
    email: EmailStr


@dataclass
class Autoupdate:
    upstream_pkg_name: str
    anytia_backend: str  # TODO: anytia backend enum
    targets_notify_on_fail: set[str]


class MetadataConfig(Config):
    def __init__(
        self,
        autoupdate: Optional[Autoupdate],
        maintainers: list[User],
        targets: set[str],
        arch: set[str],
    ) -> None:
        self.autoupdate = autoupdate
        self.maintainers = maintainers
        self.targets = targets
        self.arch = arch

    @staticmethod
    def _fill_autoupdate_dataclass(d: dict) -> Autoupdate:
        targets_notify_on_fail = set(d.pop("targets_notify_on_fail", []))
        return Autoupdate(**d, targets_notify_on_fail=targets_notify_on_fail)

    @classmethod
    def _fill_metadata_from_dict(cls, d: dict) -> "MetadataConfig":
        autoupdate = d.get("autoupdate")
        autoupdate_dataclass = None
        if autoupdate is not None:
            autoupdate_dataclass = cls._fill_autoupdate_dataclass(autoupdate)

        maintainers = cls._check_for_mandatory_key(d, "maintainers", "metadata.yaml")
        users_list = []
        for maintainer_dict in maintainers:
            maintainer = cls._check_for_mandatory_key(
                maintainer_dict, "user", "metadata.yaml", "maintainers.user"
            )
            users_list.append(User(**maintainer))

        targets = cls._check_for_mandatory_key(d, "targets", "metadata.yaml")

        return MetadataConfig(
            autoupdate=autoupdate_dataclass,
            maintainers=users_list,
            targets=set(targets),
            arch=set(d.get("arch", ["x86_64"])),
        )

    @classmethod
    def _load_metadata_config(cls, working_dir: Path) -> Optional["MetadataConfig"]:
        config_file_path = cls.get_config_file_path(working_dir, METADATA_FILE_NAMES)
        if config_file_path is None:
            return None

        with open(config_file_path) as meta_file:
            return cls._fill_metadata_from_dict(safe_load(meta_file.read()))

    @classmethod
    def get_config(cls, working_dir: Optional[Path] = None) -> "MetadataConfig":
        if working_dir is None:
            working_dir = Path(getcwd())

        metadata_data_class = cls._load_metadata_config(working_dir)
        if metadata_data_class is None:
            raise FileNotFoundError("No metadata file found in package")

        return metadata_data_class
