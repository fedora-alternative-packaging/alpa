"""
Abstract config class
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, Optional, Any

from alpa.exceptions import AlpaConfException


class Config(ABC):
    @staticmethod
    def get_config_file_path(
        path: Path, allowed_file_names: Iterable[str]
    ) -> Optional[Path]:
        for file_name in allowed_file_names:
            full_file_path = path / file_name
            if full_file_path.is_file():
                return full_file_path

        return None

    @staticmethod
    def _check_for_mandatory_key(
        d: dict,
        mandatory_key: str,
        config_file_name: str,
        different_key_name: Optional[str] = None,
    ) -> Any:
        mandatory_val = d.get(mandatory_key)
        if mandatory_val is None:
            missing = (
                mandatory_key if different_key_name is None else different_key_name
            )
            raise AlpaConfException(
                f"The `{missing}` key is missing in {config_file_name}"
            )

        return mandatory_val

    @classmethod
    @abstractmethod
    def get_config(cls) -> "Config":
        pass
