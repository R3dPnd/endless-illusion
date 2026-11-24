"""Pure gate rules for the engagement approval gate.

Decides (a) whether an agent's shell command / file write is local-only and may
be auto-allowed, and (b) whether the hosts a command touches are in the
engagement scope.

Security posture: when in doubt the answer is "gated" / "unknown" / "out" /
"denied" -- never "local" or "in".  Over-detection (a filename that looks like
a host, a `$` that is really an awk field) only causes extra gating; the
dangerous direction is under-detection, so every parser here is deliberately
strict and rejects anything it does not fully understand.
"""

from __future__ import annotations

import os
import pwd
import re
from pathlib import Path

LOCAL_COMMANDS: frozenset[str] = frozenset(
    "grep rg jq cat ls head tail wc sed awk sort uniq cut tr diff file echo pwd mkdir tee".split()
)

# ---------------------------------------------------------------- host extraction

# TLDs recognised for bare `name.tld` tokens.  Deliberately broad: a false hit
# only means extra gating.
_FILE_LIKE_TLDS = frozenset("sh py md rs pl zip mov".split())
_TLDS = frozenset(
    """com net org io dev app edu gov mil int info biz me us uk de fr ru cn jp in br nl it es se no fi ch at be
    pl cz tv cc xyz online site tech cloud ai so to ly co ca au nz za kr tw hk sg id vn th my ph mx ar cl pe ve
    ua tr gr pt ie dk hu ro bg sk si hr rs lt lv ee is il ae sa ir pk bd eu asia name pro mobi store shop blog
    top club vip link live life world today space website fun wiki page host cyber network systems security
    local internal lan home corp localhost test example invalid onion""".split()
) | _FILE_LIKE_TLDS

_URL_RE = re.compile(r"(?<![A-Za-z0-9_/.\-])(?:[A-Za-z][A-Za-z0-9+.\-]*:)?//([^\s'\"`<>/?#\\]+)")
_V6_RE = re.compile(r"\[([0-9A-Fa-f:.]*:[0-9A-Fa-f:.]*)\](?::(\d{1,5}))?")
_SPLIT_RE = re.compile(r"[^a-z0-9_.:\-]+")
_V6_TAIL_RE = re.compile(r"(?<![0-9a-z])(?:[0-9a-f]{0,4}:){2,}[0-9a-f.]{0,15}")
_TOKEN_RE = re.compile(r"^([a-z0-9_.\-]+?)(?::(\d{1,5}))?$")
_NUMERIC_IP_RE = re.compile(r"^(?:0x[0-9a-f]+|\d+)(?:\.(?:0x[0-9a-f]+|\d+)){1,3}$")
_INT_IP_RE = re.compile(r"^(?:0x[0-9a-f]+|\d{6,})$")
_LABEL_RE = re.compile(r"^[a-z0-9_\-]+$")

_INDIRECT_RE = re.compile(
    r"\$"  # any $: $VAR ${..} $(..) $'..' and zsh forms ($=X $~X $^X $[..])
    r"|`"
    r"|\beval\b|\bbase64\b|\bxxd\b"
    r"|\\x[0-9a-fA-F]{2}"
    r"|\{[^{}]*(?:,|\.\.)[^{}]*\}"  # brace expansion
    r"|[^\x00-\x7f]"  # non-ASCII: homoglyph / fullwidth-dot hosts
)


def _authority(auth: str) -> str | None:
    """`user:pw@host:port` -> `host` or `host:port` (lowercase), or None."""
    auth = auth.rsplit("@", 1)[-1].lower()
    if auth.startswith("["):
        end = auth.find("]")
        if end < 0:
            return None
        host, rest = auth[: end + 1], auth[end + 1 :]
        port = rest[1:] if rest.startswith(":") and rest[1:].isdigit() else ""
    else:
        host, _, port = auth.partition(":")
        if port and not port.isdigit():
            port = ""
        host = host.rstrip(".")
    if not host or host == "[]":
        return None
    return f"{host}:{port}" if port else host


