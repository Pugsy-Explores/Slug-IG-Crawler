#!/usr/bin/env python3
"""V1 day-end closeout: update memory files and append WORK_LOG.md. Stdlib only."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MEMORY = REPO_ROOT / ".ai" / "memory"
CURRENT_STATE = MEMORY / "CURRENT_STATE.md"
HANDOFF = MEMORY / "HANDOFF.md"
WORK_LOG = REPO_ROOT / "WORK_LOG.md"


def detect_flavor() -> str:
    if (REPO_ROOT / "src" / "thor").is_dir():
        return "thor"
    if (REPO_ROOT / "src" / "igscraper").is_dir():
        return "ig"
    sys.exit("day_end: unsupported repo (expected thor or ig_profile_scraper layout).")


def read_multiline(label: str, optional: bool = False) -> str:
    if optional:
        end = "(optional: type . alone on a line for none)"
    else:
        end = "(finish with a line containing only .)"
    print(f"\n{label}\n{end}")
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == ".":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def format_bullets(block: str) -> str:
    out: list[str] = []
    for raw in block.splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith("- "):
            out.append(s)
        elif s.startswith("* "):
            out.append("- " + s[2:].lstrip())
        else:
            out.append(f"- {s}")
    return "\n".join(out) if out else "- (none)"


def find_h2_span(text: str, heading: str) -> tuple[int, int] | None:
    m = re.search(re.escape(heading) + r"\r?\n", text)
    if not m:
        return None
    start = m.start()
    tail = text[m.end() :]
    m2 = re.search(r"(?m)^## .+$", tail)
    if m2:
        end = m.end() + m2.start()
    else:
        end = len(text)
    return (start, end)


def replace_h2_section(text: str, heading: str, body: str) -> str:
    span = find_h2_span(text, heading)
    if span is None:
        raise ValueError(f"Missing heading: {heading}")
    start, end = span
    return text[:start] + heading + "\n" + body.rstrip() + "\n" + text[end:]


def insert_before_heading(text: str, before_heading: str, block: str) -> str:
    pos = text.find(before_heading)
    if pos == -1:
        raise ValueError(f"Missing anchor heading: {before_heading}")
    return text[:pos] + block.rstrip() + "\n\n" + text[pos:]


def update_session_date_handoff(text: str, flavor: str, day: str) -> str:
    if flavor == "thor":
        text = re.sub(
            r"\*\*Session date:\*\*\s*.*",
            f"**Session date:** {day}",
            text,
            count=1,
        )
    else:
        text = re.sub(
            r"\*\*Session:\*\*\s*.*",
            f"**Session:** {day}",
            text,
            count=1,
        )
    return text


def update_last_touched(text: str, stamp: str) -> str:
    return re.sub(
        r"(\*\*Last touched:\*\*)\s*.*",
        rf"\1 {stamp}",
        text,
        count=1,
    )


def day_end_snapshot_body(
    completed: str, next_task: str, blockers: str, resume: str
) -> str:
    b = blockers.strip() or "None"
    return (
        f"- **Status / completed today:**\n{format_bullets(completed)}\n"
        f"- **Next:** {next_task.strip()}\n"
        f"- **Blockers:** {b}\n"
        f"- **Resume:** {resume.strip() or '(none)'}\n"
    )


def apply_handoff(
    text: str,
    flavor: str,
    completed: str,
    proof: str,
    next_task: str,
    blockers: str,
    resume: str,
) -> str:
    proof_heading = "## Proof / tests run"
    if flavor == "thor":
        text = replace_h2_section(
            text, "## Completed this session", format_bullets(completed)
        )
        if proof_heading in text:
            text = replace_h2_section(text, proof_heading, format_bullets(proof))
        else:
            text = insert_before_heading(
                text,
                "## Exact next task",
                proof_heading + "\n" + format_bullets(proof),
            )
        text = replace_h2_section(
            text,
            "## Exact next task",
            f"- **One line:** {next_task.strip()}",
        )
        text = replace_h2_section(text, "## Blockers", format_bullets(blockers or "None"))
        text = replace_h2_section(
            text, "## Resume pointer", format_bullets(resume or "(none)")
        )
    else:
        text = replace_h2_section(text, "## Done this session", format_bullets(completed))
        if proof_heading in text:
            text = replace_h2_section(text, proof_heading, format_bullets(proof))
        else:
            text = insert_before_heading(
                text,
                "## Next task (one line)",
                proof_heading + "\n" + format_bullets(proof),
            )
        text = replace_h2_section(
            text, "## Next task (one line)", f"- {next_task.strip()}"
        )
        text = replace_h2_section(text, "## Blockers", format_bullets(blockers or "None"))
        text = replace_h2_section(text, "## Resume", format_bullets(resume or "(none)"))
    return text


def apply_current_state(text: str, completed: str, next_task: str, blockers: str, resume: str, stamp: str) -> str:
    text = update_last_touched(text, stamp)
    snap = "## Day-end snapshot"
    body = day_end_snapshot_body(completed, next_task, blockers, resume)
    if find_h2_span(text, snap) is not None:
        text = replace_h2_section(text, snap, body)
    else:
        text = text.rstrip() + "\n\n" + snap + "\n" + body
    return text


def append_work_log(
    path: Path,
    day: str,
    completed: str,
    proof: str,
    next_task: str,
    blockers: str,
    resume: str,
    dry_run: bool,
) -> None:
    blk = blockers.strip() or "None"
    entry = (
        f"\n## {day}\n\n### Completed\n\n{completed}\n\n### Proof\n\n{proof}\n\n"
        f"### Next\n\n{next_task}\n\n### Blockers\n\n{blk}\n\n### Resume\n\n{resume}\n"
    )
    if dry_run:
        print(f"\n--- WORK_LOG append ({path}) ---\n{entry}\n--- end ---\n")
        return
    if path.exists():
        existing = path.read_text(encoding="utf-8")
    else:
        existing = "# Work log\n\nAutomated entries from `scripts/day_end.py`.\n"
    new_content = existing.rstrip() + entry
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(new_content, encoding="utf-8")
    tmp.replace(path)


def safe_write(path: Path, content: str, dry_run: bool) -> None:
    if dry_run:
        print(f"\n--- {path} (dry-run) ---\n{content}\n--- end ---\n")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def run_checks(flavor: str, dry_run: bool) -> None:
    if dry_run:
        print("\n(dry-run: skipping subprocess checks)\n")
        return
    if flavor == "thor":
        script = REPO_ROOT / "scripts" / "check_prerequisites.py"
        if not script.is_file():
            print("thor-release-check (automated slice): check_prerequisites.py missing; skip.")
            return
        print("\nRunning: python scripts/check_prerequisites.py (thor release-check slice)\n")
        r = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(REPO_ROOT),
            check=False,
        )
        if r.returncode != 0:
            sys.exit(r.returncode)
        print("\nFull checklist: .ai/commands/thor-release-check.md\n")
    else:
        tests = [
            "src/igscraper/tests/test_load_schema.py",
            "src/igscraper/tests/test_flatten_schema_contract.py",
            "src/igscraper/tests/test_parser_golden_contract.py",
            "src/igscraper/tests/test_thor_worker_id.py",
        ]
        cmd = [sys.executable, "-m", "pytest"] + tests + ["-q"]
        print("\nRunning ig-workflow-check step 1:\n", " ".join(cmd), "\n")
        r = subprocess.run(cmd, cwd=str(REPO_ROOT), check=False)
        if r.returncode != 0:
            sys.exit(r.returncode)


def main() -> None:
    flavor = detect_flavor()
    ap = argparse.ArgumentParser(description="Day-end closeout: memory + WORK_LOG.")
    ap.add_argument("--dry-run", action="store_true", help="Print changes only; no writes.")
    ap.add_argument(
        "--run-checks",
        action="store_true",
        help="Run release/workflow checks (skipped in --dry-run).",
    )
    args = ap.parse_args()

    completed = read_multiline("1) Completed work today (multi-line bullets)")
    proof = read_multiline("2) Proof / tests run (multi-line)")
    next_task = read_multiline("3) Next task (single line — use one line then .)", optional=False)
    if "\n" in next_task.strip():
        next_task = next_task.strip().splitlines()[0]
    blockers = read_multiline("4) Blockers (optional — empty line then . for none)", optional=True)
    resume = read_multiline("5) Resume pointer (file / command / location)")

    day = datetime.now().date().isoformat()
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")

    if args.run_checks:
        run_checks(flavor, args.dry_run)

    try:
        cs = CURRENT_STATE.read_text(encoding="utf-8")
        ho = HANDOFF.read_text(encoding="utf-8")
    except OSError as e:
        sys.exit(f"day_end: cannot read memory files: {e}")

    ho = update_session_date_handoff(ho, flavor, day)
    ho = apply_handoff(ho, flavor, completed, proof, next_task, blockers, resume)
    cs = apply_current_state(cs, completed, next_task, blockers, resume, stamp)

    safe_write(CURRENT_STATE, cs, args.dry_run)
    safe_write(HANDOFF, ho, args.dry_run)
    try:
        append_work_log(WORK_LOG, day, completed, proof, next_task, blockers, resume, args.dry_run)
    except OSError as e:
        if not args.dry_run:
            sys.exit(f"day_end: WORK_LOG update failed: {e}")

    if not args.dry_run:
        print("\nDone: CURRENT_STATE.md, HANDOFF.md, WORK_LOG.md updated.\n")


if __name__ == "__main__":
    main()
