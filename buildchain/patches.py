import argparse
import io
import distutils
import os
import requests
import zipfile
from pathlib import Path
from typing import List


MUSL_CROSS_MAKE_COMMIT = "fe915821b652a7fa37b34a596f47d8e20bc72338"


class Patch:
    path = Path,

    def __init__(self, name: str, version: str):
        self.path = Path(f"patches/{name}-{version}")

    def exists(self) -> bool:
        return self.path.exists()

    def files(self) -> List[str]:
        return [f"{self.path}/{i}".replace("\\", "/") for i in os.listdir(self.path)]


def download_musl_cross_make():
    extracted_dir = f"patches/downloads/musl-cross-make-{MUSL_CROSS_MAKE_COMMIT}"

    if not Path(extracted_dir).exists():
        url = f"https://github.com/richfelker/musl-cross-make/archive/{MUSL_CROSS_MAKE_COMMIT}.zip"
        print(f"Downloading patches from {url}")
        response = requests.get(url)
        data = io.BytesIO(response.content)
        print(f"Extracting patches at {extracted_dir}")
        f = zipfile.ZipFile(data)
        f.extractall("patches/downloads")
        f.close()
        distutils.dir_util.copy_tree(
            Path(extracted_dir).joinpath("patches"), "patches")
    else:
        print(f"Patches are already downloaded at {extracted_dir}")


def main(args: argparse.Namespace):
    if not os.path.exists("patches"):
        os.mkdir("patches")

    if args.musl_cross_make:
        download_musl_cross_make()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="patches",
        description="Download patches from some repositories.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--musl-cross-make",
        action="store_true",
        default=False,
        help="Download patches from https://github.com/richfelker/musl-cross-make.",
    )
    main(parser.parse_args())
