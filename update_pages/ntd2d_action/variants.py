import github_action_utils as gha_utils
import os
from packaging.version import parse, InvalidVersion
import pathlib
import re
import shutil

from .files import VariantsFile, MenuFile, IndexFile, CSSFile

class Variant:
    def __init__(self, repo, name, true_name=None):
        self.repo = repo
        self.name = name
        if true_name is None:
            self.true_name = name
        else:
            self.true_name = true_name
        self.downloads = {}

        self.dir = repo.working_dir / "html" / name

    def rmdir(self):
        gha_utils.debug(f"{self.name}.rmdir()")
        self.repo.remove(self.dir.as_posix(), working_tree=True,
                         r=True, ignore_unmatch=True)

    def copy_dir(self, src, dst):
        gha_utils.debug(f"{self.name}.copy_dir(src={src}, dst={dst})")
        # remove any previous directory of that name
        self.rmdir()
        shutil.copytree(src, dst)
        self.repo.add(dst.as_posix())

    def copy_html(self, src):
        gha_utils.debug(f"{self.name}.copy_html(src={src})")
        self.copy_dir(src=src, dst=self.dir)

    def copy_file(self, src, dst):
        gha_utils.debug(f"{self.name}.copy_file(src={src}, dst={dst})")
        os.makedirs(dst, exist_ok=True)
        shutil.copy2(src, dst)
        self.repo.add((dst / src.name).as_posix())

    def copy_static_file(self, src):
        self.copy_file(src=src, dst=self.dir / "_static")

    def copy_download_file(self, src, kind):
        gha_utils.debug(f"{self.name}.copy_download_file(src={src}, kind={kind})")
        dst = self.dir / "_downloads"
        if src.exists():
            self.copy_file(src=src, dst=dst)
            self.downloads[kind] = dst / src.name
            gha_utils.debug(f"{self.name}.downloads[{kind}] = {self.downloads[kind]}")

    def get_downloads_html(self):
        link_dir = pathlib.PurePath("/") / self.repo.repository
        downloads = []
        for kind, download in self.downloads.items():
            href = link_dir / download.relative_to(self.repo.working_dir)
            downloads.append(f'<li><a href="{href}">{kind}</a></li>')

        return "\n".join(downloads)

    def clone(self, name, cls=None):
        gha_utils.debug(f"{self.name}.clone({name})")
        if cls is None:
            cls = self.__class__
        clone = cls(repo=self.repo, name=name, true_name=self.true_name)
        # this will clone any files in _static and _downloads, too
        clone.copy_html(src=self.dir)
        dst = clone.dir / "_downloads"
        for kind, download in self.downloads.items():
            clone.downloads[kind] = dst / download.name
            gha_utils.debug(f"{name}.downloads[{kind}] = {clone.downloads[kind]}")

        return clone

    @classmethod
    def from_variant(cls, variant):
        new_variant = cls(variant.repo, variant.name)
        new_variant.downloads = variant.downloads.copy()

        return new_variant

    def __lt__(self, other):
        return self.name < other.name

    @property
    def css_name(self):
        """Escape ref name to satisfy css class naming requirements

        Used to escape characters that are
        - allowed by `man git-check-ref-format`
        - disallowed by https://www.w3.org/International/questions/qa-escapes#cssescapes
        """

        esc = re.escape("!\"#$%&'()+,-./;<=>@]`{|}")
        return re.sub(f"([{esc}])", r"\\\1", self.name)

    def get_html(self):
        link_dir = (pathlib.PurePath("/") / self.repo.repository
                    / self.dir.relative_to(self.repo.working_dir))
        href = link_dir / "index.html"
        return f'<li class="ntd2d_{self.css_name}"><a href="{href}">{self.name}</a></li>'

class Version(Variant):
    """A Variant that satisfies the PEP 440 version specification

    Raises
    ------
    InvalidVersion
        If the name is not parsable by packaging.version
    """
    def __init__(self, repo, name):
        super().__init__(repo=repo, name=name)
        self.version = parse(name)

    def __lt__(self, other):
        if isinstance(other, Version):
            return self.version < other.version
        else:
            return super().__lt__(other)