def _scan_hosts(text: str, file_like: bool) -> list[str]:
    hosts: list[str] = []

    def add(h: str | None) -> None:
        if h and h not in hosts:
            hosts.append(h)

    low = text.lower()
    for m in _URL_RE.finditer(text):
        add(_authority(m.group(1)))
    for m in _V6_RE.finditer(text):
        add(f"[{m.group(1).lower()}]" + (f":{m.group(2)}" if m.group(2) else ""))

    def bare(h: str, port: str | None) -> None:
        h = h.strip(".-")
        if not h:
            return
        hp = f"{h}:{port}" if port else h
        if _INT_IP_RE.match(h) or _NUMERIC_IP_RE.match(h):
            # file_like=False (local-only commands): only unmistakable dotted quads
            if file_like or h.count(".") == 3:
                add(hp)
            return
        labels = h.split(".")
        if not all(_LABEL_RE.match(label) for label in labels):
            return
        if len(labels) >= 2 and labels[-1] in _TLDS:
            if not file_like and labels[-1] in _FILE_LIKE_TLDS:
                return
            add(hp)
        elif len(labels) == 1 and (h == "localhost" or (port and h[0].isalpha())):
            add(hp)

    for tok in _SPLIT_RE.split(low):
        tok = tok.strip(".:")
        if not tok:
            continue
        if tok.count(":") >= 2:
            for m in _V6_TAIL_RE.finditer(tok):
                v6 = m.group(0).strip(".")
                if v6 and not file_like and not re.search(r"[a-f]|::", v6):
                    continue  # looks like a clock time in a local-only command
                if v6:
                    add(v6)
        m = _TOKEN_RE.match(tok)
        if m:
            bare(m.group(1), m.group(2))
        elif ":" in tok:
            for part in tok.split(":"):
                bare(part.strip("."), None)
    return hosts


_KNOWN_HEADS = frozenset(
    "curl wget ssh nc nmap http httpie python python3 node ruby perl dig nslookup host ping".split()
) | LOCAL_COMMANDS
_BOOL_CLUSTER = frozenset("sSikLvfIqnN46")
_SHORT_METHOD = frozenset("X")
_SHORT_NUM = frozenset("mpPr")
_SHORT_VALUE = frozenset("xJKioOdHeAbcuTF")
# only output-file flags may take a workdir path (others read it as input); per program
_OUT_SHORT = {"curl": "o", "wget": "O"}
_OUT_LONG = {"curl": "--output", "wget": "--output-document"}
_LONG_METHOD = frozenset({"--request"})
_LONG_NUM = frozenset({"--max-time", "--connect-timeout", "--retry", "--limit-rate", "--max-redirs"})
_LONG_VALUE = frozenset(
    """--proxy --connect-to --resolve --output --data --header --referer --user-agent --cookie --cookie-jar
    --user --upload-file --form --proxy-user --config --interface --dns-servers --doh-url --socks5
    --socks5-hostname --preproxy --json --url --data-raw --data-binary --data-urlencode""".split()
)
_LONG_FLAG_RE = re.compile(r"^--[A-Za-z][A-Za-z0-9\-]*$")
_METHOD_RE = re.compile(r"^[A-Z]{3,10}$")
_NUM_RE = re.compile(r"^\d{1,6}$")
_URLWORD_RE = re.compile(r"^(?:[A-Za-z][A-Za-z0-9+.\-]*:)?//([^\s'\"`<>/?#\\]+)(?:[/?#]\S*)?$")
_USER_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")


def _recognized_value(word: str, workdir: Path | None, paths_ok: bool = False) -> bool:
    """True iff the whole word is exactly one host, `user@host`, a parsed URL,
    or an absolute path inside workdir -- no unaccounted-for fragments."""
    if paths_ok and workdir is not None and word.startswith("/") and _inside(word, workdir):
        return True
    m = _URLWORD_RE.match(word)
    if m:
        return _authority(m.group(1)) is not None
    if "@" in word:
        user, _, rest = word.rpartition("@")
        if not _USER_RE.match(user):
            return False
        word = rest
    word = word.lower().strip(".")
    hosts = _scan_hosts(word, True)
    return len(hosts) == 1 and hosts[0] == word


