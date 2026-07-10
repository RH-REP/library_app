from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
INIT_PROJECT_PATH = REPO_ROOT / ".core_program" / "app" / "00_initialize_project" / "init_project.py"


def _load_init_project_module():
    spec = importlib.util.spec_from_file_location("artifactforge_init_project", INIT_PROJECT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load init_project.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


init_project = _load_init_project_module()


class InitProjectGitignoreTest(unittest.TestCase):
    def test_project_gitignore_tracks_project_artifact_directories(self) -> None:
        source_text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        project_text = init_project.project_gitignore_text(source_text)

        self.assertNotIn("\nsub_artifact/*\n", "\n" + project_text)
        self.assertNotIn("\nissue_log/*\n", "\n" + project_text)
        self.assertIn(".core_program/assignment_state.json", project_text)
        self.assertIn(".core_program/queue/*", project_text)
        self.assertIn(".core_program/pending/*", project_text)
        self.assertIn(".core_program/archive/*", project_text)
        self.assertIn(".core_program/app/01_fetch_issue/data/", project_text)
        self.assertIn(".core_program/dry_run_output/", project_text)

    def test_project_gitignore_check_ignore_behavior(self) -> None:
        source_text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        project_text = init_project.project_gitignore_text(source_text)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subprocess.run(["git", "init"], cwd=str(root), check=True, capture_output=True)
            (root / ".gitignore").write_text(project_text, encoding="utf-8")

            for path in (
                "sub_artifact/001_example/artifact.md",
                "issue_log/001_example/work_log.md",
            ):
                result = subprocess.run(
                    ["git", "check-ignore", path],
                    cwd=str(root),
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertNotEqual(0, result.returncode, msg=path)

            for path in (
                ".core_program/assignment_state.json",
                ".core_program/queue/item.md",
                ".core_program/pending/item.md",
                ".core_program/archive/item.md",
                ".core_program/app/01_fetch_issue/data/open_issues.json",
                ".core_program/dry_run_output/plan.json",
            ):
                result = subprocess.run(
                    ["git", "check-ignore", path],
                    cwd=str(root),
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(0, result.returncode, msg=path)


if __name__ == "__main__":
    unittest.main()
