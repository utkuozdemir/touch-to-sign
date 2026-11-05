#!/usr/bin/env python3
"""No key access, installed binaries, or user configuration changes."""
import json
import os
from pathlib import Path
import pty
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent


def executable(path, text):
    path.write_text(text)
    path.chmod(0o755)


def check_streams(wrapper, env):
    args = ["-T", "host with spaces", "", "$(not-a-command)", "a'b", "é"]
    result = subprocess.run([str(wrapper), *args], input=b"stdin bytes\n", capture_output=True, env=env, timeout=10)
    record = json.loads(result.stdout)
    x11 = [] if env.get("DISPLAY") else ["-o", "ForwardX11=no"]
    assert record["argv"] == x11 + args, record
    assert record["stdin"] == "stdin bytes\n", record
    assert not record["tty2"], record
    assert record["require"] == "never", record
    assert record["display"] == (env.get("DISPLAY") or ":0"), record
    assert Path(record["askpass"]) == wrapper.resolve(), record
    assert record["hint"] is None, record
    assert result.stderr == b"stderr bytes\n", result
    assert result.returncode == int(env.get("STATUS", "0")), result


def lifetime(command, env):
    p = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        time.sleep(0.2)
        assert p.poll() is None, p.communicate()
        p.terminate()
        out, err = p.communicate(timeout=5)
        assert p.returncode == -signal.SIGTERM and not out and not err, (p.returncode, out, err)
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()


