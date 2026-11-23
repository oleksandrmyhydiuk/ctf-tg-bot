"""Export all bot tasks to webapp/src/data/botTasks.json for the Mini App.

SECURITY: Never exports `setup_script` or step `check` scripts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tasks import TASKS  # noqa: E402

DEFAULT_MEM_LIMIT = "128m"
DEFAULT_PIDS_LIMIT = 64
OUTPUT_PATH = ROOT / "webapp" / "src" / "data" / "botTasks.json"


def build_exported_tasks() -> list[dict]:
    exported: list[dict] = []
    for idx, task in enumerate(TASKS, start=1):
        steps = [
            {
                "text": step["text"],
                "hint": step.get("hint", ""),
            }
            for step in task["steps"]
        ]
        exported.append(
            {
                "id": idx,
                "slug": task["slug"],
                "title": task["title"],
                "category": task.get("category", ""),
                "difficulty": task.get("difficulty", "easy"),
                "reward_points": task["reward_points"],
                "description": task["intro"],
                "mem_limit": task.get("mem_limit") or DEFAULT_MEM_LIMIT,
                "pids_limit": task.get("pids_limit") or DEFAULT_PIDS_LIMIT,
                "steps": steps,
            }
        )
    return exported


def main() -> None:
    exported = build_exported_tasks()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(exported, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Exported {len(exported)} tasks to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
