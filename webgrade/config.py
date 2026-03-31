from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import os

from dotenv import load_dotenv


DEFAULT_OUTPUT_DIR = Path("./webgrade-output")
DB_FILE_NAME = "webgrade.sqlite3"


@dataclass(slots=True)
class Settings:
    output_root: Path
    db_path: Path
    openai_api_key: str | None
    pagespeed_api_key: str | None

    def create_batch_dir(self) -> Path:
        timestamp = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
        batch_dir = self.output_root / timestamp
        batch_dir.mkdir(parents=True, exist_ok=False)
        (batch_dir / "reports").mkdir(parents=True, exist_ok=True)
        (batch_dir / "screenshots").mkdir(parents=True, exist_ok=True)
        return batch_dir


def load_settings(output_dir: Path | None) -> Settings:
    load_dotenv()
    output_root = (output_dir or DEFAULT_OUTPUT_DIR).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    return Settings(
        output_root=output_root,
        db_path=output_root / DB_FILE_NAME,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        pagespeed_api_key=os.getenv("PAGESPEED_API_KEY"),
    )
