"""Nothing another person is given stands on an address that can change.

2026-11-12: a connector tested on a laptop behind a quick tunnel was handed to two colleagues in direct messages
that carried the tunnel's address. One relied on it for real work, and when the laptop's app restarted the address
was gone for good. With `temporary_addresses` in the config, a send, draft or post whose text holds a quick-tunnel
host or an address only this machine answers is refused, and the ordinary approval of the message does not release
it: only an approval of the address itself does. Starting a quick tunnel waits for a code of its own. No key, no rule.
"""

import pytest

from synthesis import approvals, guards
from test_desktop_sends import CONFIG as DESKTOP, TYPE, WHATSAPP

SEND, DRAFT = "mcp__chat__slack_send_message", "mcp__mail__draft_gmail_message"
CONFIG = {"send_tools": ["mcp__*__slack_send_message", "mcp__*__draft_gmail_message"], "temporary_addresses": {}}
TUNNEL = "https://quiet-river-1234.trycloudflare.com/mcp"


def said(text, tool=SEND, config=CONFIG, session=None):
    return guards.check(tool, {"channel_id": "D1", "message": text}, config, cwd="/tmp", session=session)


def held_for_the_address(reason) -> bool:
    return bool(reason) and "never given to anyone" in reason


def test_a_message_that_carries_a_quick_tunnels_address_is_refused_and_no_send_code_is_issued():
    reason = said(f"Here are the setup steps. The address is {TUNNEL}")
    assert held_for_the_address(reason) and "quiet-river-1234.trycloudflare.com" in reason
    assert "permanent address" in reason and "Sending needs" not in reason
    assert len(approvals.pending()) == 1                                # the address's own code, not the message's


def test_the_ordinary_approval_of_the_message_does_not_release_it(principal):
    call = {"channel_id": "D1", "message": f"Use {TUNNEL}"}
    code = approvals.request("send", {"tool": SEND, "input": call}, "an ordinary send")
    principal(f"code {code}")
    assert held_for_the_address(guards.check(SEND, call, CONFIG, cwd="/tmp"))


def test_an_approval_of_the_address_itself_lets_the_message_go_on_to_its_own_approval(principal):
    text = f"My own test is at {TUNNEL}"
    principal(said(text))                                               # the principal approves this address
    reason = said(text)
    assert "Sending needs the principal's approval" in reason           # and now the message, as any send
    principal(reason)
    assert said(text) is None


def test_the_approval_names_the_address_and_covers_no_other(principal):
    principal(said(f"My own test is at {TUNNEL}"))
    other = said("And the second one: https://other-name-99.trycloudflare.com")
    assert held_for_the_address(other) and "other-name-99" in other


@pytest.mark.parametrize("text", [
    "https://abc.trycloudflare.com", "abc.trycloudflare.com", "HTTPS://ABC.TRYCLOUDFLARE.COM/x", "see abc.ngrok.io:443/path",
    "https://a1b2.ngrok-free.app", "https://a1b2.ngrok.app", "https://a1b2.ngrok.dev", "http://shy-cat.loca.lt",
    "https://abc.localtunnel.me", "https://x.serveo.net", "https://abc.lhr.life", "https://abc.localhost.run",
    "https://rnd.a.pinggy.link", "<a href=\"https://abc.trycloudflare.com\">the tool</a>", "(abc.trycloudflare.com).",
    "https://abc.ngrok.pizza", "https://x.serveousercontent.com", "https://abc.lhr.rocks", "https://rnd.a.free.pinggy-free.link",
    "https://k2j3-8080.use.devtunnels.ms", "https://fluffy-space-8080.app.github.dev/login",
    "https://laptop.tail1234.ts.net/mcp", "https://abcd-ip-203-0-113-7.tunnelmole.net", "http://demo.bore.pub:41234",
    "https://demo.loophole.site"])
def test_each_quick_tunnel_host_is_read_however_it_is_written(text):
    assert held_for_the_address(said(text))


@pytest.mark.parametrize("text", [
    "http://localhost:8787/mcp", "localhost:3000", "http://127.0.0.1:8000", "127.0.0.1", "0.0.0.0:8000", "http://[::1]:8080/",
    "http://my-laptop.local:8080", "my-laptop.local:3000", "http://192.168.1.20:8000", "http://10.0.0.5:3000/x",
    "http://172.16.4.2:9000", "https://app.localhost/x"])
