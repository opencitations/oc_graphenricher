import subprocess
import sys


def test():
    subprocess.run(
        [
            sys.executable,
            "-u",
            "-m",
            "unittest",
            "discover",
            "-s",
            "oc_graphenricher",
            "-p",
            "test_*.py",
        ],
        check=True,
    )
