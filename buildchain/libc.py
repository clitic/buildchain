from enum import Enum


class LibC(Enum):
    GLIBC = 1
    MSVCRT = 2
    MUSL = 3
    NEWLIB_CYGWIN = 4
    UCRT = 5

    def is_cygwin_newlib(self) -> bool:
        return self == LibC.NEWLIB_CYGWIN

    def is_mingw_w64(self) -> bool:
        return self == LibC.MSVCRT or self == LibC.UCRT

    def name(self) -> str:
        match self:
            case LibC.NEWLIB_CYGWIN:
                return "newlib-cygwin"

            case LibC.GLIBC:
                return "glibc"

            case LibC.MSVCRT:
                return "msvcrt"

            case LibC.MUSL:
                return "musl"

            case LibC.UCRT:
                return "ucrt"

    def requires_mingw_w64(self) -> bool:
        match self:
            case LibC.MSVCRT | LibC.UCRT | LibC.NEWLIB_CYGWIN:
                return True
            case _:
                return False