def _unclassified_words(text: str, workdir: Path | None) -> bool:
    """True if anything could hide an undetected host: an unknown program name,
    an unknown/attached-value flag, or a word that is not exactly one host/URL
    (or an absolute path inside workdir).  Integers and upper-case words are
    accepted only as the value of a known numeric / method flag."""
    try:
        toks = _tokenize_full(text.replace("\n", " ; ").replace("\r", " ; "), glob_ok=True)
    except _Unparseable:
        return True
    at_head = True
    expect: str | None = None  # "method" | "num" | "value"

    head = ""

    def check(kind: str, val: str) -> bool:
        if kind == "method":
            return bool(_METHOD_RE.match(val))
        if kind == "num":
            return bool(_NUM_RE.match(val))
        return _recognized_value(val, workdir, paths_ok=(kind == "out"))

    for kind, val, raw in toks:
        if kind == "op":
            at_head = val in _SPLIT_OPS
            expect = None
            continue
        # A word whose dequoted text differs from its raw text could hide a host from
        # the raw-text scan.  Exempt: the program head, quoted -X methods, local-command patterns.
        if raw != val and not at_head and expect != "method" and head not in LOCAL_COMMANDS:
            return True
        if at_head:
            at_head = False
            head = val
            if val not in _KNOWN_HEADS:
                return True
            continue
        if expect:
            ok = check(expect, val)
            expect = None
            if not ok:
                return True
            continue
        if val == "--":
            continue
        if val.startswith("--"):
            name, eq, value = val.partition("=")
            if not _LONG_FLAG_RE.match(name):
                return True
            kind_ = (
                "method" if name in _LONG_METHOD else "num" if name in _LONG_NUM
                else "out" if _OUT_LONG.get(head) == name else "value"
            )
            if eq:
                if not check(kind_, value):
                    return True
            elif name in _LONG_METHOD:
                expect = "method"
            elif name in _LONG_NUM:
                expect = "num"
            elif _OUT_LONG.get(head) == name:
                expect = "out"
            elif name in _LONG_VALUE:
                expect = "value"
            continue
        if val.startswith("-") and len(val) > 1:
            letters = val[1:]
            if len(letters) == 1 and letters.isalnum():
                if letters in _SHORT_METHOD:
                    expect = "method"
                elif letters in _SHORT_NUM:
                    expect = "num"
                elif _OUT_SHORT.get(head) == letters:
                    expect = "out"
                elif head == "curl" and letters == "O":
                    pass  # curl -O takes no value
                elif letters in _SHORT_VALUE:
                    expect = "value"
                continue
            if all(c in _BOOL_CLUSTER for c in letters):
                continue
            return True
        if not _recognized_value(val, workdir, paths_ok=head in LOCAL_COMMANDS):
            return True
    return expect is not None


