
import os
from pathlib import Path
from ..ninja_syntax import Writer

NEWLIB_CYGWIN_SITE = "https://github.com/cygwin/cygwin/archive/refs/tags"
CYGWIN_MIRROR_x86 = "https://mirrors.kernel.org/sourceware/cygwin-archive/20221123"
CYGWIN_MIRROR_x86_64 = "https://mirrors.kernel.org/sourceware/cygwin"
CYGWIN_SITE = "https://cygwin.com"

class Cygwin:
    target = str,
    version = str,

    def __init__(self, target: str, version: str) -> None:
        self.target = target
        self.version = version

    def arch(self) -> str:
        arch = self.target.split("-")[0]

        if arch in ["x86_64", "amd64", "x64"]:
            return "x86_64"
        elif (arch.startswith("i") and arch.endswith("86")) or arch == "x86":
            return "x86"
        else:
            return arch

    def write_step_variables(self, w: Writer) -> None:
        arch = self.arch()
        mirror_site = CYGWIN_MIRROR_x86_64

        if arch == "x86":
            mirror_site = CYGWIN_MIRROR_x86

        w.variable("cygwin_mirror_site", mirror_site)
        w.newline()

        w.variable("root_dir", str(Path(".").absolute().joinpath("cygwin")).replace("\\", "/"))
        w.variable("download_dir", "downloads")
        w.variable("cygwin_install_dir", "$download_dir/cygwin")
        w.newline()

        w.variable("setup_file", f"$download_dir/setup-{arch}.exe")
        w.variable("newlib_cygwin_tarball", f"$download_dir/cygwin-cygwin-{self.version}.tar.gz")
        w.newline()

    def write_step_download_files(self, w: Writer) -> None:
        w.rule(
            "download-file",
            "curl -Lo $out $url",
            description="Downloading $url",
        )
        w.newline()

        w.build(
            "$setup_file",
            "download-file",
            pool="console",
            variables={
                "url": f"{CYGWIN_SITE}/setup-{self.arch()}.exe"
            },
        )
        w.newline()

        w.build(
            "$newlib_cygwin_tarball",
            "download-file",
            pool="console",
            variables={
                "url": f"{NEWLIB_CYGWIN_SITE}/cygwin-{self.version}.tar.gz"
            },
        )
        w.newline()

    def write_step_install_cygwin(self, w: Writer) -> None:
        arch = self.target.split("-")[0]

        packages = [
            "autoconf",
            "automake",
            "busybox",
            "cocom",
            "cygutils-extra",
            "dblatex",
            "dejagnu",
            "docbook-xml45",
            "docbook-xsl",
            "docbook2X",
            "gcc-g++",
            "gettext-devel",
            "libiconv",
            "libiconv-devel",
            "libzstd-devel",
            "make",
            f"mingw64-{arch}-gcc-g++",
            f"mingw64-{arch}-zlib",
            "patch",
            "perl",
            "python39-lxml",
            "python39-ply",
            "texlive-collection-fontsrecommended",
            "texlive-collection-latexrecommended",
            "texlive-collection-pictures",
            "xmlto",
            "zlib-devel",
        ]

        # https://github.com/cygwin/cygwin-install-action/blob/master/action.yml
        # https://github.com/cygwin/cygwin/blob/main/.github/workflows/cygwin.yml
        w.rule(
            "install-cygwin",
            "$setup_file -qgNnO "
            "-l $root_dir/$cygwin_install_dir/cache "
            "-R $root_dir/$cygwin_install_dir "
            "-s $cygwin_mirror_site "
            f'-P {",".join(packages)} '
             + ("--allow-unsupported-windows" if self.arch() == "x86" else ""),
            description="Installing cygwin at $cygwin_install_dir",
        )
        w.newline()
        w.build(
            "$cygwin_install_dir",
            "install-cygwin",
            implicit=["$setup_file"],
            pool="console",
        )
        w.newline()

    def ninja(self):
        if not Path("cygwin").exists():
            os.mkdir("cygwin")

        print("Writing cygwin/build.ninja")
        with open("cygwin/build.ninja", "w") as f:
            w = Writer(f)
            self.write_step_variables(w)
            self.write_step_download_files(w)
            self.write_step_install_cygwin(w)
