
import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

EXPECTED_COMMIT = "1d4dc2c0e6e476911d0760e9c3cf3694f2d43384"

SOURCE_DIRS = ["packages", "excalidraw-app"]

EXCLUDED_DIRS = {
    "node_modules", "dist", "build", "coverage",
    ".git", "__fixtures__", "fixtures"
}

TEST_DIRS = {
    "test", "tests", "__tests__", "__mocks__", "test-utils"
}

TEST_PATTERN = re.compile(r"\.(test|spec)\.[cm]?[jt]sx?$", re.I)


def run_command(command, cwd=None):
    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        errors="replace"
    )
    return result.returncode, result.stdout + result.stderr


def collect_files(repo, production_dir, tests_dir):
    counts = {"production": 0, "tests": 0}
    manifests = {"production": [], "tests": []}

    for source in SOURCE_DIRS:
        root = repo / source

        if not root.is_dir():
            raise RuntimeError(f"Missing directory: {root}")

        for parent, directories, filenames in os.walk(root):
            directories[:] = [
                d for d in directories
                if d.lower() not in EXCLUDED_DIRS
            ]

            for filename in filenames:
                original = Path(parent) / filename

                if original.suffix.lower() not in (".ts", ".tsx"):
                    continue

                relative_path = original.relative_to(repo)

                is_test = (
                    bool(TEST_PATTERN.search(filename))
                    or any(
                        part.lower() in TEST_DIRS
                        for part in relative_path.parts[:-1]
                    )
                )

                category = "tests" if is_test else "production"
                destination_root = tests_dir if is_test else production_dir
                destination = destination_root / relative_path

                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(original, destination)

                counts[category] += 1
                manifests[category].append(relative_path.as_posix())

    return counts, manifests


def parse_simian_results(output):
    duplicate_matches = re.findall(
        r"(?mi)^\s*Found\s+([\d,]+)\s+duplicate lines in\s+\d+\s+blocks?\b",
        output
    )

    if not duplicate_matches:
        duplicate_matches = re.findall(
            r"(?mi)^\s*Found\s+([\d,]+)\s+duplicate lines in\s+\d+\s+files?\b",
            output
        )

    significant_matches = re.findall(
        r"(?mi)Processed a total of\s+([\d,]+)\s+significant"
        r"(?:\s*\([^)]*\))?\s+lines in\s+([\d,]+)\s+files?",
        output
    )

    if not duplicate_matches or not significant_matches:
        raise RuntimeError(
            "Could not parse Simian output. Check the generated log file."
        )

    duplicate_lines = int(duplicate_matches[-1].replace(",", ""))
    significant_lines = int(significant_matches[-1][0].replace(",", ""))
    files_processed = int(significant_matches[-1][1].replace(",", ""))

    if significant_lines == 0:
        raise RuntimeError("Simian processed zero significant lines.")

    return duplicate_lines, significant_lines, files_processed


def run_simian(java, jar, directory, threshold, log_path):
    patterns = [
        str(directory / "**" / "*.ts"),
        str(directory / "**" / "*.tsx")
    ]

    command = [
        java,
        "-Xmx2g",
        "-jar",
        str(jar),
        f"-threshold={threshold}",
        *patterns
    ]

    return_code, output = run_command(command)

    log_path.write_text(output, encoding="utf-8")

    duplicate, significant, processed = parse_simian_results(output)

    percentage = duplicate / significant * 100

    return {
        "threshold": threshold,
        "duplicate_lines": duplicate,
        "significant_lines": significant,
        "files_processed": processed,
        "percentage": percentage,
        "return_code": return_code,
        "log": log_path.name
    }


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--repo", required=True)
    parser.add_argument("--jar", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--java", default="java")

    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    jar = Path(args.jar).resolve()
    output_dir = Path(args.out).resolve()

    if not (repo / "package.json").exists():
        raise RuntimeError("Invalid Excalidraw repository path.")

    if not jar.is_file():
        raise RuntimeError(f"Simian JAR not found: {jar}")

    if output_dir == repo or repo in output_dir.parents:
        raise RuntimeError(
            "Output directory must be outside the Excalidraw repository."
        )

    code, commit = run_command(["git", "rev-parse", "HEAD"], repo)

    if code != 0:
        raise RuntimeError("Cannot determine Git commit.")

    commit = commit.strip()

    print(f"Excalidraw commit: {commit}")

    if commit != EXPECTED_COMMIT:
        print("WARNING: This is not the original baseline commit.")

    output_dir.mkdir(parents=True, exist_ok=True)

    stage = output_dir / "staged"

    if stage.exists():
        shutil.rmtree(stage)

    production = stage / "production"
    tests = stage / "tests"

    counts, manifests = collect_files(repo, production, tests)

    for category, paths in manifests.items():
        manifest_path = output_dir / f"{category}_manifest.txt"
        manifest_path.write_text(
            "\n".join(sorted(paths)) + "\n",
            encoding="utf-8"
        )

    print(f"Production files: {counts['production']}")
    print(f"Test files: {counts['tests']}")

    configurations = [
        ("Production", production, 6, "m5_production_t6.txt"),
        ("Production", production, 10, "m5_production_t10.txt"),
        ("Tests", tests, 6, "m5_tests_t6.txt")
    ]

    results = []

    for scope, directory, threshold, filename in configurations:
        print(f"\nRunning {scope}, threshold={threshold}...")

        result = run_simian(
            args.java,
            jar,
            directory,
            threshold,
            output_dir / filename
        )

        result["scope"] = scope
        results.append(result)

        print(f"Duplicate lines: {result['duplicate_lines']}")
        print(f"Significant lines: {result['significant_lines']}")
        print(f"Duplication: {result['percentage']:.2f}%")

        expected_files = counts[
            "tests" if scope == "Tests" else "production"
        ]

        if result["files_processed"] != expected_files:
            print(
                "WARNING: Simian processed a different number of files "
                "than were staged. Check the log and manifest."
            )

    csv_path = output_dir / "M5_results.csv"

    with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)

        writer.writerow([
            "Scope",
            "Threshold",
            "Duplicate Lines",
            "Significant Lines",
            "Duplication Percentage",
            "Files Processed",
            "Log File"
        ])

        for result in results:
            writer.writerow([
                result["scope"],
                result["threshold"],
                result["duplicate_lines"],
                result["significant_lines"],
                f"{result['percentage']:.2f}",
                result["files_processed"],
                result["log"]
            ])

    print("\nAnalysis completed.")
    print(f"Results CSV: {csv_path}")
    print("Detailed duplication locations are saved in the log files.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError) as error:
        sys.exit(f"ERROR: {error}")
