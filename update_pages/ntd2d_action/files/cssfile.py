import github_action_utils as gha_utils
import textwrap

from .template import Template, PagesTemplate
from .pagesfile import PagesFile

class CSSFile(PagesFile):
    def __init__(self, variant):
        self.variant = variant
        super().__init__(repo=variant.repo)

        self.css = Template(template_path=self.path).read()

    @property
    def path(self):
        return (self.repo.working_dir / "html" / self.variant.name
                / "_static" / "ntd2d.css")

    def get_contents(self):
        gha_utils.debug(f"CSSFile.get_contents()")

        annex = PagesTemplate(working_dir=self.repo.working_dir,
                              name="ntd2d_annex.css").read()

        return annex.format(css=self.css,
                            variant=self.variant.name)
