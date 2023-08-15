import argparse

def parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Configure binutils and gcc based toolchain.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        prog="buildchain",
    )
    group = parser.add_argument_group("toolchain options")
    group.add_argument(
        "--host",
        help="Host triple for the toolchain. Do not use this flag unless you are building cross native or canadian cross toolchain.",
    )
    group.add_argument(
        "--target",
        required=True,
        help="Target triple for the toolchain.",
    )
    group = parser.add_argument_group("compiler options")
    group.add_argument(
        "--cc",
        default="$host-gcc",
        help="C compiler for host.",
    )
    group.add_argument(
        "--cxx",
        default="$host-g++",
        help="C++ compiler for host.",
    )
    group.add_argument(
        "--cc-build",
        default="gcc",
        help="C compiler for build.",
    )
    group.add_argument(
        "--cxx-build",
        default="g++",
        help="C++ compiler for build.",
    )
    group.add_argument(
        "--cc-flags",
        default=None,
        help="Extra C compiler flags.",
    )
    group.add_argument(
        "--cxx-flags",
        default=None,
        help="Extra C++ compiler flags.",
    )
    group.add_argument(
        "--ld-flags",
        default=None,
        help="Extra linker flags.",
    )
    group.add_argument(
        "--enable-cache",
        action="store_true",
        default=False,
        help="Use ccache or sccache (if available) as compiler wrapper.",
    )
    group = parser.add_argument_group("configure options")
    group.add_argument(
        "--binutils-flags",
        default=None,
        help="Add extra flags when configuring binutils.",
    )
    group.add_argument(
        "--gcc-flags",
        default=None,
        help="Add extra flags when configuring gcc.",
    )
    group.add_argument(
        "--gcc-with-isl",
        action="store_true",
        default=False,
        help="Build gcc with isl library.",
    )
    group.add_argument(
        "--libc",
        choices=["auto", "glibc", "msvcrt", "musl", "newlib-cygwin", "ucrt"],
        default="auto",
        help="Libc implemention to use for target toolchain.",
    )
    group.add_argument(
        "--linux-headers",
        choices=["auto", "disabled", "enabled"],
        default="auto",
        help="Build and install linux kernel headers.",
    )
    group.add_argument(
        "--no-default-configure",
        action="store_true",
        default=False,
        help="Do not configure binutils and gcc with default flags.",
    )
    parser.add_argument(
        "--no-patches",
        action="store_true",
        default=False,
        help="Do not apply patches from patches directory.",
    )
    group = parser.add_argument_group("dependencies")
    group.add_argument(
        "--binutils-version",
        default="2.40",  # https://ftp.gnu.org/gnu/binutils
        help="Binutils version to build.",
    )
    group.add_argument(
        "--cygwin-version",
        default="3.4.7",  # https://cygwin.com
        help="Cygwin version to build.",
    )
    group.add_argument(
        "--gcc-version",
        default="13.2.0",  # https://ftp.gnu.org/gnu/gcc
        help="Gcc version to build.",
    )
    group.add_argument(
        "--glibc-version",
        default="2.38",  # https://ftp.gnu.org/gnu/glibc
        help="Glibc version to build.",
    )
    group.add_argument(
        "--gmp-version",
        default="6.2.1",  # https://ftp.gnu.org/gnu/gmp
        help="Gmp version to build.",
    )
    group.add_argument(
        "--mingw-w64-version",
        # https://sourceforge.net/projects/mingw-w64/files/mingw-w64/mingw-w64-release
        default="11.0.1",
        help="Mingw-w64 version to build.",
    )
    group.add_argument(
        "--mpc-version",
        default="1.3.1",  # https://ftp.gnu.org/gnu/mpc
        help="Mpc version to build.",
    )
    group.add_argument(
        "--mpfr-version",
        default="4.2.0",  # https://ftp.gnu.org/gnu/mpfr
        help="Mpfr version to build.",
    )
    group.add_argument(
        "--isl-version",
        default="0.26",  # https://libisl.sourceforge.io
        help="Isl version to build.",
    )
    group.add_argument(
        "--linux-version",
        default="6.1.40",  # https://www.kernel.org
        help="Linux version to build.",
    )
    group.add_argument(
        "--musl-version",
        default="1.2.4",  # https://musl.libc.org
        help="Musl version to build.",
    )
    return parser.parse_args()