def extract_hosts(
    text: str, *, file_like: bool = True, strict: bool = True, workdir: Path | None = None
) -> tuple[list[str], bool]:
    """Return `(hosts, indirect)` for a command line or URL text.

    Hosts come from URLs (any scheme, incl. single-label hosts), bracketed and
    unbracketed IPv6, `host:port` tokens, bare `name.tld` domains (known TLDs,
    found anywhere inside a token), `localhost`, IPv4 and obfuscated numeric IPs
    (hex / decimal / 2-4 part dotted).  Each is lowercased, as `host` or
    `host:port` (port only when explicit).

    `indirect` is True when the text can build or hide a host: any `$`,
    backticks, `eval`, `base64`/`xxd`, hex escapes, brace expansion, any
    non-ASCII character, an unparseable command line, and (with `strict`) any
    segment head that is not a known program, any word whose dequoted text differs
    from its raw text, any non-head word that is not exactly one host/URL (or a
    known-safe flag), and any flag value other than a host/URL, an upper-case
    method after `-X`/`--request`, a number after a known numeric flag, or an
    absolute `workdir` path as an output-file value.  A verdict on such
    text can never be trusted ("unknown").  Over-triggering is intentional.

    `file_like=False` ignores bare-domain matches whose TLD doubles as a common
    file extension (`.sh .py .md .rs .pl .zip .mov`) and lone numerics -- only
    used when no network-capable command is involved.  `strict=False` skips the
    word-classification rule (also for local-only commands).
    """
    hosts = _scan_hosts(text, file_like)
    indirect = bool(_INDIRECT_RE.search(text))
    if strict and not indirect:
        indirect = _unclassified_words(text, workdir)
        try:  # hosts seen in dequoted words must also be reported (raw/dequoted views never disagree)
            toks = _tokenize(text.replace("\n", " ; ").replace("\r", " ; "), glob_ok=True)
        except _Unparseable:
            toks = []
        for kind, val in toks:
            if kind == "word":
                for h in _scan_hosts(val, file_like):
                    if h not in hosts:
                        hosts.append(h)
    return hosts, indirect


# ---------------------------------------------------------------- scope verdicts


def _norm_entry(s: str) -> tuple[str, str | None] | None:
    """Normalise a scope entry or host to `(host, port)`; None if unusable."""
    s = s.strip().lower()
    s = re.sub(r"^(?:[a-z][a-z0-9+.\-]*:)?//", "", s)
    s = re.split(r"[/?#\\]", s, maxsplit=1)[0].rsplit("@", 1)[-1].strip()
    if s.startswith("["):
        end = s.find("]")
        if end < 0:
            return None
        host, rest = s[: end + 1], s[end + 1 :]
        if rest and not (rest.startswith(":") and rest[1:].isdigit()):
            return None
        port = rest[1:] or None
    elif s.count(":") == 1 and s.rsplit(":", 1)[1].isdigit():
        host, port = s.rsplit(":", 1)
    else:
        host, port = s, None
    host = host.rstrip(".").strip()
    return (host, port) if host else None


def _host_matches(host: str, port: str | None, entry: tuple[str, str | None]) -> bool:
    ehost, eport = entry
    if eport is not None and eport != port:
        return False
    if "*" in host:
        return False
    if ehost.startswith("*."):
        suffix = ehost[2:]
        if "." not in suffix or "*" in suffix:  # `*`, `*.com`: too broad, never matches
            return False
        return host.endswith("." + suffix) and len(host) > len(suffix) + 1
    if "*" in ehost:
        return False
    return host == ehost


def scope_verdict(hosts: list[str], indirect: bool, scope_hosts: list[str]) -> str:
    """`"unknown"` | `"none"` | `"out"` | `"in"` for hosts against scope entries.

    Both sides are normalised (lowercase, trimmed, trailing dot dropped; scope
    entries may carry a scheme/path/userinfo).  `*.example.com` matches
    subdomains only (not the apex).  A scope entry with a port matches only that
    port; one without matches any port.  A host *without* an explicit port only
    matches scope entries *without* a port (scheme-default ports are not
    guessed).  Any unparseable host is `out`.
    """
    if indirect:
        return "unknown"
    if not hosts:
        return "none"
    entries = [e for e in (_norm_entry(s) for s in scope_hosts if s and s.strip()) if e]
    for h in hosts:
        n = _norm_entry(h)
        if n is None or not any(_host_matches(n[0], n[1], e) for e in entries):
            return "out"
    return "in"


# ---------------------------------------------------------------- path rules


def _real_home() -> str:
    try:
        return pwd.getpwuid(os.getuid()).pw_dir
    except KeyError:
        return os.path.expanduser("~")


