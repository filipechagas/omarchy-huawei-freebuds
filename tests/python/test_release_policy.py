"""Exercise the actual release-check script with local Git remotes."""

import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[2]
TAG = "refs/tags/v0.1.3"


class ReleasePolicyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="freebuds-release-")
        self.addCleanup(self.temporary.cleanup)
        self.origin = Path(self.temporary.name) / "origin"
        self.checkout = Path(self.temporary.name) / "checkout"
        self.origin.mkdir()
        self.git(self.origin, "init", "--quiet")
        docs = self.origin / "docs"
        docs.mkdir()
        (docs / "hardware-validation.md").write_text(
            (ROOT / "docs/hardware-validation.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        self.git(self.origin, "add", "docs")
        self.git(self.origin, "commit", "--quiet", "-m", "release fixture")
        self.git(self.origin, "tag", "-a", TAG.removeprefix("refs/tags/"), "-m", "unsigned annotated fixture")
        self.git(self.origin, "clone", "--quiet", "--no-hardlinks", str(self.origin), str(self.checkout))
        # Reproduce actions/checkout fetching the peeled commit into the tag ref.
        self.git(self.checkout, "update-ref", TAG, "HEAD")

    @staticmethod
    def git(directory, *arguments):
        return subprocess.run(
            [
                "git", "-C", str(directory),
                "-c", "user.name=Release policy test",
                "-c", "user.email=test@example.invalid",
                "-c", "commit.gpgsign=false",
                "-c", "tag.gpgsign=false",
                *arguments,
            ],
            check=True, capture_output=True, text=True,
        )

    def run_check(self):
        workflow = (ROOT / ".github/workflows/check.yml").read_text(encoding="utf-8")
        section = workflow.split(
            "      - name: Validate optional hardware checklist and annotated release tag\n", 1
        )[1].split("\n      - name:", 1)[0]
        script = textwrap.dedent(section.split("        run: |\n", 1)[1])
        return subprocess.run(
            ["bash", "-euc", script], cwd=self.checkout,
            env=dict(os.environ, GITHUB_REF_TYPE="tag", GITHUB_REF=TAG),
            capture_output=True, text=True, timeout=10,
        )

    def test_accepts_pending_checklist_and_remote_annotated_tag_after_checkout_peels_it(self):
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rejects_remote_lightweight_tag(self):
        self.git(self.origin, "update-ref", TAG, "HEAD")
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("annotated tag objects", result.stderr)

    def test_rejects_remote_tag_targeting_another_commit(self):
        self.git(self.origin, "commit", "--quiet", "--allow-empty", "-m", "another commit")
        self.git(self.origin, "update-ref", TAG, "HEAD")
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("remote release tag must target the checked commit", result.stderr)


if __name__ == "__main__":
    unittest.main()
