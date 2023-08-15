import argparse
import os
import sys
import shutil
from pathlib import Path
from typing import Optional, List
from . import cli
from .libc import LibC
from .ninja_syntax import Writer
from .patches import Patch


class Args:
    no_patches = (bool,)
    prefix = (str,)

    host = (Optional[str],)
    target = (str,)

    cc = (str,)
    cxx = (str,)
    cc_build = (str,)
    cxx_build = (str,)
    cc_flags = (str,)
    cxx_flags = (str,)
    ld_flags = (str,)
    enable_cache = (bool,)

    binutils_flags = (List[str],)
    gcc_flags = (List[str],)
    gcc_with_isl = (bool,)
    libc = (LibC,)
    linux_headers = (bool,)

    binutils_version = (str,)
    cygwin_version = (str,)
    gcc_version = (str,)
    glibc_version = (str,)
    gmp_version = (str,)
    isl_version = (str,)
    linux_version = (str,)
    mpc_version = (str,)
    mpfr_version = (str,)
    mingw_w64_version = (str,)
    musl_version = (str,)

    _make = (str,)

    def __init__(self, args: argparse.Namespace) -> None:
        self.no_patches = args.no_patches

        self.host = args.host
        self.target = args.target

        self.cc = args.cc
        self.cxx = args.cxx
        self.cc_build = args.cc_build
        self.cxx_build = args.cxx_build
        self.cc_flags = args.cc_flags
        self.cxx_flags = args.cxx_flags
        self.ld_flags = args.ld_flags
        self.enable_cache = args.enable_cache

        self.binutils_flags = [
            "--disable-multilib",
            "--disable-werror",
            "--libdir=/lib",
            "--prefix=",
            "--target=$target",
            "--with-sysroot=/$target",
        ]

        if self.host:
            self.binutils_flags.append("--host=$host")

        if not args.no_default_configure:
            match args.libc:
                case LibC.MUSL:
                    self.binutils_flags.extend([
                        "--disable-separate-code",
                        "--enable-deterministic-archives",
                    ])

        if args.binutils_flags:
            self.binutils_flags.extend(args.binutils_flags.split(" "))

        self.gcc_flags = [
            "--disable-bootstrap",
            # https://wiki.musl-libc.org/open-issues.html#Sanitizer_compatibility
            "--disable-libsanitizer",
            "--disable-multilib",
            "--disable-werror",
            "--enable-languages=c,c++",
            "--libdir=/lib",
            "--prefix=",
            "--target=$target",
            "--with-build-sysroot=$build_sysroot_dir",
            "--with-sysroot=/$target",
        ]

        if self.host:
            self.gcc_flags.append("--host=$host")

        if not args.no_default_configure:
            match args.libc:
                case LibC.MSVCRT | LibC.NEWLIB_CYGWIN | LibC.UCRT:
                    self.gcc_flags.append("--enable-threads=posix")

                    # https://github.com/brechtsanders/winlibs_mingw/issues/20
                    arch = self.target.split("-")[0]

                    if arch.startswith("i") and arch.endswith("86"):
                        self.gcc_flags.extend([
                            "--disable-sjlj-exceptions",
                            "--with-dwarf2",
                        ])

                case LibC.MUSL:  # https://github.com/richfelker/musl-cross-make/blob/master/litecross/Makefile
                    self.gcc_flags.extend([
                        "--disable-assembly",
                        "--disable-gnu-indirect-function",
                        "--disable-libmpx",
                        "--disable-libmudflap",
                        "--enable-initfini-array",
                        "--enable-libstdcxx-time=rt",
                        "--enable-tls",
                    ])

            if "fdpic" in self.target:
                self.gcc_flags.append("--enable-fdpic")

            if self.target.startswith("x86_64") and self.target.endswith("x32"):
                self.gcc_flags.append("--with-abi=x32")

            if "powerpc64" in self.target:
                self.gcc_flags.append("--with-abi=elfv2")

            if "mips64" in self.target or "mipsisa64" in self.target:
                if "n32" in self.target:
                    self.gcc_flags.append("--with-abi=n32")
                else:
                    self.gcc_flags.append("--with-abi=64")

            if "s390x" in self.target:
                self.gcc_flags.append("--with-long-double-128")

            if self.target.endswith("sf"):
                self.gcc_flags.append("--with-float=soft")
            elif self.target.endswith("hf"):
                self.gcc_flags.append("--with-float=hard")

        if args.gcc_flags:
            self.gcc_flags.extend(args.gcc_flags.split(" "))

        self.gcc_with_isl = args.gcc_with_isl
        self.libc = args.libc
        self.linux_headers = args.linux_headers

        self.binutils_version = args.binutils_version
        self.cygwin_version = args.cygwin_version
        self.gcc_version = args.gcc_version
        self.glibc_version = args.glibc_version
        self.gmp_version = args.gmp_version
        self.isl_version = args.isl_version
        self.linux_version = args.linux_version
        self.mpc_version = args.mpc_version
        self.mpfr_version = args.mpfr_version
        self.mingw_w64_version = args.mingw_w64_version
        self.musl_version = args.musl_version

        self._make = "make"

    def dependencies_summary(self) -> None:
        print("\nDependencies:")
        print(f"  binutils {self.binutils_version}")
        print(f"       gcc {self.gcc_version}")
        print(f"       gmp {self.gmp_version}")

        if self.gcc_with_isl:
            print(f"       isl {self.isl_version}")

        if self.linux_headers:
            print(f"     linux {self.linux_version}")

        print(f"       mpc {self.mpc_version}")
        print(f"      mpfr {self.mpfr_version}")

        match self.libc:
            case LibC.CYGWIN_NEWLIB:
                print(f"    cygwin {self.cygwin_version}")
                print(f" mingw-w64 {self.mingw_w64_version}\n")
            case LibC.GLIBC:
                print(f"     glibc {self.glibc_version}\n")
            case LibC.MSVCRT | LibC.UCRT:
                print(f" mingw-w64 {self.mingw_w64_version}\n")
            case LibC.MUSL:
                print(f"      musl {self.musl_version}\n")

    @staticmethod
    def _exists(cmd: str, msg: str) -> bool:
        path = shutil.which(cmd)
        if path is not None:
            print(f"{msg}: {cmd} ({path})")
            return True
        else:
            print(f"{msg}: {cmd} (doesn't exists)")
            return False

    def try_get_tools(self):
        failed = False

        if not self._exists(self.cc_build, "Checking for build C compiler"):
            failed = True
        if not self._exists(self.cxx_build, "Checking for build C++ compiler"):
            failed = True

        if self.host:
            self.cc = self.cc.replace("$host", self.host).lstrip("-")
            self.cxx = self.cxx.replace("$host", self.host).lstrip("-")

            if not self._exists(self.cc, "Checking for host C compiler"):
                failed = True
            if not self._exists(self.cxx, "Checking for host C++ compiler"):
                failed = True
        else:
            self.cc = self.cc_build
            self.cxx = self.cxx_build

        if self.enable_cache:
            ccache = self._exists("ccache", "Checking for tool ccache")
            sccache = None
            wrapper = None

            if ccache:
                wrapper = "ccache"
            else:
                sccache = self._exists("sccache", "Checking for tool sccache")

                if sccache:
                    wrapper = "sccache"

            if wrapper:
                print(f"Using {wrapper} as compiler wrapper")
                self.cc = f"{wrapper} {self.cc}"
                self.cxx = f"{wrapper} {self.cxx}"
                self.cc_build = f"{wrapper} {self.cc_build}"
                self.cxx_build = f"{wrapper} {self.cxx_build}"

        if self._exists("make", "Checking for tool make"):
            self._make = "make"
        elif self._exists("gmake", "Checking for tool gmake"):
            self._make = "gmake"
        elif self._exists("mingw32-make", "Checking for tool mingw32-make"):
            self._make = "mingw32-make"
        else:
            failed = True

        if not self._exists("curl", "Checking for tool curl"):
            failed = True

        if not self._exists("patch", "Checking for tool patch"):
            failed = True

        if not self._exists("tar", "Checking for tool tar"):
            failed = True

        return failed

    def is_cross(self) -> bool:
        self.host is None

    def libc_version(self) -> str:
        match self.libc:
            case LibC.CYGWIN_NEWLIB:
                return self.cygwin_version
            case LibC.GLIBC:
                return self.glibc_version
            case LibC.MSVCRT | LibC.UCRT:
                return self.mingw_w64_version
            case LibC.MUSL:
                return self.musl_version

    def write_variables(self, w: Writer) -> None:
        w.comment("this file is generated from configure.py")
        w.newline()
        w.variable("target", self.target)
        w.variable("host", self.host)
        w.newline()

        w.variable("cc", self.cc)
        w.variable("cxx", self.cxx)

        if not self.is_cross():
            w.variable("cc_build", self.cc_build)
            w.variable("cxx_build", self.cxx_build)

        w.variable("cc_flags", self.cc_flags)
        w.variable("cxx_flags", self.cxx_flags)
        w.variable("ld_flags", self.ld_flags)
        w.newline()

        w.variable("binutils_version", self.binutils_version)
        w.variable("gcc_version", self.gcc_version)
        w.variable("gmp_version", self.gmp_version)

        if self.gcc_with_isl:
            w.variable("isl_version", self.isl_version)

        w.variable("linux_version", self.linux_version)
        w.variable("mpc_version", self.mpc_version)
        w.variable("mpfr_version", self.mpfr_version)

        match self.libc:
            case LibC.MSVCRT | LibC.NEWLIB_CYGWIN | LibC.UCRT:
                w.variable("mingw_w64_version", self.mingw_w64_version)
            case _:
                w.variable(f"{self.libc.name()}_version", self.libc_version())

        w.newline()

        w.variable("gnu_site", "https://ftpmirror.gnu.org")

        if self.gcc_with_isl:
            w.variable("isl_site", "https://libisl.sourceforge.io")

        w.variable(
            "linux_site", "https://cdn.kernel.org/pub/linux/kernel/v6.x"
        )

        match self.libc:
            case LibC.MSVCRT | LibC.NEWLIB_CYGWIN | LibC.UCRT:
                w.variable("mingw_w64_site",
                           "https://sourceforge.net/projects/mingw-w64/files/mingw-w64/mingw-w64-release")
            case LibC.MUSL:
                w.variable("musl_site", "https://www.musl-libc.org")

        w.newline()
        w.variable("download_cmd", "curl -L -o")
        w.variable(
            "make_cmd",
            f"{self._make} -j {os.cpu_count()} MULTILIB_OSDIRNAMES= ac_cv_prog_lex_root=lex.yy",
            # INFO_DEPS= infodir= MAKEINFO=false
        )
        w.newline()
        w.comment("edit below this line carefully")
        w.newline()

        w.variable("root_dir", Path(".").absolute())
        w.variable("build_dir", "build")
        w.variable("build_sysroot_dir", "$root_dir/$build_dir/sysroot")
        w.variable("build_targets_dir", "$build_dir/targets")
        w.variable("download_dir", "downloads")
        w.variable("install_dir", "$root_dir/toolchain")
        w.newline()

        env_vars = '$env_path CC="$cc" CXX="$cxx" CFLAGS="$cc_flags" CXXFLAGS="$cxx_flags" LDFLAGS="$ld_flags"'

        if not self.is_cross():
            env_vars += ' CC_FOR_BUILD="$cc_build" CXX_FOR_BUILD="$cxx_build"'

        w.variable("env_path", 'PATH="$install_dir/bin:$$PATH"')
        w.variable("env_vars", env_vars)
        w.newline()

    def write_step_download_extract(self, w: Writer, step_no: int) -> None:
        w.comment(f"step {step_no} - download, extract and patch archives")
        w.newline()

        download_targets = ["binutils", "gcc", "gmp"]

        if self.gcc_with_isl:
            download_targets.append("isl")

        if self.linux_headers:
            download_targets.append("linux")

        download_targets.extend(["mpc", "mpfr"])

        if self.libc.requires_mingw_w64():
            download_targets.append("mingw_w64")
        else:
            download_targets.append(self.libc.name())

        for name in download_targets:
            compression = "xz"

            if name in ["mpc", "musl"]:
                compression = "gz"
            elif name == "mingw_w64":
                compression = "bz2"

            w.variable(
                f"{name}_tarball",
                f"$download_dir/{name.replace('_', '-')}-${name}_version.tar.{compression}",
            )

        w.newline()

        for name in download_targets:
            if name == "mingw_w64":
                w.variable("mingw_w64_dir",
                           "$build_dir/mingw-w64-v$mingw_w64_version")
            else:
                w.variable(f"{name}_dir", f"$build_dir/{name}-${name}_version")

        w.newline()
        w.rule(
            "download-tarball",
            "$download_cmd $out $url",
            description="Downloading $url",
        )
        w.newline()
        w.rule(
            "extract-tar",
            "rm -rf $extracted_dir && tar -C $build_dir -x -$compression -f $in && cd $extracted_dir && $patch_command && touch ../../$out",
            description="Extracting $in",
        )
        w.newline()
        w.build(
            "$binutils_tarball",
            "download-tarball",
            pool="console",
            variables={
                "url": "$gnu_site/binutils/binutils-$binutils_version.tar.xz"
            },
        )
        w.newline()
        w.build(
            "$gcc_tarball",
            "download-tarball",
            pool="console",
            variables={
                "url": "$gnu_site/gcc/gcc-$gcc_version/gcc-$gcc_version.tar.xz"
            },
        )
        w.newline()
        w.build(
            "$gmp_tarball",
            "download-tarball",
            pool="console",
            variables={"url": "$gnu_site/gmp/gmp-$gmp_version.tar.xz"},
        )
        w.newline()

        if self.gcc_with_isl:
            w.build(
                "$isl_tarball",
                "download-tarball",
                pool="console",
                variables={"url": "$isl_site/isl-$isl_version.tar.xz"},
            )
            w.newline()

        if self.linux_headers:
            w.build(
                "$linux_tarball",
                "download-tarball",
                pool="console",
                variables={"url": "$linux_site/linux-$linux_version.tar.xz"},
            )
            w.newline()

        w.build(
            "$mpc_tarball",
            "download-tarball",
            pool="console",
            variables={"url": "$gnu_site/mpc/mpc-$mpc_version.tar.gz"},
        )
        w.newline()
        w.build(
            "$mpfr_tarball",
            "download-tarball",
            pool="console",
            variables={"url": "$gnu_site/mpfr/mpfr-$mpfr_version.tar.xz"},
        )
        w.newline()

        tarball_name = ""
        url = ""

        match self.libc:
            case LibC.MSVCRT | LibC.NEWLIB_CYGWIN | LibC.UCRT:
                tarball_name = "mingw_w64"
                url = "$mingw_w64_site/mingw-w64-v$mingw_w64_version.tar.bz2"
            case LibC.GLIBC:
                tarball_name = "glibc"
                url = "$gnu_site/glibc/glibc-$glibc_version.tar.xz"
            case LibC.MUSL:
                tarball_name = "musl"
                url = "$musl_site/releases/musl-$musl_version.tar.gz"

        w.build(
            f"${tarball_name}_tarball",
            "download-tarball",
            pool="console",
            variables={"url": url},
        )
        w.newline()

        name_version_tuples = [
            ("binutils", self.binutils_version),
            ("gcc", self.gcc_version),
            ("gmp", self.gmp_version),
        ]

        if self.gcc_with_isl:
            name_version_tuples.append(("isl", self.isl_version))

        if self.linux_headers:
            name_version_tuples.append(("linux", self.linux_version))

        name_version_tuples.extend([
            ("mpc", self.mpc_version),
            ("mpfr", self.mpfr_version),
        ])

        if self.libc.requires_mingw_w64():
            name_version_tuples.append(("mingw_w64", self.mingw_w64_version))
        else:
            name_version_tuples.append((self.libc.name(), self.libc_version()))

        for (name, version) in name_version_tuples:
            compression = "J"
            patch_command = "patch -p 1"

            if name in ["mpc", "musl"]:
                compression = "x"
            if name == "mingw_w64":
                compression = "j"

            if not self.no_patches:
                patch = Patch(name.replace("_", "-"), version)

                if patch.exists():
                    for patch_file in patch.files():
                        patch_command += f" -i ../../{patch_file}"

            if patch_command == "patch -p 1":
                patch_command = "true"

            w.build(
                f"$build_targets_dir/extract-{name}",
                "extract-tar",
                inputs=[f"${name}_tarball"],
                variables={
                    "compression": compression,
                    "extracted_dir": f"${name}_dir",
                    "patch_command": patch_command,
                },
            )
            w.newline()

    def write_step_binutils(self, w: Writer, step_no: int) -> None:
        w.comment(f"step {step_no} - build binutils")
        w.newline()
        w.variable("binutils_build_dir", "$build_dir/binutils-build")
        w.newline()

        w.rule(
            "configure-binutils",
            f'rm -rf $binutils_build_dir && mkdir $binutils_build_dir && cd $binutils_build_dir && $env_vars ../binutils-$binutils_version/configure {" ".join(self.binutils_flags)} && touch ../../$out',
            description="Configuring binutils $binutils_version",
        )
        w.newline()
        w.build(
            "$build_targets_dir/configure-binutils",
            "configure-binutils",
            implicit=["$build_targets_dir/extract-binutils"],
            pool="console",
        )
        w.newline()

        w.rule(
            "build-binutils",
            'cd $binutils_build_dir && $env_vars $make_cmd MAKE="$make_cmd" && touch ../../$out',
            description="Building binutils $binutils_version",
        )
        w.newline()
        w.build(
            "$build_targets_dir/build-binutils",
            "build-binutils",
            implicit=["$build_targets_dir/configure-binutils"],
            pool="console",
        )
        w.newline()

        w.rule(
            "install-binutils",
            'cd $binutils_build_dir && $env_vars $make_cmd install MAKE="$make_cmd" DESTDIR=$install_dir && touch ../../$out',
            description="Installing binutils $binutils_version",
        )
        w.newline()
        w.build(
            "$build_targets_dir/install-binutils",
            "install-binutils",
            implicit=["$build_targets_dir/build-binutils"],
            pool="console",
        )
        w.newline()

    def write_step_sysroot(self, w: Writer, step_no: int) -> None:
        w.comment(f"step {step_no} - create build sysroot dir")
        w.newline()

        w.rule(
            "build-sysroot",
            "rm -rf $build_sysroot_dir && "
            "mkdir -p $build_sysroot_dir/usr/include $build_sysroot_dir/usr/lib $build_sysroot_dir/mingw && "
            "ln -sf $build_sysroot_dir/usr/lib $build_sysroot_dir/usr/lib32 && "
            "ln -sf $build_sysroot_dir/usr/lib $build_sysroot_dir/usr/lib64 && "
            "ln -sf $build_sysroot_dir/usr/include $build_sysroot_dir/include && "
            "ln -sf $build_sysroot_dir/usr/lib $build_sysroot_dir/lib && "
            "ln -sf $build_sysroot_dir/usr/lib $build_sysroot_dir/lib32 && "
            "ln -sf $build_sysroot_dir/usr/lib $build_sysroot_dir/lib64 && "
            "ln -sf $build_sysroot_dir/usr/include $build_sysroot_dir/mingw/include && "
            "ln -sf $build_sysroot_dir/usr/lib $build_sysroot_dir/mingw/lib && "
            "ln -sf $build_sysroot_dir/usr/lib $build_sysroot_dir/mingw/lib32 && "
            "ln -sf $build_sysroot_dir/usr/lib $build_sysroot_dir/mingw/lib64 && "
            "touch $out",
            description="Creating build sysroot dir at $build_sysroot_dir",
        )
        w.newline()
        w.build(
            "$build_targets_dir/build-sysroot",
            "build-sysroot",
        )
        w.newline()

    def write_step_linux_headers(self, w: Writer, step_no: int) -> None:
        w.comment(f"step {step_no} - install linux-headers")
        w.newline()

        # https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/arch
        arch = self.target.split("-")[0]

        if arch.startswith("aarch64"):
            arch = "arm64"
        elif arch.startswith("arm"):
            arch = "arm"
        elif arch.startswith("i") and arch.endswith("86"):
            arch = "x86"
        elif arch.startswith("microblaze"):
            arch = "microblaze"
        elif arch.startswith("mips"):
            arch = "mips"
        elif arch.startswith("or1k"):
            arch = "openrisc"
        elif arch.startswith("powerpc"):
            arch = "powerpc"
        elif arch.startswith("riscv"):
            arch = "riscv"
        elif arch.startswith("s390"):
            arch = "s390"
        elif arch.startswith("sh"):
            arch = "sh"
        elif arch.startswith("x86_64"):
            arch = "x86_64"

        w.variable("arch", arch)
        w.variable("linux_build_dir", "$build_dir/linux-build")
        w.newline()

        w.rule(
            "build-linux-headers",
            "cd $linux_dir && $env_vars $make_cmd ARCH=$arch mrproper && touch ../../$out",
            description="Building linux $linux_version (headers)",
        )
        w.newline()
        w.build(
            "$build_targets_dir/build-linux-headers",
            "build-linux-headers",
            implicit=["$build_targets_dir/extract-linux"],
            pool="console",
        )
        w.newline()

        w.rule(
            "install-linux-headers-sysroot",
            "rm -rf $linux_build_dir && mkdir $linux_build_dir && cd $linux_dir && $env_vars $make_cmd O=$root_dir/$linux_build_dir ARCH=$arch INSTALL_HDR_PATH=$build_sysroot_dir/usr headers_install && touch ../../$out",
            description="Installing linux $linux_version (headers) at $build_sysroot_dir/usr",
        )
        w.newline()
        w.build(
            "$build_targets_dir/install-linux-headers-sysroot",
            "install-linux-headers-sysroot",
            implicit=[
                "$build_targets_dir/build-linux-headers",
                "$build_targets_dir/build-sysroot",
            ],
            pool="console",
        )
        w.newline()

        w.rule(
            "install-linux-headers",
            "rm -rf $linux_build_dir && mkdir $linux_build_dir && cd $linux_dir && $env_vars $make_cmd O=$root_dir/$build_dir/linux-build ARCH=$arch INSTALL_HDR_PATH=$install_dir/$target headers_install && touch ../../$out",
            description="Installing linux $linux_version (headers)",
        )
        w.newline()
        w.build(
            "$build_targets_dir/install-linux-headers",
            "install-linux-headers",
            implicit=["$build_targets_dir/build-linux-headers"],
            pool="console",
        )
        w.newline()

    def write_step_configure_gcc(self, w: Writer, step_no: int) -> None:
        w.comment(f"step {step_no} - configure gcc")
        w.newline()
        w.variable("gcc_build_dir", "$build_dir/gcc-build")
        w.newline()

        w.rule(
            "move-directory",
            "rm -rf $dst_dir && mv $src_dir $dst_dir && touch $out",
            description="Moving $src_dir -> $dst_dir",
        )
        w.newline()

        move_targets = ["gmp"]

        if self.gcc_with_isl:
            move_targets.append("isl")

        move_targets.extend(["mpc", "mpfr"])
        build_targets_move = []

        for name in move_targets:
            w.build(
                f"$build_targets_dir/move-{name}",
                "move-directory",
                implicit=[f"$build_targets_dir/extract-{name}"],
                variables={
                    "src_dir": f"${name}_dir",
                    "dst_dir": f"$gcc_dir/{name}",
                },
            )
            w.newline()
            build_targets_move.append(f"$build_targets_dir/move-{name}")

        w.rule(
            "configure-gcc",
            f'rm -rf $gcc_build_dir && mkdir $gcc_build_dir && cd $gcc_build_dir && $env_vars ../gcc-$gcc_version/configure {" ".join(self.gcc_flags)} && touch ../../$out',
            description="Configuring gcc $gcc_version",
        )
        w.newline()

        deps = ["$build_targets_dir/extract-gcc"]
        deps.extend(build_targets_move)
        deps.extend([
            "$build_targets_dir/install-binutils",
            "$build_targets_dir/build-sysroot",
        ])

        w.build(
            "$build_targets_dir/configure-gcc",
            "configure-gcc",
            implicit=deps,
            pool="console",
        )
        w.newline()

    def write_step_gcc_all_gcc(self, w: Writer, step_no: int) -> None:
        w.comment(f"step {step_no} - build gcc (all-gcc)")
        w.newline()

        deps = ["$build_targets_dir/configure-gcc"]

        if self.libc.is_mingw_w64():
            deps.append("$build_targets_dir/install-mingw-w64-headers-sysroot")

        w.rule(
            "build-gcc-all-gcc",
            'cd $gcc_build_dir && $env_vars $make_cmd all-gcc MAKE="$make_cmd" && touch ../../$out',
            description="Building gcc $gcc_version (all-gcc)",
        )
        w.newline()
        w.build(
            "$build_targets_dir/build-gcc-all-gcc",
            "build-gcc-all-gcc",
            implicit=deps,
            pool="console",
        )
        w.newline()

        w.rule(
            "install-gcc-all-gcc",
            'cd $gcc_build_dir && $env_vars $make_cmd install-gcc DESTDIR=$install_dir MAKE="$make_cmd" && touch ../../$out',
            description="Installing gcc $gcc_version (all-gcc)",
        )
        w.newline()
        w.build(
            "$build_targets_dir/install-gcc-all-gcc",
            "install-gcc-all-gcc",
            implicit=["$build_targets_dir/build-gcc-all-gcc"],
            pool="console",
        )
        w.newline()

    def write_step_mingw_w64_headers(self, w: Writer, step_no: int) -> None:
        w.comment(f"step {step_no} - mingw-w64-headers")
        w.newline()
        w.variable("mingw_w64_headers_build_dir",
                   "$build_dir/mingw-w64-headers-build")
        w.newline()

        flags = [
            "--prefix=",
            "--host=$target",
        ]

        if self.libc.is_cygwin_newlib():
            flags.extend([
                "--enable-w32api",
                "--with-default-msvcrt=ucrt",
            ])
        elif self.libc.is_mingw_w64():
            flags.append(f"--with-default-msvcrt={self.libc.name()}")

        w.rule(
            "configure-mingw-w64-headers",
            "rm -rf $mingw_w64_headers_build_dir && "
            "mkdir $mingw_w64_headers_build_dir && "
            "cd $mingw_w64_headers_build_dir && "
            f'$env_vars ../mingw-w64-v$mingw_w64_version/mingw-w64-headers/configure {" ".join(flags)} && '
            "touch ../../$out",
            description="Configuring mingw-w64 $mingw_w64_version (headers)",
        )
        w.newline()
        w.build(
            "$build_targets_dir/configure-mingw-w64-headers",
            "configure-mingw-w64-headers",
            implicit=["$build_targets_dir/extract-mingw_w64"],
            pool="console",
        )
        w.newline()

        w.rule(
            "install-mingw-w64-headers-sysroot",
            "cd $mingw_w64_headers_build_dir && "
            "$env_vars $make_cmd install DESTDIR=$build_sysroot_dir/usr && "
            "touch ../../$out",
            description="Installing mingw-w64 $mingw_w64_version (headers) at $build_sysroot_dir/usr",
        )
        w.newline()
        w.build(
            "$build_targets_dir/install-mingw-w64-headers-sysroot",
            "install-mingw-w64-headers-sysroot",
            implicit=[
                "$build_targets_dir/configure-mingw-w64-headers",
                "$build_targets_dir/build-sysroot",
            ],
            pool="console",
        )
        w.newline()

        w.rule(
            "install-mingw-w64-headers",
            "cd $mingw_w64_headers_build_dir && "
            "$env_vars $make_cmd install DESTDIR=$install_dir/$target && "
            "touch ../../$out",
            description="Installing mingw-w64 $mingw_w64_version (headers)",
        )
        w.newline()
        w.build(
            "$build_targets_dir/install-mingw-w64-headers",
            "install-mingw-w64-headers",
            implicit=["$build_targets_dir/configure-mingw-w64-headers"],
            pool="console",
        )
        w.newline()

    def write_step_mingw_w64_crt(self, w: Writer, step_no: int) -> None:
        w.comment(f"step {step_no} - mingw-w64-crt")
        w.newline()
        w.variable("mingw_w64_crt_build_dir", "$build_dir/mingw-w64-crt-build")
        w.newline()

        cc = 'CC="${target}-gcc --sysroot=$build_sysroot_dir"'
        flags = [
            "--prefix=",
            "--host=$target",
            "--with-sysroot=$build_sysroot_dir",
        ]

        if self.libc.is_cygwin_newlib():
            flags.extend([
                "--enable-w32api",
                "--with-default-msvcrt=ucrt",
            ])
        elif self.libc.is_mingw_w64():
            flags.append(f"--with-default-msvcrt={self.libc.name()}")

        arch = self.target.split("-")[0]

        if arch == "x86_64":
            flags.extend([
                "--enable-lib64",
                "--disable-lib32",
            ])
        elif arch.startswith("i") and arch.endswith("86"):
            flags.extend([
                "--enable-lib32",
                "--disable-lib64",
            ])

        w.rule(
            "configure-mingw-w64-crt",
            "rm -rf $mingw_w64_crt_build_dir && "
            "mkdir $mingw_w64_crt_build_dir && "
            "cd $mingw_w64_crt_build_dir && "
            f"$env_path {cc} ../mingw-w64-v$mingw_w64_version/mingw-w64-crt/configure {' '.join(flags)} && "
            "touch ../../$out",
            description="Configuring mingw-w64 $mingw_w64_version (crt)",
        )
        w.newline()
        w.build(
            "$build_targets_dir/configure-mingw-w64-crt",
            "configure-mingw-w64-crt",
            implicit=[
                "$build_targets_dir/install-gcc-all-gcc",
                "$build_targets_dir/install-mingw-w64-headers-sysroot",
            ],
            pool="console",
        )
        w.newline()

        w.rule(
            "build-mingw-w64-crt",
            "cd $mingw_w64_crt_build_dir && "
            f'$env_path {cc} $make_cmd MAKE="$make_cmd" && '
            "touch ../../$out",
            description="Building mingw-w64 $mingw_w64_version (crt)",
        )
        w.newline()
        w.build(
            "$build_targets_dir/build-mingw-w64-crt",
            "build-mingw-w64-crt",
            implicit=["$build_targets_dir/configure-mingw-w64-crt"],
            pool="console",
        )
        w.newline()

        w.rule(
            "install-mingw-w64-crt-sysroot",
            "cd $mingw_w64_crt_build_dir && "
            f'$env_path {cc} $make_cmd install DESTDIR=$build_sysroot_dir/usr MAKE="$make_cmd" && '
            "touch ../../$out",
            description="Installing mingw-w64 $mingw_w64_version (crt) at $build_sysroot_dir/usr",
        )
        w.newline()
        w.build(
            "$build_targets_dir/install-mingw-w64-crt-sysroot",
            "install-mingw-w64-crt-sysroot",
            implicit=["$build_targets_dir/build-mingw-w64-crt"],
            pool="console",
        )
        w.newline()

        w.rule(
            "install-mingw-w64-crt",
            "cd $mingw_w64_crt_build_dir && "
            f'$env_path {cc} $make_cmd install DESTDIR=$install_dir/$target MAKE="$make_cmd" && '
            "touch ../../$out",
            description="Installing mingw-w64 $mingw_w64_version",
        )
        w.newline()
        w.build(
            "$build_targets_dir/install-mingw-w64-crt",
            "install-mingw-w64-crt",
            implicit=["$build_targets_dir/build-mingw-w64-crt"],
            pool="console",
        )
        w.newline()

    def write_step_mingw_w64_threads(self, w: Writer, step_no: int) -> None:
        w.comment(f"step {step_no} - mingw-w64-threads")
        w.newline()
        w.variable("mingw_w64_threads_build_dir",
                   "$build_dir/mingw-w64-threads-build")
        w.newline()

        cc = 'CC="${target}-gcc --sysroot=$build_sysroot_dir"'
        flags = [
            "--prefix=",
            "--host=$target",
            "--with-sysroot=$build_sysroot_dir",
            # "--disable-shared",
            # "--enable-static",
        ]

        w.rule(
            "configure-mingw-w64-threads",
            "rm -rf $mingw_w64_threads_build_dir && "
            "mkdir $mingw_w64_threads_build_dir && "
            "cd $mingw_w64_threads_build_dir && "
            f"$env_path {cc} ../mingw-w64-v$mingw_w64_version/mingw-w64-libraries/winpthreads/configure {' '.join(flags)} && "
            "touch ../../$out",
            description="Configuring mingw-w64 $mingw_w64_version (winpthreads)",
        )
        w.newline()
        w.build(
            "$build_targets_dir/configure-mingw-w64-threads",
            "configure-mingw-w64-threads",
            implicit=["$build_targets_dir/install-mingw-w64-crt-sysroot"],
            pool="console",
        )
        w.newline()

        w.rule(
            "build-mingw-w64-threads",
            "cd $mingw_w64_threads_build_dir && "
            f'$env_path {cc} $make_cmd MAKE="$make_cmd" RC="${{target}}-windres -I$build_sysroot_dir/usr/include" && '
            "touch ../../$out",
            description="Building mingw-w64 $mingw_w64_version (winpthreads)",
        )
        w.newline()
        w.build(
            "$build_targets_dir/build-mingw-w64-threads",
            "build-mingw-w64-threads",
            implicit=["$build_targets_dir/configure-mingw-w64-threads"],
            pool="console",
        )
        w.newline()

        w.rule(
            "install-mingw-w64-threads-sysroot",
            "cd $mingw_w64_threads_build_dir && "
            f'$env_path {cc} $make_cmd install DESTDIR=$build_sysroot_dir/usr MAKE="$make_cmd" && '
            "touch ../../$out",
            description="Installing mingw-w64 $mingw_w64_version (winpthreads) at $build_sysroot_dir/usr",
        )
        w.newline()
        w.build(
            "$build_targets_dir/install-mingw-w64-threads-sysroot",
            "install-mingw-w64-threads-sysroot",
            implicit=["$build_targets_dir/build-mingw-w64-threads"],
            pool="console",
        )
        w.newline()

        w.rule(
            "install-mingw-w64-threads",
            "cd $mingw_w64_threads_build_dir && "
            f'$env_path {cc} $make_cmd install DESTDIR=$install_dir/$target MAKE="$make_cmd" && '
            "touch ../../$out",
            description="Installing mingw-w64 $mingw_w64_version (winpthreads)",
        )
        w.newline()
        w.build(
            "$build_targets_dir/install-mingw-w64-threads",
            "install-mingw-w64-threads",
            implicit=["$build_targets_dir/build-mingw-w64-threads"],
            pool="console",
        )
        w.newline()

    def write_step_configure_libc(self, w: Writer, step_no: int) -> None:
        libc_name = self.libc.name()

        w.comment(f"step {step_no} - configure {libc_name}")
        w.newline()
        w.variable(f"{libc_name}_build_dir", f"$build_dir/{libc_name}-build")
        w.newline()

        deps = [
            f"$build_targets_dir/extract-{self.libc.name()}",
            "$build_targets_dir/install-gcc-all-gcc",
        ]
        env_vars = [
            "CROSS_COMPILE=${target}-",
            'CC="${target}-gcc --sysroot=$build_sysroot_dir"',
            # TODO - Add support for CFLAGS
        ]
        flags = [
            "--prefix=",
            "--host=$target",
        ]

        match self.libc:
            case LibC.GLIBC:
                flags.extend([
                    "--disable-multilib",
                    "--disable-werror",
                    "--with-headers=$build_sysroot_dir/usr/include",
                ])
                deps.append("$build_targets_dir/install-linux-headers-sysroot")
            case LibC.MUSL:
                env_vars.append(
                    'LIBCC="$root_dir/$gcc_build_dir/$target/libgcc/libgcc.a"')

                if self.linux_headers:
                    deps.append(
                        "$build_targets_dir/install-linux-headers-sysroot")

        w.rule(
            f"configure-{libc_name}",
            f'rm -rf ${libc_name}_build_dir && mkdir ${libc_name}_build_dir && cd ${libc_name}_build_dir && $env_path {" ".join(env_vars)} ../{libc_name}-${libc_name}_version/configure {" ".join(flags)} && touch ../../$out',
            description=f"Configuring {libc_name} ${libc_name}_version",
        )
        w.newline()
        w.build(
            f"$build_targets_dir/configure-{libc_name}",
            f"configure-{libc_name}",
            implicit=deps,
            pool="console",
        )
        w.newline()

    def write_step_libc_headers(self, w: Writer, step_no: int) -> None:
        libc_name = self.libc.name()

        w.comment(f"step {step_no} - install {libc_name} (headers)")
        w.newline()

        w.rule(
            f"install-{libc_name}-headers-sysroot",
            f'cd ${libc_name}_build_dir && $env_path $make_cmd install-headers DESTDIR=$build_sysroot_dir/usr && touch ../../$out',
            description=f"Installing {libc_name} ${libc_name}_version (headers) at $build_sysroot_dir/usr",
        )
        w.newline()
        w.build(
            f"$build_targets_dir/install-{libc_name}-headers-sysroot",
            f"install-{libc_name}-headers-sysroot",
            implicit=[
                f"$build_targets_dir/configure-{libc_name}",
                "$build_targets_dir/build-sysroot",
            ],
            pool="console",
        )
        w.newline()

    def write_step_gcc_all_target_libgcc(self, w: Writer, step_no: int) -> None:
        w.comment(f"step {step_no} - build gcc (all-target-libgcc)")
        w.newline()

        deps = [
            f"$build_targets_dir/install-{self.libc.name()}-headers-sysroot"]
        sub_make = 'MAKE="$make_cmd"'

        match self.libc:
            case LibC.GLIBC:
                w.rule(
                    "build-glibc-csu",
                    "cd $glibc_build_dir && $env_path $make_cmd csu/subdir_lib && touch ../../$out",
                    description="Building glibc $glibc_version (csu)",
                )
                w.newline()
                w.build(
                    "$build_targets_dir/build-glibc-csu",
                    "build-glibc-csu",
                    implicit=[
                        "$build_targets_dir/install-glibc-headers-sysroot"],
                    pool="console",
                )
                w.newline()

                w.rule(
                    "install-glibc-csu-sysroot",
                    "install $glibc_build_dir/csu/crti.o $glibc_build_dir/csu/crtn.o $build_sysroot_dir/usr/lib && $env_path ${target}-gcc -nostdlib -nostartfiles -shared -x c /dev/null -o $build_sysroot_dir/usr/lib/libc.so && touch $build_sysroot_dir/usr/include/gnu/stubs.h && touch $out",
                    description="Installing glibc $glibc_version (csu) at $build_sysroot_dir/usr",
                )
                w.newline()
                w.build(
                    "$build_targets_dir/install-glibc-csu-sysroot",
                    "install-glibc-csu-sysroot",
                    implicit=["$build_targets_dir/build-glibc-csu"],
                    pool="console",
                )
                w.newline()

                deps.append(
                    "$build_targets_dir/install-glibc-csu-sysroot")

            case LibC.MUSL:
                sub_make = 'MAKE="$make_cmd enable_shared=no"'

        w.rule(
            "build-gcc-all-target-libgcc",
            f"cd $gcc_build_dir && $env_vars $make_cmd all-target-libgcc {sub_make} && touch ../../$out",
            description="Building gcc $gcc_version (all-target-libgcc)",
        )
        w.newline()
        w.build(
            "$build_targets_dir/build-gcc-all-target-libgcc",
            "build-gcc-all-target-libgcc",
            implicit=deps,
            pool="console",
        )
        w.newline()

        w.rule(
            "install-gcc-all-target-libgcc",
            f"cd $gcc_build_dir && $env_vars $make_cmd install-target-libgcc DESTDIR=$install_dir {sub_make} && touch ../../$out",
            description="Installing gcc $gcc_version (all-target-libgcc)",
        )
        w.newline()
        w.build(
            "$build_targets_dir/install-gcc-all-target-libgcc",
            "install-gcc-all-target-libgcc",
            implicit=["$build_targets_dir/build-gcc-all-target-libgcc"],
            pool="console",
        )
        w.newline()

    def write_step_build_libc(self, w: Writer, step_no: int) -> None:
        libc_name = self.libc.name()

        w.comment(f"step {step_no} - build {libc_name}")
        w.newline()

        deps = []

        match self.libc:
            case LibC.GLIBC:
                deps.append("$build_targets_dir/install-gcc-all-target-libgcc")
            case LibC.MUSL:
                deps.append("$build_targets_dir/build-gcc-all-target-libgcc")

        w.rule(
            f"build-{libc_name}",
            f'cd ${libc_name}_build_dir && $env_path $make_cmd MAKE="$make_cmd" && touch ../../$out',
            description=f"Building {libc_name} ${libc_name}_version",
        )
        w.newline()
        w.build(
            f"$build_targets_dir/build-{libc_name}",
            f"build-{libc_name}",
            implicit=deps,
            pool="console",
        )
        w.newline()

        w.rule(
            f"install-{libc_name}-sysroot",
            f'cd ${libc_name}_build_dir && $env_path $make_cmd install DESTDIR=$build_sysroot_dir/usr MAKE="$make_cmd" && touch ../../$out',
            description=f"Installing {libc_name} ${libc_name}_version at $build_sysroot_dir",
        )
        w.newline()
        w.build(
            f"$build_targets_dir/install-{libc_name}-sysroot",
            f"install-{libc_name}-sysroot",
            implicit=[
                f"$build_targets_dir/build-{libc_name}",
                "$build_targets_dir/build-sysroot",
            ],
            pool="console",
        )
        w.newline()

        w.rule(
            f"install-{libc_name}",
            f'cd ${libc_name}_build_dir && $env_path $make_cmd install DESTDIR=$install_dir/$target MAKE="$make_cmd" && touch ../../$out',
            description=f"Installing {libc_name} ${libc_name}_version",
        )
        w.newline()
        w.build(
            f"$build_targets_dir/install-{libc_name}",
            f"install-{libc_name}",
            implicit=[f"$build_targets_dir/build-{libc_name}"],
            pool="console",
        )
        w.newline()

    def write_step_build_gcc(self, w: Writer, step_no: int) -> None:
        w.comment(f"step {step_no} - build gcc")
        w.newline()

        deps = []

        if self.libc.requires_mingw_w64():
            deps.append("$build_targets_dir/install-mingw-w64-crt-sysroot")

            if self.libc.is_mingw_w64():
                deps.append(
                    "$build_targets_dir/install-mingw-w64-threads-sysroot")
        else:
            deps.append(
                f"$build_targets_dir/install-{self.libc.name()}-sysroot")

        w.rule(
            "build-gcc",
            'cd $gcc_build_dir && $env_vars $make_cmd MAKE="$make_cmd" && touch ../../$out',
            description="Building gcc $gcc_version",
        )
        w.newline()
        w.build(
            "$build_targets_dir/build-gcc",
            "build-gcc",
            implicit=deps,
            pool="console",
        )
        w.newline()

        w.rule(
            "install-gcc",
            'cd $gcc_build_dir && $env_vars $make_cmd install MAKE="$make_cmd" DESTDIR=$install_dir && touch ../../$out',
            description="Installing gcc $gcc_version",
        )
        w.newline()
        w.build(
            "$build_targets_dir/install-gcc",
            "install-gcc",
            implicit=["$build_targets_dir/build-gcc"],
            pool="console",
        )
        w.newline()

    def write_clean_targets(self, w: Writer) -> None:
        w.comment("clean targets")
        w.newline()

        w.rule(
            "delete-directory",
            "rm -rf $in",
            description="Deleting $in"
        )
        w.newline()

        w.rule("clean-all", "true", description="Cleaned everything")
        w.newline()

        w.build(
            "clean-build",
            "delete-directory",
            inputs=["$build_dir"],
        )
        w.build(
            "clean-downloads",
            "delete-directory",
            inputs=["$download_dir"],
        )
        w.build(
            "clean-toolchain",
            "delete-directory",
            inputs=["$install_dir"],
        )
        w.build(
            "clean",
            "clean-all",
            implicit=["clean-build", "clean-downloads", "clean-toolchain"],
        )
        w.newline()

    def write_install_targets(self, w: Writer) -> None:
        w.comment("install targets")
        w.newline()

        w.rule(
            "install-all", "true", description="Installed toolchain at $install_dir"
        )
        w.newline()

        install_targets = [
            "$build_targets_dir/install-binutils",
            "$build_targets_dir/install-gcc",
        ]

        if self.libc.requires_mingw_w64():
            install_targets.extend([
                "$build_targets_dir/install-mingw-w64-headers",
                "$build_targets_dir/install-mingw-w64-crt",
            ])

            if self.libc.is_mingw_w64():
                install_targets.append(
                    "$build_targets_dir/install-mingw-w64-threads")
        else:
            if self.linux_headers:
                install_targets.append(
                    "$build_targets_dir/install-linux-headers")

            install_targets.append(
                f"$build_targets_dir/install-{self.libc.name()}")

        w.build(
            "install",
            "install-all",
            implicit=install_targets,
        )
        w.newline()

    def write_default_targets(self, w: Writer) -> None:
        w.comment("default targets")
        w.newline()

        default_targets = ["$build_targets_dir/build-gcc"]

        if self.linux_headers:
            default_targets.append("$build_targets_dir/build-linux-headers")

        w.default(default_targets)
        w.newline()

    def ninja(self) -> None:
        step_no = 1
        print("Writing build.ninja")
        with open("build.ninja", "w") as f:
            w = Writer(f)

            self.write_variables(w)
            self.write_step_download_extract(w, step_no)
            step_no += 1
            self.write_step_binutils(w, step_no)
            step_no += 1
            self.write_step_sysroot(w, step_no)
            step_no += 1
            self.write_step_configure_gcc(w, step_no)
            step_no += 1
            self.write_step_gcc_all_gcc(w, step_no)
            step_no += 1

            if self.libc.requires_mingw_w64():
                self.write_step_mingw_w64_headers(w, step_no)
                step_no += 1
                self.write_step_mingw_w64_crt(w, step_no)
                step_no += 1

                if self.libc.is_mingw_w64():
                    self.write_step_mingw_w64_threads(w, step_no)
                    step_no += 1
            else:
                if self.linux_headers:
                    self.write_step_linux_headers(w, step_no)
                    step_no += 1

                self.write_step_configure_libc(w, step_no)
                step_no += 1
                self.write_step_libc_headers(w, step_no)
                step_no += 1
                self.write_step_gcc_all_target_libgcc(w, step_no)
                step_no += 1
                self.write_step_build_libc(w, step_no)
                step_no += 1

            self.write_step_build_gcc(w, step_no)
            step_no += 1
            self.write_clean_targets(w)
            self.write_install_targets(w)
            self.write_default_targets(w)


