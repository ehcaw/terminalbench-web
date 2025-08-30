from typing import Iterable, Any, List, Dict
import os
import zipfile
from fastapi import HTTPException

def _normalize_path(p: str) -> str:
    """
    Normalize a path string for consistent comparison:
    - Convert Windows backslashes to forward slashes
    - Remove leading './'
    - Collapse duplicate slashes
    - Strip surrounding whitespace
    """
    p = (p or "").strip()
    p = p.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    while "//" in p:
        p = p.replace("//", "/")
    return p


def _path_parts(p: str) -> List[str]:
    return [part for part in _normalize_path(p).split("/") if part]


def _basename(p: str) -> str:
    parts = _path_parts(p)
    return parts[-1] if parts else ""


def _collect_filenames(files: Iterable[Any]) -> List[str]:
    """
    Accepts any of:
      - Iterable[str] of file paths relative to the root of the uploaded directory
      - Iterable[UploadFile] from FastAPI with .filename
      - Iterable[objects] that have a .filename attribute

    Returns a list of normalized paths.
    """
    paths: List[str] = []
    for f in files:
        if isinstance(f, str):
            paths.append(_normalize_path(f))
        else:
            # Best-effort to read a 'filename' attribute (like UploadFile)
            filename = getattr(f, "filename", None)
            if filename:
                paths.append(_normalize_path(filename))
            else:
                # If there's no filename, skip (or could raise).
                continue
    return paths


def validate_directory(files: Iterable[Any]) -> Dict[str, Any]:
    """
    Validate that the uploaded directory contains required files:
      - tests directory containing 'test_outputs.py' (directory named 'test' or 'tests')
      - either 'solution.yaml' or 'solution.sh'
      - 'task.yaml'
      - either exactly one 'Dockerfile' or a 'docker-compose.yaml' (or .yml)

    The check is based on the filenames provided. Clients should include the
    directory path in each file's filename (e.g., 'tests/test_outputs.py').

    Returns a dict with:
      - 'valid': bool
      - 'checks': details about each check
      - 'errors': list of human-readable error strings
      - 'files_seen': sorted list of normalized file paths (for debugging)
    """
    file_paths = _collect_filenames(files)
    files_set = set(file_paths)

    # Helpers for checks
    def any_basename_is(names: List[str]) -> bool:
        wanted = {n for n in names}
        for p in files_set:
            if _basename(p) in wanted:
                return True
        return False

    def count_basenames(name: str) -> int:
        c = 0
        for p in files_set:
            if _basename(p) == name:
                c += 1
        return c

    # tests dir with test_outputs.py inside
    has_test_outputs_in_tests_dir = False
    for p in files_set:
        parts = _path_parts(p)
        if parts and parts[-1] == "test_outputs.py":
            # must have a parent directory named 'test' or 'tests'
            parent_dirs = set(parts[:-1])
            if "tests" in parent_dirs or "test" in parent_dirs:
                has_test_outputs_in_tests_dir = True
                break

    # solution
    has_solution = any_basename_is(["solution.yaml", "solution.sh"])

    # task.yaml
    has_task_yaml = any_basename_is(["task.yaml"])

    # docker: either a single Dockerfile or a docker-compose
    dockerfiles_count = count_basenames("Dockerfile")
    has_docker_compose = any_basename_is(["docker-compose.yaml", "docker-compose.yml"])
    docker_ok = has_docker_compose or dockerfiles_count == 1

    errors: List[str] = []
    if not has_test_outputs_in_tests_dir:
        errors.append("Missing tests/test_outputs.py (must be inside a 'tests' or 'test' directory).")
    if not has_solution:
        errors.append("Missing solution.yaml or solution.sh.")
    if not has_task_yaml:
        errors.append("Missing task.yaml.")
    if not docker_ok:
        if dockerfiles_count == 0:
            errors.append("Missing Dockerfile or docker-compose.yaml.")
        elif dockerfiles_count > 1:
            errors.append("Multiple Dockerfile files found; provide exactly one Dockerfile or use docker-compose.yaml.")

    checks = {
        "tests_dir_has_test_outputs": has_test_outputs_in_tests_dir,
        "solution_present": has_solution,
        "task_yaml_present": has_task_yaml,
        "docker_requirement_ok": docker_ok,
        "dockerfiles_found": dockerfiles_count,
        "docker_compose_present": has_docker_compose,
    }

    return {
        "valid": len(errors) == 0,
        "checks": checks,
        "errors": errors,
        "files_seen": sorted(files_set),
    }


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _is_within_directory(directory: str, target: str) -> bool:
    abs_directory = os.path.abspath(directory)
    abs_target = os.path.abspath(target)
    try:
        common = os.path.commonpath([abs_directory, abs_target])
    except ValueError:
        # Different drives on Windows
        return False
    return common == abs_directory


def safe_extract(zipf: zipfile.ZipFile, target_dir: str) -> None:
    for member in zipf.namelist():
        # Prevent absolute paths and path traversal
        if os.path.isabs(member):
            raise HTTPException(status_code=400, detail="Unsafe zip content: absolute path detected.")
        dest_path = os.path.join(target_dir, member)
        if not _is_within_directory(target_dir, dest_path):
            raise HTTPException(status_code=400, detail="Unsafe zip content: path traversal detected.")
    zipf.extractall(target_dir)


def list_relative_files(root_dir: str) -> List[str]:
    rels: List[str] = []
    for base, _, files in os.walk(root_dir):
        for name in files:
            full_path = os.path.join(base, name)
            rel = os.path.relpath(full_path, root_dir)
            rels.append(_normalize_path(rel))
    return rels
