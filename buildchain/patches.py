import os
from pathlib import Path
from typing import List


class Patch:
    path = Path,

    def __init__(self, name: str, version: str):
        self.path = Path(f"patches/{name}-{version}")

    def exists(self) -> bool:
        return self.path.exists()

    def files(self) -> List[str]:
        return [f"{self.path}/{i}".replace("\\", "/") for i in os.listdir(self.path)]
