#!/usr/bin/env python3
import argparse, os, re, json, subprocess, sys, textwrap, pathlib, datetime
from typing import Optional, Dict, Any

STATE_PATH = pathlib.Path.home() / ".genie_local_state.json"
HIST_PATH  = pathlib.Path.home() / ".genie_local_history"

DANGEROUS_PATTERNS = [
    r"rm\s+-rf\s+/\b",
    r"mkfs\.", r"\bumount\b", r"\bdd\b\s+if=",
    r"\bshutdown\b", r"\breboot\b",
    r"\bchown\s+-R\s+root\b",
    r"\bchmod\s+0{3,4}\b",
    r"\b:>\s*/\w",
]

SYSTEM_TEMPLATE = """You are a shell command generator.

Rules:
- Output ONLY a single shell command on one line, no markdown, no code fences, no quotes, no explanations, no "`".
- Prefer portable POSIX sh where possible (macOS/BSD compatible if feasible).
- Do not include comments.

Task: {task}
"""

REFINE_TEMPLATE = """You returned a wrong command previously.

Constraints:
- Output ONLY a single shell command on one line, no markdown, no code fences, no quotes, no explanations.
- Keep it portable POSIX sh when possible.
- Fix the issue while preserving the user's intent.

User task: {task}
Previous command: {prev_cmd}
Problem description (from user or stderr): {problem}
"""

EXPLAIN_TEMPLATE = """Explain briefly what the command does, in 1-5 bullet points, concise:
Command: {cmd}
"""

def call_ollama(model: str, prompt: str) -> str:
    try:
        out = subprocess.check_output(["ollama", "run", model, prompt], text=True)
        return out.strip()
    except subprocess.CalledProcessError as e:
        print(f"[err] ollama failed: {e}", file=sys.stderr)
        sys.exit(1)

def normalize_one_line(s: str) -> str:
    if not s:
        return ""
    s = s.strip()

    s = re.sub(r"^```[\w-]*\n?", "", s)
    s = re.sub(r"\n?```$", "", s)

    if s.startswith("`") and s.endswith("`"):
        s = s[1:-1].strip()

    s = re.sub(r"\s*\n\s*", " ", s)
    s = re.sub(r"\s{2,}", " ", s)

    return s.strip()

def is_dangerous(cmd: str) -> bool:
    for pat in DANGEROUS_PATTERNS:
        if re.search(pat, cmd):
            return True
    return False

def save_history(task: str, cmd: str):
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    HIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(HIST_PATH, "a") as f:
        f.write(f"[{ts}] TASK: {task}\n[{ts}] CMD:  {cmd}\n")

def load_state() -> Dict[str, Any]:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except Exception:
            return {}
    return {}

