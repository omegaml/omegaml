from pathlib import Path
from datetime import datetime
from sphinx_polyversion import *
from sphinx_polyversion.git import *
from sphinx_polyversion.pyvenv import Poetry
from sphinx_polyversion.sphinx import SphinxBuilder

#: Regex matching the branches to build docs for
BRANCH_REGEX = r".*"

#: Regex matching the tags to build docs for
TAG_REGEX = r".*"

#: Output dir relative to project root
#: !!! This name has to be choosen !!!
OUTPUT_DIR = "../build"

#: Source directory
SOURCE_DIR = "./"

#: Arguments to pass to `poetry install`
POETRY_ARGS = "--only docs --sync"

#: Arguments to pass to `sphinx-build`
SPHINX_ARGS = "-a -v"

#: Mock data used for building local version
MOCK_DATA = {
    "revisions": [
        GitRef("release/0.9", "", "", GitRefType.TAG, datetime.fromtimestamp(0)),
        GitRef("master", "", "", GitRefType.BRANCH, datetime.fromtimestamp(1)),
    ],
    "current": GitRef("local", "", "", GitRefType.BRANCH, datetime.fromtimestamp(2)),
}

# calculate and expose latest version
from sphinx_polyversion.git import refs_by_type

def root_data(driver: DefaultDriver):
    revisions = driver.builds
    tags, branches  = refs_by_type(revisions)
    latest = max(tags or branches)
    return {"revisions": revisions, "latest": latest}

# Load overrides read from commandline to global scope
apply_overrides(globals())

# Determine repository root directory
root = Git.root(Path(__file__).parent)

# Setup driver and run it
src = Path(SOURCE_DIR)  # convert from string
DefaultDriver(
    root,
    OUTPUT_DIR,
    vcs=Git(
        branch_regex=BRANCH_REGEX,
        tag_regex=TAG_REGEX,
        buffer_size=1 * 10**9,  # 1 GB
        predicate=file_predicate([src]),  # exclude refs without source dir
    ),
    builder=SphinxBuilder(src / "sphinx", args=SPHINX_ARGS.split()),
    env=Poetry.factory(args=POETRY_ARGS.split()),
    template_dir=root / src / "templates",
    static_dir=root / src / "static",
    mock=MOCK_DATA,
).run(MOCK)