def test_an_address_only_this_machine_or_its_network_answers_is_refused(text):
    assert held_for_the_address(said(f"The tool is at {text} for now"))
    assert "Sending needs" in said(f"The tool is at {text} for now", config={**CONFIG, "temporary_addresses": {"local": False}})


@pytest.mark.parametrize("text", [
    "It ran on localhost during my test.", "Copy .env.local and settings.local.json first.", "Version 10.2.3.4 fixes it.",
    "nottrycloudflare.com is someone else's site", "https://trycloudflare.com.example.org/x", "ngrok.io.evil.example",
    "Read the trycloudflare docs before the call.", "The meeting is at 10:30 and 127 people joined.", "user@local.example.com",
    "https://docs.example.com/local/setup", "the 192.168 range is private", "at 172.16.4.2 pm"])
def test_words_that_are_no_address_someone_could_be_sent_to_go_on_to_the_ordinary_approval(text):
    assert "Sending needs the principal's approval" in said(text)


@pytest.mark.parametrize("text", [
    "https://localhost.example.org", "https://10.2.3.4.example.org/x", "https://example.localhost.org", "https://127.0.0.1.example.org",
    "127.0.0.1.example.org", "http://my-laptop.local.example.com:3000", "localhost.example.org:8080", "the key file 127.0.0.1-key.pem",
    "localhost:123456"])
def test_a_host_is_read_whole_so_a_public_name_that_starts_like_a_local_one_goes_on(text):
    assert "Sending needs the principal's approval" in said(text)


@pytest.mark.parametrize("text, address", [
    ("The test UI is localhost:9.", "localhost:9"), ("Use laptop.local:9.", "laptop.local:9"), ("10.0.0.5:7 answers", "10.0.0.5:7"),
    ("192.168.1.20:9", "192.168.1.20:9"), ("localhost:65535", "localhost:65535"), ("It is at http://localhost.", "localhost"),
    ("http://localhost.:8080", "localhost:8080"), ("app.local:7", "app.local:7"), ("http://config.local:7", "config.local:7"),
    ("//laptop.local:3000/x", "laptop.local:3000"), ("db.corp.local:5432", "db.corp.local:5432")])
def test_a_port_of_one_to_five_digits_counts_and_the_refusal_names_the_host_with_it(text, address):
    reason = said(text)
    assert held_for_the_address(reason) and f"({address})" in reason


@pytest.mark.parametrize("text", [
    ".env.local:12", "settings.local.json:3", "config.local:7", "config.local:12", "/etc/rc.local:14", "src/app.local:42",
    "apps/web/.env.local:12", "named.conf.local:31", "Makefile.local:12", "C:\\work\\app.local:7", "settings.local:120",
    "notes.local:17:3"])
def test_a_file_named_like_a_host_with_its_line_number_is_no_address(text):
    assert "Sending needs the principal's approval" in said(f"The key is set at {text} now")


@pytest.mark.parametrize("text, address", [
    ("Open http://[fd12::42]:8080/.", "[fd12::42]:8080"), ("Open http://[fe80::12]:9090/.", "[fe80::12]:9090"),
    ("[fd12::42]:8080", "[fd12::42]:8080"), ("bind it to [fe80::12]", "[fe80::12]"), ("it listens on [::1]", "[::1]"),
    ("http://[fe80::12%25en0]:9090/", "[fe80::12%25en0]:9090"), ("http://[::ffff:10.0.0.1]/", "[::ffff:10.0.0.1]"),
    ("http://[::]:8000", "[::]:8000"), ("Use ssh://10.1.2.3.", "10.1.2.3"), ("Open ftp://192.168.1.2/data.", "192.168.1.2"),
    ("redis://localhost", "localhost"), ("ws://my-laptop.local/x", "my-laptop.local"),
    ("git+ssh://git@192.168.1.5/app.git", "192.168.1.5"), ("jdbc:postgresql://10.1.2.3:5432/app", "10.1.2.3:5432"),
    ("http://169.254.169.254/latest/meta-data", "169.254.169.254"), ("169.254.10.1:8080", "169.254.10.1:8080"),
    ("http://172.31.255.254", "172.31.255.254")])
def test_a_private_address_is_read_however_it_is_written(text, address):
    reason = said(text)
    assert held_for_the_address(reason) and f"({address})" in reason
    assert "Sending needs" in said(text, config={**CONFIG, "temporary_addresses": {"local": False}})