class VariantCollection(object):
    def __init__(self, repo, current_variant):
        self.repo = repo
        self.current_variant = current_variant

        self.html_dir = repo.working_dir / "html"

        self._latest = None
        self._stable = None
        self._branches = None
        self._versions = None

    @property
    def latest(self):
        gha_utils.debug("VariantCollection.latest")
        if self._latest is None:
            for branch in self.branches:
                gha_utils.debug(f"{branch.name} =?= {self.repo.default_branch}")
                if branch.name == self.repo.default_branch:
                    # replace any built documents in latest/
                    # (but only do this for default branch of repo)
                    self._latest = branch.clone("latest")
                    gha_utils.debug(f"Cloned {branch.name} to {self._latest.name}")
                    break

        return self._latest

    @property
    def stable(self):
        gha_utils.debug("VariantCollection.stable")
        if self._stable is None:
            # replace any built documents in stable/
            # (but only do this for highest non-prerelease version)
            if len(self.stable_versions) > 0:
                self._stable = self.stable_versions[0].clone("stable", cls=Variant)
                gha_utils.debug(f"Cloned {self.stable_versions[0].name} to {self._stable.name}")
            else:
                self._stable = None

        return self._stable

    @property
    def stable_versions(self):
        return [version
                for version in self.versions
                if not version.version.is_prerelease]

    def _calc_branches_and_versions(self):
        gha_utils.debug("VariantCollection._calc_branches_and_versions")

        names = [variant.name for variant in self.html_dir.glob("*")]

        gha_utils.debug(f"self.repo.refs = {self.repo.refs}")

        self._branches = []
        self._versions = []
        for name in names:
            gha_utils.debug(f"{name}")
            if name == self.current_variant.name:
                # re-use existing variant
                try:
                    # Cast to a Version if it's a PEP 440 version.
                    # Retain the string literal for the tag or branch,
                    # but use the Version for sorting.
                    variant = Version.from_variant(variant=self.current_variant)
                    gha_utils.debug(f"Version({variant.name})")
                except InvalidVersion:
                    variant = self.current_variant
                    gha_utils.debug(f"Variant({variant.name})")
            else:
                try:
                    # Check if it's a PEP 440 version.
                    # Retain the string literal for the tag or branch,
                    # but use the Version for sorting.
                    variant = Version(repo=self.repo, name=name)
                    gha_utils.debug(f"Version({variant.name})")
                except InvalidVersion:
                    variant = Variant(repo=self.repo, name=name)
                    gha_utils.debug(f"Variant({variant.name})")

            if variant.name in ["latest", "stable"]:
                continue

            gha_utils.debug(f"variant.name = {variant.name}")
            gha_utils.debug(f"self.current_variant.name = {self.current_variant.name}")
            gha_utils.debug(f"self.repo.refs")
            for ref in self.repo.refs:
                gha_utils.debug(f"...{ref}")
            gha_utils.debug(f"sself.repo.origin.refs")
            for ref in self.repo.origin.refs:
                gha_utils.debug(f"...{ref}")

            if (variant.name != self.current_variant.name
                and variant.name not in self.repo.refs
                and variant.name not in self.repo.origin.refs):
                # This variant has been removed from the repository,
                # so remove the corresponding docs.
                # current_variant may correspond to a PR, which
                # won't be listed in the refs.
                gha_utils.debug(f"Deleting {variant.name}")
                variant.rmdir()
            elif isinstance(variant, Version):
                gha_utils.debug(f"Appending version {variant.name}")
                self._versions.append(variant)
            else:
                gha_utils.debug(f"Appending branch {variant.name}")
                self._branches.append(variant)
        self._branches.sort()
        self._versions.sort(reverse=True)

    @property
    def branches(self):
        if self._branches is None:
            self._calc_branches_and_versions()

        return self._branches

    @property
    def versions(self):
        if self._versions is None:
            self._calc_branches_and_versions()

        return self._versions

    @property
    def variants(self):
        """Collect tags and versions with documentation
        """
        # variants = ["v1.0.0", "stables", "1.2.3", "latest", "4b1",
        #             "0.2", "neat_idea", "doesn't_work", "experiment"]

        variants = []
        for variant in [self.latest, self.stable]:
            if variant is not None:
                variants.append(variant)
        variants = variants + self.versions + self.branches

        return variants

    def get_html(self, items=None):
        if items is None:
            items = self.variants
        link_dir = (pathlib.PurePath("/") / self.repo.repository
                    / self.html_dir.relative_to(self.repo.working_dir))
        variants = []
        for variant in items:
            variants.append(variant.get_html())

        return "\n".join(variants)

    def get_versions_html(self):
        return self.get_html(items=self.versions)

    def get_all_versions_html(self):
        latest_and_stable = []
        for variant in [self.latest, self.stable]:
            if variant is not None:
                latest_and_stable.append(variant)
        return self.get_html(items=latest_and_stable + self.versions)

    def get_branches_html(self):
        return self.get_html(items=self.branches)

    def get_latest_html(self):
        if self.latest is not None:
            return self.latest.get_html()
        else:
            return ""

    def get_stable_html(self):
        if self.stable is not None:
            return self.stable.get_html()
        else:
            return ""

    def write_files(self, pages_url):
        gha_utils.debug(f"VariantCollection.write_files(pages_url={pages_url})")
        variants_file = VariantsFile(repo=self.repo,
                                     variants=self,
                                     pages_url=pages_url)
        variants_file.write()

        url = variants_file.get_url()

        # Need an absolute url because this gets included from
        # many different levels
        for variant in [self.latest, self.stable, self.current_variant]:
            if variant is not None:
                MenuFile(variant=variant,
                         variants_url=url.geturl()).write()
                CSSFile(variant=variant).write()


        # This can be a relative url, because all variants should
        # be on the same server
        IndexFile(repo=self.repo, variants_url=url.path).write()