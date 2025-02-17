"""
Class for local cli config
"""

import logging
from os.path import isfile
from pathlib import Path
from typing import Optional

from yaml import safe_load

from alpa.constants import CONFIG_FILE_LOCATIONS


logger = logging.getLogger(__name__)


class AlpaLocalConfig:
    def __init__(self, gh_api_token: str) -> None:
        self.gh_api_token = gh_api_token

    @staticmethod
    def _get_config_file_path() -> Optional[Path]:
        for location in CONFIG_FILE_LOCATIONS:
            expanded_path = Path(location).expanduser()
            if isfile(str(expanded_path)):
                logger.info(f"Config file found in {str(expanded_path)}")
                return expanded_path

        logger.info("No config file found for local alpa")
        return None

    @classmethod
    def get_config(cls, repo_name: str) -> Optional["AlpaLocalConfig"]:
        cfg_file_path = cls._get_config_file_path()
        if cfg_file_path is None:
            return None

        with open(cfg_file_path) as alpa_cfg_file:
            config_dict = safe_load(alpa_cfg_file)

        for item in config_dict["api_keys"]:
            if item["repo"]["name"] == repo_name:
                return AlpaLocalConfig(gh_api_token=item["repo"]["key"])

        return None