@pytest.mark.parametrize("text, address", [
    ("The database is postgres://app:secret@10.1.2.3:5432/app", "10.1.2.3:5432"),
    ("https://user:secret@abc.trycloudflare.com/mcp", "abc.trycloudflare.com"), ("http://admin:secret@localhost:8000", "localhost:8000")])
def test_what_stands_before_the_host_in_an_address_is_read_past_and_never_shown(text, address):
    reason = said(text)
    assert held_for_the_address(reason) and f"({address})" in reason and "secret" not in reason


def test_a_password_that_holds_an_at_sign_is_read_past_whole():
    reason = said("The database is postgres://app:p@ss@10.1.2.3:5432/app")
    assert held_for_the_address(reason) and "(10.1.2.3:5432)" in reason and "ss@" not in reason


@pytest.mark.parametrize("text", [
    "http://[2001:db8::1]:8080/", "https://[2606:4700:4700::1111]/", "rows[::1] keeps every row", "rows[::2] and [::-1]",
    "ssh://build.example.com", "postgres://app:secret@db.example.com:5432/app", "http://172.32.0.1", "ftp://192.169.1.2/data",
    "https://203.0.113.9:8443", "http://169.255.0.1", "mail user@10.1.2.3 about it", "http://[fd12::42",
    "https://user:secret@docs.example.com/x"])
def test_an_address_outside_those_ranges_goes_on_however_it_is_written(text):
    assert "Sending needs the principal's approval" in said(text)


@pytest.mark.parametrize("text", ["file://localhost/tmp/plan.pdf", "FILE://localhost/tmp/plan%20v2.pdf", "file:///tmp/plan.pdf"])
def test_a_file_url_names_a_file_on_this_disk_and_is_no_address(text):
    """A connector takes a local file as file://localhost/<path>: its host says this disk, and nobody is sent there."""
    assert "Sending needs the principal's approval" in said(f"The plan is at {text} now")


def test_a_host_the_config_adds_counts_and_its_subdomains_too():
    config = {**CONFIG, "temporary_addresses": {"hosts": ["preview.example.dev"]}}
    assert held_for_the_address(said("https://pr-12.preview.example.dev", config=config))
    assert held_for_the_address(said("https://abc.trycloudflare.com", config=config))   # the built-in ones stay
    assert "Sending needs" in said("https://example.dev", config=config)


def test_a_public_name_that_points_at_a_private_address_is_refused_once_the_config_names_its_service():
    text = "https://app.192.168.1.20.nip.io/x"
    assert "Sending needs the principal's approval" in said(text)      # read whole, it is a public name
    reason = said(text, config={**CONFIG, "temporary_addresses": {"hosts": ["nip.io"]}})
    assert held_for_the_address(reason) and "(app.192.168.1.20.nip.io)" in reason


def test_a_draft_a_shell_post_and_typed_words_are_read_the_same(isolated_home):
    assert held_for_the_address(guards.check(DRAFT, {"to": "a@example.com", "subject": "Setup", "body": f"Open {TUNNEL}"}, CONFIG, cwd="/tmp"))
    assert held_for_the_address(guards.check("Bash", {"command": f'gh pr comment 12 -R team/app --body "Try it at {TUNNEL}"'}, CONFIG, cwd="/tmp"))
    session = {"session_id": "S-principal"}
    desktop = {**DESKTOP, "temporary_addresses": {}}
    assert guards.check("mcp__computer-use__request_access", {"apps": ["WhatsApp"], "reason": "test"}, desktop, session=session) is None
    typed = guards.check(TYPE, {"app": WHATSAPP, "text": f"The address is {TUNNEL}"}, desktop, session=session)
    assert held_for_the_address(typed)


def test_no_key_is_no_rule_and_a_setting_that_cannot_be_read_stops_the_send():
    assert "Sending needs" in said(f"Use {TUNNEL}", config={"send_tools": CONFIG["send_tools"]})
    for broken in ("yes", ["trycloudflare.com"], {"hosts": "trycloudflare.com"}, {"hosts": [1]}, {"local": "no"}):
        reason = said("An ordinary note.", config={**CONFIG, "temporary_addresses": broken})
        assert "temporary_addresses" in reason and "Sending needs" not in reason


