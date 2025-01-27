import contextlib
import github_action_utils as gha_utils
import os
import pathlib

from .file import File


# By [Lukas](https://stackoverflow.com/users/911441/lukas)
# [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/)
# https://stackoverflow.com/a/42441759/2019542
@contextlib.contextmanager
def _working_directory(path):
    """Changes working directory and returns to previous on exit."""
    prev_cwd = pathlib.Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev_cwd)

class ConfFile(File):
    """Sphinx configuration file."""

    def __init__(self, source_dir):
        self.source_dir = pathlib.Path(source_dir)
        self.theme = None
        self._code = None
        self._configuration = None

    @property
    def configuration(self):
        """Text of configuration file."""

        if self._configuration is None:
            self._configuration = self.read()
        return self._configuration

    @property
    def exclude_patterns(self):
        return self.configuration.get("exclude_patterns", [])

    @property
    def html_theme(self):
        """html_theme_ Sphinx configuration value.

        .. _html_theme: https://www.sphinx-doc.org/en/master/usage/configuration.html#confval-html_theme
        """
        return self.configuration.get("html_theme", "default")

    @property
    def html_theme_path(self):
        """html_theme_path_ Sphinx configuration value.

        .. _html_theme_path: https://www.sphinx-doc.org/en/master/usage/configuration.html#confval-html_theme_path
        """
        return self.configuration.get("html_theme_path", [])

    @property
    def language(self):
        """language_ Sphinx configuration value.

        .. _language: https://www.sphinx-doc.org/en/master/usage/configuration.html#confval-language
        """
        return self.configuration.get("language", "en")

    @property
    def original_contents(self):
        if self._code is None:
            with self.path.open(mode='r') as f:
                self._code = f.read()

        return self._code

    @property
    def path(self):
        return self.source_dir / "conf.py"

    @property
    def project(self):
        """project_ Sphinx configuration value.

        .. _project: https://www.sphinx-doc.org/en/master/usage/configuration.html#confval-project
        """
        return self.configuration["project"]

    @property
    def theme_path(self):
        return self.source_dir / "_themes"

    def read(self):
        """Evaluate Sphinx configuration values.

        The Sphinx docs says that it |readconfdoc|_.
        `It doesn't <https://github.com/sphinx-doc/sphinx/blob/2c83af0aab7080e0b78d4a16981eed878b2cac4c/sphinx/config.py#L353>`_.

        .. |readconfdoc|     replace:: reads :file:`conf.py` with  :func:`importlib.import_module`
        .. _readconfdoc:     https://www.sphinx-doc.org/en/master/usage/configuration.html#module-conf

        Returns
        -------
        namespace : dict
          Configuration values.
        """
        namespace = {}
        namespace['__file__'] = self.path.resolve().as_posix()

        code = compile(self.original_contents, self.path, 'exec')

        with _working_directory(self.source_dir):
            exec(code, namespace)  # NoQA: S102

        return namespace

    def get_contents(self):
        return self.original_contents
