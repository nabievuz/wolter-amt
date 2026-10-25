#!/usr/bin/env python3
"""Read-only admission facts. No authentication files, keys, tokens or external calls."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import pwd
import re
import shutil
import subprocess
from datetime import datetime, timezone


def command(argv: list[str]) -> str | None:
    """Return local, bounded output only; callers expose selected facts, never raw output."""
    if not shutil.which(argv[0]):
        return None
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def file_text(path: Path) -> str | None:
    try:
        return path.read_text()
    except (OSError, UnicodeError):
        return None


def account(name: str) -> dict[str, object]:
    try:
        entry = pwd.getpwnam(name)
    except KeyError:
        return {"exists": False}
    return {"exists": True, "current_session": entry.pw_uid == os.geteuid(),
            "login_shell_disabled": entry.pw_shell in ("/usr/sbin/nologin", "/sbin/nologin", "/bin/false")}


def version(argv: list[str]) -> str | None:
    value = command(argv)
    match = re.search(r"\b(v?\d+\.\d+\.\d+)\b", value or "")
    return match.group(1) if match else None


def collect(repo_root: Path, project_os_root: Path) -> dict[str, object]:
    linux = platform.system() == "Linux"
    os_release = file_text(Path("/etc/os-release")) if linux else None
    release = dict(re.findall(r'^([A-Z_]+)=["\']?([^\n"\']*)', os_release or "", re.M))
    mdstat = file_text(Path("/proc/mdstat")) if linux else None
    md0 = re.search(r"^md0\s*:\s*active\s+raid1\b([^\n]*)(?:\n([^\n]*))?", mdstat or "", re.M)
    ssh = command(["ss", "-ltnH", "sport = :22"]) if linux else None
    listeners = [row for row in (ssh or "").splitlines() if row.strip()]
    virt = command(["systemd-detect-virt"]) if linux else None
    route = command(["ip", "-4", "route", "show", "default"]) if linux else None
    ts_ip = command(["tailscale", "ip", "-4"]) if shutil.which("tailscale") else None
    facts = {
        "platform": platform.system(),
        "ubuntu_24_04": release.get("ID") == "ubuntu" and release.get("VERSION_ID") == "24.04" if os_release is not None else None,
        "hostname_matches_office_pc": platform.node() == "amt-pc",
        "virtualization_detected": bool(virt and virt != "none") if linux else None,
        "md0_active_raid1": bool(md0) if mdstat is not None else None,
        "md0_reports_two_members_up": "[UU]" in md0.group(0) if md0 else None,
        "system_timezone": command(["timedatectl", "show", "-p", "Timezone", "--value"]) if linux else None,
        "ipv4_default_route_present": bool(route) if route is not None else None,
        "tailscale_ipv4_present": bool(ts_ip) if ts_ip is not None else None,
        "ssh_listener_count": len(listeners) if ssh is not None else None,
        "ssh_listeners_only_tailscale0": bool(listeners) and all("%tailscale0" in row for row in listeners) if ssh is not None else None,
        "accounts": {name: account(name) for name in ("owner", "builder", "amt-build")},
        "running_as_root": os.geteuid() == 0,
        "claude_binary_found": shutil.which("claude") is not None,
        "claude_version": version(["claude", "--version"]) if shutil.which("claude") else None,
        "node_version": version(["node", "--version"]),
        "repo_root_exists": repo_root.is_dir(),
        "project_os_root_exists": project_os_root.is_dir(),
        "claude_instructions_present": (project_os_root / "CLAUDE.md").is_file(),
        "project_os_is_repo_child": project_os_root.resolve() == (repo_root / "project-os").resolve(),
        "bootstrap_state_present": Path("/var/lib/amt-bootstrap").is_dir() if linux else None,
        "bootstrap_complete_marker_present": Path("/var/lib/amt-bootstrap/complete").is_file() if linux else None,
        "runtime_release_present": Path("/opt/wolter-amt/current").exists() if linux else None,
    }
    expected = {
        "ubuntu_24_04": True, "hostname_matches_office_pc": True, "md0_active_raid1": True,
        "md0_reports_two_members_up": True, "system_timezone": "UTC", "ipv4_default_route_present": True,
        "tailscale_ipv4_present": True, "ssh_listeners_only_tailscale0": True,
        "running_as_root": False, "claude_binary_found": True, "claude_instructions_present": True,
        "project_os_is_repo_child": True,
    }
    checks = {key: "unknown" if facts[key] is None else "match" if facts[key] == value else "mismatch"
              for key, value in expected.items()}
    return {
        "schema_version": 1,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only", "runtime_acceptance": "NOT_RUN", "admission": "requires_human_reconciliation",
        "facts": facts, "checks": checks,
        "manual_checks_required": [
            "Owner confirms office PC, existing data/workloads, backup and restore point before any mutation.",
            "Owner verifies both ESP boot paths, UPS/BIOS, Omada isolation/static addressing and Tailscale policy/device approval.",
            "Owner verifies account/group/sudo policy locally; no sudo or authentication files are read by this probe.",
            "Owner confirms Claude subscription/login in the builder session; auth state is never inspected or copied.",
            "Owner reconciles repository origin, clean/dirty work, pinned versions and every prerequisite HUMAN_GATE.",
            "Unknown or mismatch facts stay blockers; this report never approves a gate, rebuild, disk change or SSH change.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("/srv/builder/wolter-amt"))
    parser.add_argument("--project-os-root", type=Path, default=Path("/srv/builder/wolter-amt/project-os"))
    args = parser.parse_args()
    print(json.dumps(collect(args.repo_root, args.project_os_root), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
