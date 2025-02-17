"""
File for really long messages.
"""

NO_GH_API_KEY_FOUND = (
    "No GitHub API key found. Please set the {token} environment variable and"
    " pass the GitHub API token to it or set it in alpa.yaml config file. \n"
    "For more information please see (link TODO)"
)

NO_PERMISSION_FOR_ALPA_REPO = (
    "You don't have write permission to this repository. Please fork this Alpa "
    "repository and work with your fork. Cloning a fork repo is done with "
    "`--fork` flag. e.g. `alpa clone --fork my-fork-repo`"
)
CLONED_REPO_IS_NOT_FORK = (
    "You are trying to clone repository which is not a fork! Clone a fork "
    "repository or do the clone command without `--fork` flag."
)
CLONED_REPO_IS_FORK = (
    "The url of GitHub repository is a fork. Please provide repository which "
    "is not a forked form Alpa repository or specify the clone command with "
    "the `--fork` flag."
)

NO_WRITE_ACCESS_ERR = (
    "You don't have write access to this repository. If you "
    "want to create new package, please use `alpa request-package "
    "[PACKAGE NAME]` command instead."
)

NOT_IN_PREDEFINED_STATE = (
    "Repository is not in predefined state. Seems like someone "
    "was playing with it. Please see TODO LINK to return this repo "
    "back to its predefined state."
)

RETURNING_CLONE_URL_MSG = (
    "User {user} does not have access to {repo} repository. "
    "Using https url for cloning instead of ssh url."
)

NO_PRE_COMMIT = (
    "pre-commit is not installed! Please install " "it via `pip install pre-commit`"
)
