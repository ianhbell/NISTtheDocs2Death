#!/usr/bin/env python3
import github_action_utils as gha_utils
import os
import pathlib
import subprocess

from ntd2d_action.repository import Repository
from ntd2d_action.sphinxdocs import SphinxDocs


def main():
    action = os.environ['INPUT_ACTION']

    if action == 'update_pages':
        if os.environ['INPUT_SEPARATED-LAYOUT'] == 'true':
            docs = SphinxDocs(docs_dir=os.environ['INPUT_DOCS-FOLDER'],
                              build_rel="build")
        else:
            docs = SphinxDocs(docs_dir=os.environ['INPUT_DOCS-FOLDER'],
                              build_rel="_build")
        repo = Repository(server_url=os.environ['GITHUB_SERVER_URL'],
                          repository=os.environ['GITHUB_REPOSITORY'],
                          branch=os.environ['INPUT_PAGES-BRANCH'],
                          default_branch=os.environ['INPUT_DEFAULT-BRANCH'],
                          docs=docs,
                          pages_url=os.environ['INPUT_PAGES-URL'])

        repo.update_pages(branch=os.environ['SANITIZED_REF_NAME'],
                          sha=os.environ['GITHUB_SHA'])

        gha_utils.warning(f"separated-layout = {os.environ['INPUT_SEPARATED-LAYOUT']}")

        gha_utils.set_output("borged-docs-folder", os.environ['INPUT_DOCS-FOLDER'])
    elif action == 'borg_the_docs':
        # Install any packages needed for Sphinx
        # Adapted from https://github.com/ammaraskar/sphinx-action/blob/master/sphinx_action/action.py#LL102C1-L105C1
        # [Apache-2.0](https://spdx.org/licenses/Apache-2.0.html)
        docs_dir = pathlib.Path(os.environ['INPUT_DOCS-FOLDER'])
        docs_requirements = docs_dir / "requirements.txt"
        if docs_requirements.is_file():
            gha_utils.debug(f"pip installing")
            subprocess.check_call(["pip", "install", "-r", docs_requirements.as_posix()])

        gha_utils.warning(f"separated-layout = {os.environ['INPUT_SEPARATED-LAYOUT']}")

        # Modify the Sphinx theme
        # This needs to be a subprocess so that it sees packages installed above
        subprocess.check_call(["/borg_the_docs.py"])

if __name__ == "__main__":
    main()
