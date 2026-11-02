"""Pre-publish check: nothing private in the files, the git history or the commit authors.

1. Generic patterns in every tracked file (and in new, not ignored ones): IP addresses, `host:port`, API tokens,
   private keys, home paths and e-mail addresses. Only loopback with the default llama-server (8080) and Ollama
   (11434) ports and GitHub noreply e-mails are allowed.
2. Private terms from a list OUTSIDE the repository (PRIVATE_TERMS_FILE): project, people and machine names. The list
   is not shipped, so it does not reveal what it protects.
3. Authors, e-mails and messages of every commit, against the same terms.
4. gitleaks (when installed) on the directory and the history, with .gitleaks.toml.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "IPv4": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "host:port": re.compile(r"\b[\w.-]+:\d{2,5}\b(?=/|\s|$|\)|`|\")"),
    "OpenRouter/OpenAI token": re.compile(r"\bsk-(?:or-v1-|proj-)?[A-Za-z0-9_-]{16,}"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"),
    "RunPod token": re.compile(r"\brpa_[A-Za-z0-9]{20,}"),
    "Hugging Face token": re.compile(r"\bhf_[A-Za-z0-9]{20,}"),
    "AWS key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "Bearer": re.compile(r"Bearer\s+[A-Za-z0-9._-]{16,}"),
    "home path": re.compile(r"(?:/Users/|/home/)[A-Za-z0-9._-]+"),
    "e-mail": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
}
ALLOWED = {
    "IPv4": re.compile(r"^(127\.0\.0\.1|0\.0\.0\.0)$"),
    "host:port": re.compile(r"^(localhost|127\.0\.0\.1):(8080|11434)$|^[\w.-]+:\d{2}$"),
    "e-mail": re.compile(r"@users\.noreply\.github\.com$", re.I),
}
SKIP_FILES = {".gitleaks.toml"}
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".gguf", ".zip", ".gz"}
SERIOUS_IN_HISTORY = ("private term", "OpenRouter/OpenAI token", "GitHub token", "private key", "IPv4")


def private_terms(env=os.environ):
    path = env.get("PRIVATE_TERMS_FILE")
    if not path:
        return None
    p = Path(path).expanduser()
    if not p.exists():
        raise FileNotFoundError("PRIVATE_TERMS_FILE points to a file that does not exist")
    return [t.strip().lower() for t in p.read_text(encoding="utf-8").splitlines()
            if t.strip() and not t.strip().startswith("#")]


def findings(text, terms=()):
    """(kind, masked excerpt). The excerpt is never printed in full: it may be a secret."""
    out = []
    low = text.lower()
    for t in terms:
        if t in low:
            out.append(("private term", "(from the list)"))
    for name, rx in PATTERNS.items():
        for m in rx.finditer(text):
            hit = m.group(0)
            if name in ALLOWED and ALLOWED[name].search(hit):
                continue
            out.append((name, hit[:4] + "…"))
    return out


def _git(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def files():
    names = _git("ls-files", "--cached", "--others", "--exclude-standard").splitlines()
    return [ROOT / n for n in names if n and (ROOT / n).is_file()]


def check(terms, use_gitleaks=True, log=print):
    problems = 0
    for path in files():
        if path.name in SKIP_FILES or path.suffix.lower() in BINARY_SUFFIXES:
            continue
        rel = path.relative_to(ROOT)
        for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for kind, hit in findings(line, terms):
                log(f"  {rel}:{i}: {kind} {hit}")
                problems += 1
        if terms and any(t in str(rel).lower() for t in terms):
            log(f"  {rel}: private term in the file name")
            problems += 1
    history = _git("log", "--all", "--format=%an%n%ae%n%cn%n%ce%n%B")
    for kind, _ in findings(history, terms):
        if kind in SERIOUS_IN_HISTORY:
            log(f"  git history: {kind}")
            problems += 1
    emails = {e for e in _git("log", "--all", "--format=%ae%n%ce").split() if e}
    for e in sorted(emails):
        if not ALLOWED["e-mail"].search(e):
            log(f"  commit e-mail is not a GitHub noreply address ({e.split('@')[-1]}); change it before pushing")
            problems += 1
    if use_gitleaks:
        if shutil.which("gitleaks"):
            for mode in (["dir", "."], ["git", "."]):
                r = subprocess.run(["gitleaks", *mode, "--config", ".gitleaks.toml", "--redact", "--no-banner"],
                                   cwd=ROOT, capture_output=True, text=True)
                if r.returncode != 0:
                    log(f"  gitleaks {mode[0]}: found something (run `gitleaks {mode[0]} . --config .gitleaks.toml "
                        "--redact -v` to see it)")
                    problems += 1
        else:
            log("  warning: gitleaks is not installed (Mac: brew install gitleaks); only the built-in check ran")
    return problems


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        terms = private_terms()
    except FileNotFoundError as e:
        print(f"error: {e}")
        return 2
    if terms is None and "--no-private-terms" not in argv:
        print("error: set PRIVATE_TERMS_FILE to the private list of terms (outside this repository), or pass "
              "--no-private-terms (testing only: not valid for publishing)")
        return 2
    print(f"Checking {ROOT.name} ({len(terms or [])} private terms)…")
    n = check(terms or [], use_gitleaks="--no-gitleaks" not in argv)
    print("OK: nothing private found." if n == 0 else f"STOP: {n} problem(s). Do not publish.")
    return 0 if n == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