def test_a_setting_that_is_present_and_null_cannot_be_read_only_an_absent_key_is_no_rule():
    null = {**CONFIG, "temporary_addresses": None}
    reason = said("An ordinary note.", config=null)
    assert "temporary_addresses" in reason and "needs an object" in reason and "Sending needs" not in reason
    held = guards.check("Bash", {"command": STARTS_A_TUNNEL[0]}, null, cwd="/tmp")
    assert held and "temporary tunnel" in held                          # starting one is held under a setting no one can read
    from synthesis import doctor
    check = doctor.check_temporary_addresses(null)
    assert check.status == "fail" and "temporary_addresses" in check.detail and "needs an object" in check.detail


STARTS_A_TUNNEL = [
    "cloudflared tunnel --url http://localhost:8787", "cloudflared tunnel --url=http://localhost:8787 --no-autoupdate",
    "nohup cloudflared tunnel --url http://localhost:8787 > /tmp/t.log 2>&1 &", "env X=1 ngrok http 8080", "ngrok tcp 22",
    "ngrok start web", "npx localtunnel --port 3000", "lt --port 3000 --subdomain shy-cat", "bunx localtunnel -p 3000",
    "ssh -R 80:localhost:8080 serveo.net", "ssh -o StrictHostKeyChecking=no -R 80:localhost:3000 nokey@localhost.run",
    "cd /tmp && cloudflared tunnel --url http://127.0.0.1:9000", "/opt/homebrew/bin/cloudflared tunnel --url http://localhost:1",
    "devtunnel host -p 8080 --allow-anonymous",
    # the ssh destination is a host: the service's name in any case, a subdomain of it, given as a URL, before its options
    "ssh -R 80:localhost:8080 Serveo.NET", "ssh -p 443 -R0:localhost:8000 qr@a.pinggy.io", "ssh serveo.net -R 80:localhost:8080",
    "ssh -R 80:localhost:3000 ssh://nokey@localhost.run:22",
    # the program named through a variable the command sets
    "tunnel_program=cloudflared; $tunnel_program tunnel --url http://localhost:7777", 'export T=ngrok && "$T" http 8080',
    'IMAGE=cloudflare/cloudflared; docker run --rm "$IMAGE" tunnel --url http://host.docker.internal:7777',
    # a container run of a tunnel image, with a tag, from another registry, or with the program after the image
    "docker run --rm cloudflare/cloudflared tunnel --url http://host.docker.internal:7777",
    "docker run -it --net=host -e TZ=UTC -p 4040:4040 ngrok/ngrok:latest http 8080",
    "podman run --rm docker.io/cloudflare/cloudflared:2024.6.1 tunnel --no-autoupdate --url http://host.containers.internal:3000",
    "docker run --rm --net=host pinggy/pinggy -p 443 -R0:localhost:8000 a.pinggy.io", "docker run --rm tools/ngrok ngrok http web:80",
    # ngrok's subcommand after its own options and their values
    "ngrok --log=stdout http 7777", "ngrok --config /tmp/ngrok.yml start web", "ngrok --log stdout --region eu tcp 22",
    # a package runner with options and a versioned package
    "npx --yes localtunnel@2.0.2 --port 7777", "pnpm dlx localtunnel@2.0.2 --port 7777", "npm exec --yes localtunnel@2 -- --port 3000",
    "yarn dlx localtunnel@2.0.2 --port 7777", "bunx --bun localtunnel@latest -p 3000", "bun x localtunnel@2.0.2 --port 3000",
    "npx --yes cloudflared@latest tunnel --url http://localhost:3000", "pnpm dlx ngrok@5 http 3000",
    # -R joined to other flags, and with its value joined on
    "ssh -NR 80:localhost:7777 nokey@localhost.run", "ssh -fNTR 80:localhost:3000 serveo.net", "ssh -NR80:localhost:3000 serveo.net"]