def save_state(task: str, cmd: str, last_error: Optional[str] = None, exit_code: Optional[int] = None):
    data = {
        "task": task,
        "cmd": cmd,
        "last_error": last_error or "",
        "exit_code": exit_code if exit_code is not None else "",
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    STATE_PATH.write_text(json.dumps(data, indent=2))

def suggest(model: str, task: str) -> str:
    prompt = SYSTEM_TEMPLATE.format(task=task)
    cmd = normalize_one_line(call_ollama(model, prompt))
    if not cmd or "\n" in cmd:
        print("[err] Model returned empty or multiline command. Refine your prompt.", file=sys.stderr)
        sys.exit(2)
    return cmd

def refine(model: str, task: str, prev_cmd: str, problem: str) -> str:
    prompt = REFINE_TEMPLATE.format(task=task, prev_cmd=prev_cmd, problem=problem.strip() or "no details")
    cmd = normalize_one_line(call_ollama(model, prompt))
    if not cmd or "\n" in cmd:
        print("[err] Model returned empty or multiline command. Try adding more detail to --why.", file=sys.stderr)
        sys.exit(2)
    return cmd

def explain(model: str, cmd: str) -> str:
    return call_ollama(model, EXPLAIN_TEMPLATE.format(cmd=cmd)).strip()

def main():
    ap = argparse.ArgumentParser(prog="genie-local", description="Local Genie using Ollama, with refine")
    ap.add_argument("task", nargs="*", help="What you want to do (natural language). Omit in refine if using --use-last.")
    ap.add_argument("--model", default=os.getenv("GENIE_MODEL", "mistral"),
                    help="Ollama model (default: mistral)")
    ap.add_argument("--mode", choices=["suggest","run","explain","refine"], default="suggest",
                    help="suggest (default), run (with confirm), explain, refine")
    ap.add_argument("--shell", default=os.getenv("SHELL", "/bin/bash"),
                    help="Shell to execute in run mode (default: current SHELL)")
    ap.add_argument("--no-history", action="store_true", help="Do not save history")
    # refine options
    ap.add_argument("--use-last", action="store_true", help="Use last saved task/command from state")
    ap.add_argument("--why", default="", help="Describe what was wrong (error message, behavior, platform constraints)")
    # explain option (explicit command)
    ap.add_argument("--cmd", default="", help="When using --mode explain, provide a command explicitly (optional)")

    args = ap.parse_args()
    state = load_state()

    if args.mode == "refine":
        # Determine task & prev_cmd
        if args.use_last:
            if not state.get("task") or not state.get("cmd"):
                print("[err] No previous state found. Run a suggest/run first.", file=sys.stderr)
                sys.exit(1)
            task = state["task"]
            prev_cmd = state["cmd"]
            problem = args.why or state.get("last_error","")
        else:
            if not args.task:
                print("[err] Provide a task (natural language) or use --use-last.", file=sys.stderr)
                sys.exit(1)
            task = " ".join(args.task)
            prev_cmd = state.get("cmd","")
            problem = args.why
            if not prev_cmd:
                print("[warn] No previous command in state; refining without prev_cmd context.", file=sys.stderr)

        cmd = refine(args.model, task, prev_cmd, problem)
        if not args.no_history:
            save_history(task, cmd)
        save_state(task, cmd)
        print(cmd)
        return

    # suggest / run / explain
    if args.mode == "suggest":
        if not args.task:
            print("[err] Provide a task.", file=sys.stderr)
            sys.exit(1)
        task = " ".join(args.task)
        cmd = suggest(args.model, task)
        if not args.no_history:
            save_history(task, cmd)
        save_state(task, cmd)
        print(cmd)
        return

    if args.mode == "explain":
        # prefer explicit command; fallback to last
        cmd = args.cmd.strip()
        if not cmd:
            cmd = state.get("cmd","")
            if not cmd:
                print("[err] Use --cmd '<command>' or --use-last with an existing state.", file=sys.stderr)
                sys.exit(1)
        print(textwrap.dedent(f"""\
        Command:
          {cmd}

        Explanation:
        {explain(args.model, cmd)}
        """))
        return

    if args.mode == "run":
        if not args.task:
            print("[err] Provide a task.", file=sys.stderr)
            sys.exit(1)
        task = " ".join(args.task)
        cmd = suggest(args.model, task)

        print(f"Suggested:\n  {cmd}\n")
        if is_dangerous(cmd):
            print("[warn] Command looks dangerous. Not running without explicit consent.", file=sys.stderr)
            confirm = input("Type 'YES' to run anyway: ").strip()
            if confirm != "YES":
                print("Aborted.")
                save_state(task, cmd)
                sys.exit(3)
        else:
            confirm = input("Run this command? [y/N]: ").lower().strip()
            if confirm not in ("y","yes"):
                print("Aborted.")
                save_state(task, cmd)
                sys.exit(0)

        # Execute
        try:
            completed = subprocess.run([args.shell, "-lc", cmd], capture_output=True, text=True)
            rc = completed.returncode
            if rc == 0:
                print(completed.stdout, end="")
                if not args.no_history:
                    save_history(task, cmd)
                save_state(task, cmd, last_error="", exit_code=0)
                sys.exit(0)
            else:
                # Show error and offer refine
                sys.stderr.write(completed.stderr)
                save_state(task, cmd, last_error=completed.stderr.strip(), exit_code=rc)
                print(f"\n[err] Command failed with exit code {rc}.", file=sys.stderr)
                choice = input("Refine based on this error? [y/N]: ").lower().strip()
                if choice in ("y","yes"):
                    improved = refine(args.model, task, cmd, completed.stderr)
                    print(f"\nImproved suggestion:\n  {improved}")
                    # Ask to run improved
                    confirm2 = input("Run improved command? [y/N]: ").lower().strip()
                    if confirm2 in ("y","yes"):
                        try:
                            res2 = subprocess.run([args.shell, "-lc", improved], check=True)
                            if not args.no_history:
                                save_history(task, improved)
                            save_state(task, improved, last_error="", exit_code=0)
                            sys.exit(0)
                        except subprocess.CalledProcessError as e:
                            print(f"[err] Improved command failed (exit {e.returncode}).", file=sys.stderr)
                            save_state(task, improved, last_error=f"exit {e.returncode}", exit_code=e.returncode)
                            sys.exit(e.returncode)
                    else:
                        save_state(task, improved)
                        sys.exit(0)
                else:
                    sys.exit(rc)
        except subprocess.CalledProcessError as e:
            print(f"[err] Command failed (exit {e.returncode}).", file=sys.stderr)
            save_state(task, cmd, last_error=f"exit {e.returncode}", exit_code=e.returncode)
            sys.exit(e.returncode)

if __name__ == "__main__":
    main()