def main() -> None:
    args = cli.parse()
    
    match args.libc:
        case "auto":
            if "cygwin" in args.target:
                args.libc = LibC.CYGWIN_NEWLIB
            elif "gnu" in args.target:
                args.libc = LibC.GLIBC
            elif "mingw" in args.target:
                args.libc = LibC.UCRT
            elif "musl" in args.target:
                args.libc = LibC.MUSL
            else:
                print(
                    "Error: Cannot determine which libc implemention to use. "
                    "Use --libc flag to explicitly specify it."
                )
                sys.exit(1)
        case "cygwin-newlib":
            args.libc = LibC.CYGWIN_NEWLIB
        case "glibc":
            args.libc = LibC.GLIBC
        case "msvcrt":
            args.libc = LibC.MSVCRT
        case "musl":
            args.libc = LibC.MUSL
        case "ucrt":
            args.libc = LibC.UCRT

    match args.linux_headers:
        case "auto" | "enabled":
            if args.libc.is_cygwin_newlib() or args.libc.is_mingw_w64():
                args.linux_headers = False
            else:
                args.linux_headers = True
        case "disabled":
            if args.libc == LibC.GLIBC:
                print("Error: Linux headers cannot be disabled when building glibc.")
                sys.exit(1)

            args.linux_headers = False

    if "cygwin" in args.target:
        tarball = f"prepare/cygwin-{args.cygwin_version}-{args.target}.tar.xz"

        if not Path(tarball).exists():
            if not Path("prepare").exists():
                os.mkdir("prepare")

            sys.exit(1)

    # print("using")
    args = Args(args)
    failed = args.try_get_tools()

    if failed:
        print("Error: Some tools do not exist. You may need add them to your PATH.")
        sys.exit(1)

    args.dependencies_summary()
    args.ninja()


if __name__ == "__main__":
    main()