def _abs_resolved(path: str) -> Path | None:
    """Resolved absolute path, or None.  Relative paths are refused (the shell's
    cwd is not observable); only `~` and `~/...` tilde forms are expanded."""
    if not path or "\x00" in path:
        return None
    if path == "~" or path.startswith("~/"):
        path = _real_home() + path[1:]
    elif path.startswith("~"):
        return None  # ~user, ~-, ~+, ~N ...
    if not path.startswith("/"):
        return None
    try:
        return Path(path).resolve()
    except (OSError, ValueError, RuntimeError):
        return None


def _inside(path: str, workdir: Path) -> bool:
    r = _abs_resolved(path)
    if r is None:
        return False
    try:
        return r.is_relative_to(Path(workdir).resolve())
    except (OSError, ValueError, RuntimeError):
        return False


def _write_ok(path: str, workdir: Path) -> bool:
    """Absolute path resolving inside workdir whose basename cannot be an option."""
    return _inside(path, workdir) and not os.path.basename(path.rstrip("/")).startswith("-")


def classify_write(path: str, workdir: Path) -> str:
    """`"local"` if the path is absolute and resolves (symlinks, `..`, `~`) inside
    workdir, else `"denied"`.  Relative paths are denied."""
    return "local" if _inside(path, workdir) else "denied"


# ---------------------------------------------------------------- bash parsing

_OP_CHARS = set("|&;<>()")
_SPLIT_OPS = {"|", "&&", "||", ";"}
_REDIR_OPS = {">", ">>", ">|", "&>", "&>>"}


class _Unparseable(Exception):
    pass


def _tokenize_full(cmd: str, glob_ok: bool = False) -> list[tuple[str, str, str]]:
    """Minimal POSIX-ish tokenizer -> [("word"|"op", text)].  Raises on anything odd,
    including (unless glob_ok) any unquoted glob char: globs can inject options."""
    toks: list[tuple[str, str, str]] = []
    wstart = 0
    i, n = 0, len(cmd)
    cur: list[str] = []
    have = False
    while i < n:
        c = cmd[i]
        if c in " \t":
            if have:
                toks.append(("word", "".join(cur), cmd[wstart:i]))
                cur, have = [], False
            i += 1
        elif c in _OP_CHARS:
            if have:
                toks.append(("word", "".join(cur), cmd[wstart:i]))
                cur, have = [], False
            j = i
            while j < n and cmd[j] in _OP_CHARS:
                j += 1
            toks.append(("op", cmd[i:j], cmd[i:j]))
            i = j
        elif c == "'":
            end = cmd.find("'", i + 1)
            if end < 0:
                raise _Unparseable("unterminated '")
            cur.append(cmd[i + 1 : end])
            if not have:
                wstart = i
            have = True
            i = end + 1
        elif c == '"':
            qs = i
            i += 1
            while True:
                if i >= n:
                    raise _Unparseable('unterminated "')
                d = cmd[i]
                if d == '"':
                    i += 1
                    break
                if d == "\\":
                    if i + 1 >= n:
                        raise _Unparseable("dangling backslash")
                    nxt = cmd[i + 1]
                    cur.append(nxt if nxt in '"\\$`' else "\\" + nxt)
                    i += 2
                else:
                    cur.append(d)
                    i += 1
            if not have:
                wstart = qs
            have = True
        elif c == "\\":
            if i + 1 >= n:
                raise _Unparseable("dangling backslash")
            cur.append(cmd[i + 1])
            if not have:
                wstart = i
            have = True
            i += 2
        else:
            if c in "*?[" and not glob_ok:
                raise _Unparseable("unquoted glob")
            cur.append(c)
            if not have:
                wstart = i
            have = True
            i += 1
    if have:
        toks.append(("word", "".join(cur), cmd[wstart:i]))
    return toks


def _tokenize(cmd: str, glob_ok: bool = False) -> list[tuple[str, str]]:
    return [(k, v) for k, v, _ in _tokenize_full(cmd, glob_ok)]