with tempfile.TemporaryDirectory(prefix="touch-to-sign-test-", dir="/tmp") as directory:
    tmp = Path(directory)
    binary = tmp / "touch-to-sign"
    wrapper = tmp / "touch-to-sign-ssh"
    shutil.copy2(ROOT / "touch-to-sign-ssh", wrapper)
    subprocess.run(["swiftc", "-O", "-o", str(tmp / "ui-build"), str(ROOT / "touch-to-sign.swift")], check=True)
    subprocess.run(["swiftc", "-D", "HEADLESS_TESTS", "-o", str(binary), str(ROOT / "touch-to-sign.swift")], check=True)
    stub = f"#!{sys.executable}\n" + '''import json, os, signal, sys, time
if os.environ.get("WAIT"):
    def bye(sig, _):
        sys.stderr.write("bye\\n")
        sys.stderr.flush()
        signal.signal(sig, signal.SIG_DFL)
        os.kill(os.getpid(), sig)
    signal.signal(signal.SIGINT, bye)
    print("ready", flush=True)
    while True: time.sleep(1)
if os.environ.get("TTY"):
    terminal = os.open("/dev/tty", os.O_RDONLY)
    os.close(terminal)
    print(json.dumps([os.isatty(0), os.isatty(1), os.isatty(2)]), flush=True)
    sys.exit(0)
print(json.dumps(dict(argv=sys.argv[1:], stdin=sys.stdin.read(), tty2=os.isatty(2),
    require=os.environ.get("SSH_ASKPASS_REQUIRE"), display=os.environ.get("DISPLAY"),
    askpass=os.environ.get("SSH_ASKPASS"), hint=os.environ.get("SSH_ASKPASS_PROMPT"))))
sys.stderr.write("stderr bytes\\n")
sys.exit(int(os.environ.get("STATUS", "0")))
'''
    executable(tmp / "ssh", stub)
    executable(tmp / "git", "#!/bin/sh\nexit 1\n")  # never consult user's git config
    executable(tmp / "gpg", stub)
    env = {**os.environ, "PATH": str(tmp) + ":" + os.environ["PATH"]}
    for name in ("SSH_ASKPASS_PROMPT", "DISPLAY", "WAYLAND_DISPLAY", "WAIT", "TTY", "STATUS"):
        env.pop(name, None)
    env["SSH_ASKPASS_REQUIRE"] = "force"  # must be overridden
    for code in (0, 1, 47):
        check_streams(wrapper, {**env, "STATUS": str(code)})
    check_streams(wrapper, {**env, "DISPLAY": ":77"})
    print("PASS exact argv, separate streams, stdin, stderr nonTTY, environment, exits 0/1/47")

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        p = subprocess.Popen([str(wrapper)], env={**env, "WAIT": "1"}, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            assert select.select([p.stdout], [], [], 5)[0], "SSH did not start"
            assert p.stdout.readline() == b"ready\n"
            p.send_signal(sig)
            p.communicate(timeout=5)
            assert p.returncode == -sig, (sig, p.returncode)
        finally:
            if p.poll() is None:
                p.kill()
                p.wait()
    print("PASS direct SIGINT/SIGTERM/SIGHUP reach SSH with exact signal status")

    # Ctrl-C goes to the whole process group; ssh's last stderr must still get through.
    p = subprocess.Popen([str(wrapper)], env={**env, "WAIT": "1"}, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        assert select.select([p.stdout], [], [], 5)[0], "SSH did not start"
        assert p.stdout.readline() == b"ready\n"
        os.killpg(p.pid, signal.SIGINT)
        _, err = p.communicate(timeout=5)
        assert p.returncode == -signal.SIGINT and err == b"bye\n", (p.returncode, err)
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()
    print("PASS Ctrl-C on the process group keeps ssh's last stderr")

    child, master = pty.fork()
    if child == 0:
        os.execve(str(wrapper), [str(wrapper)], {**env, "TTY": "1"})
    try:
        assert select.select([master], [], [], 5)[0]
        output = os.read(master, 4096)
        _, status = os.waitpid(child, 0)
        assert status == 0 and json.loads(output) == [True, True, False], (status, output)
    finally:
        os.close(master)
    print("PASS controlling /dev/tty and tty stdin/stdout preserved; stderr alone piped")

    for hint in (None, "", "confirm", "anything"):
        e = dict(env)
        if hint is not None:
            e["SSH_ASKPASS_PROMPT"] = hint
        p = subprocess.run([str(binary), "--ssh-askpass", "dummy"], env=e, capture_output=True, timeout=5)
        assert p.returncode != 0 and not p.stdout and not p.stderr, p
    for args in (["--ssh-askpass"], ["--ssh-askpass", "one", "two"]):
        p = subprocess.run([str(binary), *args], env={**env, "SSH_ASKPASS_PROMPT": "none"}, capture_output=True, timeout=5)
        assert p.returncode != 0 and not p.stdout and not p.stderr
    for hint in ("confirm", "unknown"):
        p = subprocess.run([str(wrapper), "dummy"], env={**env, "SSH_ASKPASS_PROMPT": hint}, capture_output=True, timeout=5)
        assert p.returncode != 0 and not p.stdout and not p.stderr
    for command in ([str(binary), "--ssh-askpass", "dummy"], [str(wrapper), "dummy"]):
        lifetime(command, {**env, "SSH_ASKPASS_PROMPT": "none"})
    print("PASS notification lifetime/SIGTERM, silent secret/confirmation/malformed rejection, wrapper dispatch")

    for args in (["--verify", "file with spaces"], ["--sign", "file with spaces"]):
        p = subprocess.run([str(binary), *args], input=b"gpg input", env={**env, "STATUS": "47"}, capture_output=True, timeout=5)
        record = json.loads(p.stdout)
        assert p.returncode == 47 and record["argv"] == args and record["stdin"] == "gpg input" and p.stderr == b"stderr bytes\n", p
    print("PASS existing GPG verify/sign argv, stdin/stdout/stderr and exit passthrough")

    # Mutation checks prove the tests detect wrong stream handling and exit swallowing.
    original = wrapper.read_text()
    for old, new in (("2> >(/bin/cat >&2)", "2>&1"), ("exec ssh \"${x11[@]}\" \"$@\"", "ssh \"${x11[@]}\" \"$@\"; exit 0 #"), ("SSH_ASKPASS_REQUIRE=never", "SSH_ASKPASS_REQUIRE=force")):
        assert old in original
        executable(wrapper, original.replace(old, new))
        try:
            check_streams(wrapper, {**env, "STATUS": "47"})
        except (AssertionError, json.JSONDecodeError):
            pass
        else:
            raise AssertionError("mutation escaped: " + old)
    print("PASS mutations: merged stderr, swallowed SSH status, forced GUI auth")
print("All tests passed; no real SSH, GPG key, or user configuration accessed.")
