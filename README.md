# NISTtheDocs2Death Action

This is a GitHub action that uses sphinx to build documentation and then
host on <https://pages.nist.gov> as an approximation of
[ReadTheDocs](https://readthedocs.org).

## Usage

- [Configure your repo for publishing on `pages.nist.gov`](https://github.com/usnistgov/pages-root/wiki/Configuring-your-repo-for-publishing-on-pages.nist.gov)
- Create a workflow, such as `.github/workflows/NISTtheDocs2Death.yml`:

    ```yaml
    name: "Build Documentation"

    on: [push, pull_request, delete]

    jobs:
      docs:
        runs-on: ubuntu-latest
        steps:
          - uses: usnistgov/NISTtheDocs2Death@main
            with:
              docs-folder: docs/
    ```
