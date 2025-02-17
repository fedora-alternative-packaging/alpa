"""
These commands need GH API token.
"""

from os import getcwd
from pathlib import Path

import click

from alpa.repository.branch import AlpaRepoBranch


pkg_name = click.argument("name", type=str)


@click.command("create")
@pkg_name
def create(name: str) -> None:
    """Create new package"""
    AlpaRepoBranch(Path(getcwd())).create_package(name)


@click.command("delete")
@pkg_name
def delete(name: str) -> None:
    """Request deleting existing package"""
    AlpaRepoBranch(Path(getcwd())).request_package_delete(name)


@click.command("request-package")
@pkg_name
def request_package(name: str) -> None:
    """Request new branch for new package in Alpa repo"""
    AlpaRepoBranch(Path(getcwd())).request_package(name)
