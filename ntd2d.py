import argparse
import git
import pathlib
import shutil
import textwrap
from urllib.parse import urlparse

class NISTtheDocs2Death(object):
    def __init__(self, repo_url, to_path, docs_dir,
                 branch, sha, default_branch, pages_branch="nist-pages",
                 pages_url="https://pages.nist.gov"):
        self.repo_url = repo_url
        self.to_path = pathlib.Path(to_path)
        self.docs_dir = pathlib.Path(docs_dir)
        self.branch = branch
        self.sha = sha
        self.default_branch = default_branch
        self.pages_branch = pages_branch
        self.pages_url = pages_url

        parsed = urlparse(self.repo_url)
        self.repository = pathlib.PurePath(parsed.path).stem

        self.build_dir = self.docs_dir / "_build" / "html"
        
        self.repo = None
        self.working_dir = None
        self.html_dir = None
        self.versions_html = None

    def clone(self):
        self.repo = git.Repo.clone_from(self.repo_url,
                                        to_path=self.to_path,
                                        branch=self.pages_branch,
                                        single_branch=True)

        self.working_dir = pathlib.Path(self.repo.working_dir)
        self.html_dir = self.working_dir / "html"

    def copy_html(self, branch):
        dst = self.html_dir / branch

        # remove any previous directory of that name
        res = self.repo.index.remove(dst.as_posix(), working_tree=True,
                               r=True, ignore_unmatch=True)
        shutil.copytree(self.build_dir, dst)
        self.repo.index.add(dst.as_posix())

    def get_versions(self, from_dir, html_dir):
        link_dir = (pathlib.PurePath("/") / self.repository
                    / html_dir.relative_to(self.working_dir))
        versions = []
        for version in from_dir.glob("*"):
            href = link_dir / version.name / "index.html"
            versions.append(f'<a href="{href}">{version.name}</a>')

        versions = "\n".join(versions)

        # build index.html with available documentation versions
        versions = textwrap.dedent("""\
            <div class="ntd2dwrapper">
            {versions}
            </div>
            """).format(versions=textwrap.indent(versions, "  "))

        return versions

    def get_menu(self):
        # Need an absolute url because this gets included from
        # many different levels
        versions = self.get_iframe(self.versions_html.geturl())
        return textwrap.dedent("""\
            <div class="dropdown">
              <div class="dropdown-content">
                <p>Versions</p>
                {versions}
                <p>Downloads</p>
                <hr>
              </div>
              <button class="dropbtn">v: {branch} ▲</button>"
            </div>
            """).format(versions=textwrap.indent(versions, "    "),
                        branch=self.branch)

    def get_iframe(self, src):
        onload = "this.before((this.contentDocument.body||this.contentDocument).children[0]);this.remove()"
        return textwrap.dedent(f"""
            <!-- Taken from https://www.filamentgroup.com/lab/html-includes/#another-demo%3A-including-another-html-file -->
            <iframe src="{src}" onload="{onload}" ></iframe>
            """)

    def get_index(self):
        """build index.html with available documentation versions
        """
        template_fname = pathlib.Path("_templates/index.html")
        if template_fname.exists():
            with open(template_fname, mode='r') as template_file:
                template = template_fname.read()
        else:
            template = textwrap.dedent("""\
            <!doctype html>
            <html>
            <head>
              <title>{repository} documentation</title>
            </head>
            <body>
              {versions}
            </body>
            </html>
            """)

        # This can be a relative url, because all version should
        # be on the same server
        versions = self.get_iframe(self.versions_html.path)
        versions = textwrap.dedent("""
            <div class="documentation-versions">
            {versions}
            </div>
            """).format(versions=textwrap.indent(versions, "  "))

        return template.format(versions=textwrap.indent(versions, "  "),
                               repository=self.repository)

    def set_versions_html(self, versions_html):
        full_url = "/".join([self.pages_url,
                             self.repository,
                             str(versions_html.relative_to(self.working_dir))])

        self.versions_html = urlparse(full_url)

    def write_nojekyll(self):
        # jekyll conflicts with sphinx' underlined directories and files
        nojekyll = self.working_dir / ".nojekyll"
        nojekyll.touch()
        self.repo.index.add(nojekyll)

    def write_global_versions(self):
        includes = self.working_dir / "_includes"
        includes.mkdir(exist_ok=True)
        versions_html = includes / "ntd2d_versions.html"
        with open(versions_html, mode='w') as version_file:
            version_file.write(self.get_versions(from_dir=self.build_dir,
                                                 html_dir=self.html_dir))
        self.repo.index.add(versions_html)

        self.set_versions_html(versions_html)

    def write_local_versions(self):
        static = self.html_dir / self.branch / "_static"
        static.mkdir(exist_ok=True)
        menu_html = static / "ntd2d_versions.html"
        with open(menu_html, mode='w') as menu_file:
            menu_file.write(self.get_menu())
        self.repo.index.add(menu_html)

    def write_index_html(self):
        index_html = self.working_dir / "index.html"
        with open(index_html, mode='w') as index_file:
            index_file.write(self.get_index())
        self.repo.index.add(index_html)

    def commit(self):
        if len(self.repo.index.diff("HEAD")) > 0:
            # GitPython will make an empty commit if no changes,
            # so only commit if things have actually changed
            message = f"Update documentation for {self.branch}@{self.sha}"
            author = git.Actor("GitHub Action", "action@github.com")
            self.repo.index.commit(message=message, author=author)

    def update_pages(self):
        self.clone()

        # replace any built documents in directory named for current branch
        self.copy_html(branch=self.branch)

        # replace any built documents in latest/
        # (but only do this for default branch of repo)
        if self.branch == self.default_branch:
            self.copy_html(branch="latest")

            # TODO: stable?

        self.write_nojekyll()
        self.write_global_versions()
        self.write_local_versions()
        self.write_index_html()

        self.commit()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
                        prog='NistTheDocs2Death',
                        description='Update nist-pages branch based on sphinx builds')

    parser.add_argument('repo_url')
    parser.add_argument('to_path')
    parser.add_argument('docs_dir')
    parser.add_argument('branch')
    parser.add_argument('sha')
    parser.add_argument('default_branch')
    parser.add_argument('pages_branch')
    parser.add_argument('pages_url')

    args = parser.parse_args()

    ntd2d = NISTtheDocs2Death(repo_url=args.repo_url,
                              to_path=args.to_path,
                              docs_dir=args.docs_dir,
                              branch=args.branch,
                              sha=args.sha,
                              default_branch=args.default_branch,
                              pages_branch=args.pages_branch,
                              pages_url=args.pages_url)
    ntd2d.update_pages()