def _parse_opts(args, short_ok, short_val, long_ok, long_val):
    """Strict option parse.  Returns positionals, or None if any option is unknown."""
    pos: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        i += 1
        if a == "--":
            pos.extend(args[i:])
            break
        if a.startswith("--"):
            name, eq, _ = a.partition("=")
            if name in long_val:
                if not eq:
                    i += 1
            elif name not in long_ok or eq:
                return None
        elif a.startswith("-") and a != "-":
            j = 1
            while j < len(a):
                ch = a[j]
                if ch in short_val:
                    if j + 1 == len(a):
                        i += 1
                    break
                if ch not in short_ok:
                    return None
                j += 1
        else:
            pos.append(a)
    return pos


_AWK_BAD_RE = re.compile(r"system|getline|popen|close|ENVIRON|[|>@]")


def _awk_ok(args: list[str]) -> bool:
    i = 0
    while i < len(args):
        a = args[i]
        i += 1
        if a == "--":
            continue
        if a.startswith("-") and a != "-":
            if a in ("-F", "-v"):
                if i < len(args) and _AWK_BAD_RE.search(args[i]):
                    return False
                i += 1
            elif a.startswith("-F") or (a.startswith("-v") and len(a) > 2):
                pass
            else:
                return False
        if _AWK_BAD_RE.search(a):
            return False
    return True


_SED_ADDR = r"(?:\d+|\$|/(?:\\.|[^/\\])*/)"


def _sed_script_safe(script: str) -> bool:
    """Only plain substitution / print / delete / quit commands; no e, w, r, y, {} etc."""
    pos, n = 0, len(script)
    cmd_re = re.compile(rf"\s*(?:{_SED_ADDR}(?:,{_SED_ADDR})?)?\s*!?\s*([pdq]|s(.))")
    while pos < n:
        while pos < n and script[pos] in " \t;":
            pos += 1
        if pos >= n:
            break
        m = cmd_re.match(script, pos)
        if not m:
            return False
        pos = m.end()
        if m.group(2):  # s<delim>...: consume pattern, replacement, flags
            d = re.escape(m.group(2))
            part = rf"(?:\\.|(?!{d})[^\\])*{d}"
            m2 = re.compile(rf"{part}{part}([gIip0-9]*)").match(script, pos)
            if not m2:
                return False
            pos = m2.end()
    return True


def _sed_ok(args: list[str], workdir: Path) -> bool:
    scripts: list[str] = []
    files: list[str] = []
    in_place = False
    i = 0
    while i < len(args):
        a = args[i]
        i += 1
        if a == "--":
            files.extend(args[i:])
            break
        if a.startswith("--"):
            name, eq, val = a.partition("=")
            if name in ("--quiet", "--silent", "--regexp-extended", "--posix", "--null-data", "--separate") and not eq:
                continue
            if name == "--in-place" and not eq:  # a backup suffix could point anywhere
                in_place = True
                continue
            if name == "--expression":
                if eq:
                    scripts.append(val)
                elif i < len(args):
                    scripts.append(args[i])
                    i += 1
                else:
                    return False
                continue
            return False
        if a.startswith("-") and a != "-":
            j = 1
            while j < len(a):
                ch = a[j]
                if ch in "nEsrz":
                    j += 1
                elif ch == "i":
                    if j + 1 != len(a):
                        return False  # `-iSUFFIX`: backup file could land outside workdir
                    in_place = True
                    break
                elif ch == "e":
                    rest = a[j + 1 :]
                    if rest:
                        scripts.append(rest)
                    elif i < len(args):
                        scripts.append(args[i])
                        i += 1
                    else:
                        return False
                    break
                else:
                    return False
        else:
            files.append(a)
    if not scripts:
        if not files:
            return False
        scripts.append(files.pop(0))
    if not all(_sed_script_safe(s) for s in scripts):
        return False
    return not in_place or all(_write_ok(f, workdir) for f in files)