NO_TUNNEL = [
    "cloudflared tunnel run production", "cloudflared tunnel list", "cloudflared --version", "ngrok config check", "ngrok version",
    "echo cloudflared tunnel --url http://localhost:1", "grep -rn 'ngrok http' docs/", "brew install cloudflared",
    "ssh -R 9000:localhost:9000 build.example.com", "lt --help", "devtunnel list",
    # a reverse forward to someone else's host: one that ends with a service's letters, and one reached with a jump
    # host, a key file or a remote command that carries a service's name
    "ssh -R 9000:localhost:9000 notserveo.net", "ssh -R 9000:localhost:9000 team-pinggy.io",
    "ssh -R 9000:localhost:9000 deploy@xlocalhost.run", "ssh -R 80:localhost:8080 -J jump@serveo.net build.example.com",
    "ssh -i ~/.ssh/serveo.net -R 9000:localhost:9000 build.example.com",
    "ssh -R 9000:localhost:9000 build.example.com curl https://serveo.net",
    # a variable that names the program and starts nothing, or names another program
    'tunnel_program=cloudflared; echo "$tunnel_program"', "tunnel_program=cloudflared; $tunnel_program tunnel list",
    "T=cloudflared; brew install $T", "T=ls; $T tunnel --url http://localhost:1",
    # a container that runs a named tunnel, a lookup, another image, or only carries a service's name
    "docker run --rm cloudflare/cloudflared tunnel --no-autoupdate run production", "docker run --rm cloudflare/cloudflared --version",
    "docker pull cloudflare/cloudflared:latest", "docker run -d --name cloudflared nginx", "docker run --rm ngrok/ngrok config check",
    "docker run -v ngrok:/data alpine ls /data", "docker logs ngrok", "docker run -p 3000:3000 example/app --port 3000",
    # ngrok's other subcommands after its options
    "ngrok --log=stdout config check", "ngrok help http", "ngrok --config /tmp/ngrok.yml version", "ngrok --version",
    # another package with a version and a port, and a tunnel package that is installed or looked up
    "npx --yes cowsay@1.6.0 --port 7777", "npm install localtunnel@2.0.2", "npm view localtunnel@2.0.2 version",
    "yarn add --dev localtunnel", "npx --yes localtunnel@2.0.2 --help", "pnpm dlx serve@14 --port 3000",
    # a cluster with no -R, the letter in another option's value, a forward the other way, -R in the remote command
    "ssh -NR 9000:localhost:9000 build.example.com", "ssh -NT -L 8080:localhost:80 nokey@localhost.run",
    "ssh -oRequestTTY=no -N nokey@localhost.run", "ssh nokey@localhost.run ls -R /tmp"]


@pytest.mark.parametrize("command", STARTS_A_TUNNEL)
def test_starting_a_quick_tunnel_waits_for_a_code_of_its_own(command, principal):
    reason = guards.check("Bash", {"command": command}, CONFIG, cwd="/tmp")
    assert reason and "temporary tunnel" in reason and "never given to anyone" in reason and "own test" in reason
    principal(reason)
    assert guards.check("Bash", {"command": command}, CONFIG, cwd="/tmp") is None
    assert "temporary tunnel" in guards.check("Bash", {"command": command}, CONFIG, cwd="/tmp")     # one approval, one start


@pytest.mark.parametrize("command", NO_TUNNEL)
def test_a_named_tunnel_a_lookup_and_words_about_a_tunnel_start_nothing(command):
    assert guards.check("Bash", {"command": command}, CONFIG, cwd="/tmp") is None


def test_without_the_key_a_tunnel_starts_as_before():
    assert guards.check("Bash", {"command": STARTS_A_TUNNEL[0]}, {}, cwd="/tmp") is None


def test_the_doctor_proves_the_rule_is_wired():
    from synthesis import doctor
    ok = doctor.check_temporary_addresses(CONFIG)
    assert ok.status == "ok" and "refused" in ok.detail
    assert doctor.check_temporary_addresses({**CONFIG, "temporary_addresses": {"hosts": "x"}}).status == "fail"


def test_the_guard_and_the_knowledge_base_connector_name_the_same_tunnel_services():
    """Two lists: one in the core, one in a connector that is deployed alone and cannot import it. A service known
    to one and not the other would be refused when the connector starts and passed in a message, or the reverse."""
    import ast
    from pathlib import Path
    source = Path(guards.__file__).resolve().parents[1] / "skills/synthesis-kb-distribution/scripts/connector/kb_connector/config.py"
    hosts = next(ast.literal_eval(node.value) for node in ast.walk(ast.parse(source.read_text(encoding="utf-8")))
                 if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "TEMPORARY_HOSTS")
    assert {name.lstrip(".") for name in guards.TUNNELS} == set(hosts) - {"localhost", "local"}
