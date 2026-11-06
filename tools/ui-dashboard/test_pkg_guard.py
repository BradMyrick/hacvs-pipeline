"""Permanent tripwire: the lib/ package layout must match git exactly.

Born from a real incident: a transposed package name (hacsvp/hacvsp) created a
stray sibling directory, and nondeterministic glob order sent patches into the
stray while git tracked the real one. This test makes that class of drift fail
loudly at `make test` time — forever.
"""
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


class TestPackageLayout(unittest.TestCase):
    def test_exactly_one_lib_package_and_it_is_git_tracked(self):
        lib = ROOT / "lib"
        dirs = sorted(d.name for d in lib.iterdir() if d.is_dir())
        self.assertEqual(len(dirs), 1, f"lib/ must hold exactly one package, found: {dirs}")
        tracked = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "lib/"],
            capture_output=True, text=True).stdout.split()
        self.assertTrue(tracked, "git tracks nothing under lib/")
        tracked_pkg = pathlib.Path(tracked[0]).parts[1]
        self.assertEqual(dirs[0], tracked_pkg,
                         f"filesystem pkg {dirs[0]!r} != git-tracked pkg {tracked_pkg!r}")

    def test_package_imports_with_version(self):
        sys.path.insert(0, str(ROOT / "lib"))
        pkg_name = sorted((ROOT / "lib").iterdir())[0].name
        mod = __import__(pkg_name)
        self.assertTrue(getattr(mod, "__version__", ""),
                        "package __init__ lost its version (clobbered?)")

    def test_no_transposed_sibling(self):
        lib = ROOT / "lib"
        names = {d.name for d in lib.iterdir()}
        for n in names:
            transposed = n[3:5][::-1] and n[:3] + n[4] + n[3] + n[5:]
            if transposed != n:
                self.assertNotIn(transposed, names - {n},
                                 f"transposed sibling of {n!r} exists: {transposed!r}")


if __name__ == "__main__":
    unittest.main()