def _args_ok(head: str, args: list[str], workdir: Path) -> bool:
    """Per-command safety for LOCAL_COMMANDS members (no exec / no write outside workdir)."""
    if head == "awk":
        return _awk_ok(args)
    if head == "sed":
        return _sed_ok(args, workdir)
    if head == "tee":
        pos = _parse_opts(args, "aip", "", {"--append", "--ignore-interrupts"}, set())
        return pos is not None and all(_write_ok(p, workdir) for p in pos)
    if head == "mkdir":
        pos = _parse_opts(args, "pv", "", {"--parents", "--verbose"}, set())
        return pos is not None and bool(pos) and all(_write_ok(p, workdir) for p in pos)
    if head == "sort":
        pos = _parse_opts(
            args,
            "nrufbdgihMVsRzcC",
            "kt",
            {
                "--numeric-sort", "--reverse", "--unique", "--ignore-case", "--ignore-leading-blanks",
                "--dictionary-order", "--general-numeric-sort", "--human-numeric-sort", "--month-sort",
                "--version-sort", "--stable", "--zero-terminated", "--check", "--ignore-nonprinting",
            },
            {"--key", "--field-separator"},
        )
        return pos is not None
    if head == "uniq":
        pos = _parse_opts(
            args,
            "cdiuz",
            "fsw",
            {"--count", "--repeated", "--ignore-case", "--unique", "--zero-terminated"},
            {"--skip-fields", "--skip-chars", "--check-chars"},
        )
        return pos is not None and all(_write_ok(p, workdir) for p in pos)
    if head == "rg":
        return not any(a.startswith(("--pre", "--hostname-bin")) for a in args)
    if head == "file":
        return not any(a.startswith("--c") or (a.startswith("-") and not a.startswith("--") and "C" in a) for a in args)
    return True


def classify_bash(command: str, workdir: Path) -> str:
    """`"local"` only when the command provably stays local; otherwise `"gated"`.

    Local means: every `|`/`&&`/`||`/`;` segment starts with a bare
    `LOCAL_COMMANDS` name (so `env curl`, `bash -c`, `/usr/bin/curl` are gated);
    no hosts, no indirection (`$VAR`, `$(..)`, backticks, `eval`, ...), no
    `xargs`, no `&`, subshells, `<`, `<(`/`>(`, newlines; per-command argument
    checks (awk/sed cannot exec or write, sort/rg/file cannot spawn programs);
    and every `>`, `>>`, `tee`, `mkdir`, `sed -i` target resolves inside
    `workdir` (`/dev/null` excepted).  Unparseable input is gated.
    """
    if not command or not command.strip() or any(c in command for c in "\n\r\x00"):
        return "gated"
    hosts, indirect = extract_hosts(command, file_like=False, strict=False)
    if hosts or indirect:
        return "gated"
    try:
        toks = _tokenize(command)
    except _Unparseable:
        return "gated"

    segments: list[list[str]] = [[]]
    i = 0
    while i < len(toks):
        kind, val = toks[i]
        i += 1
        if kind == "word":
            if val == "xargs":
                return "gated"
            segments[-1].append(val)
        elif val in _SPLIT_OPS:
            segments.append([])
        elif val in _REDIR_OPS or val == ">&":
            if i >= len(toks) or toks[i][0] != "word":
                return "gated"
            target = toks[i][1]
            i += 1
            if val == ">&" and (target == "-" or target.isdigit()):
                continue  # fd duplication, e.g. 2>&1
            if target != "/dev/null" and not _write_ok(target, workdir):
                return "gated"
        else:
            return "gated"  # &, (, ), <, <<, <(, >(, |&, ;; ...

    cmds = [s for s in segments if s]
    if not cmds:
        return "gated"
    for words in cmds:
        head, args = words[0], words[1:]
        if head not in LOCAL_COMMANDS or not _args_ok(head, args, workdir):
            return "gated"
    return "local"
