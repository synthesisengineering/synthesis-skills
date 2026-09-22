# Promoted from the private control plane (private agent-control, PRO-2, 2026-09-21); behavior identical.
"""Bounded shell execution classification, without executing or expanding input.

This identifies commands for the approval guard, not repository targets or
approval. The existing stricter publication parser still enforces those. Shell
substitutions and shell-interpreter input are executable; quoted arguments and
literal heredocs to other programs are data. Arbitrary interpreter/script
semantics are outside this shell-command boundary.
"""
from __future__ import annotations

from pathlib import Path
import re
import shlex
from typing import NamedTuple


SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
STDIN_PATHS = {"/dev/stdin", "/dev/fd/0", "/proc/self/fd/0"}
# Git aliases cannot replace built-in commands. Unknown commands can resolve
# to persisted aliases or external git-* programs, whose effects are unknown.
GIT_BUILTINS = set("""
add am annotate apply archive bisect blame branch bugreport bundle cat-file
check-attr check-ignore check-mailmap check-ref-format checkout checkout-index
cherry cherry-pick clean clone column commit commit-graph commit-tree config count-objects
credential credential-cache credential-store describe diagnose diff diff-files
diff-index diff-tree difftool fast-export fast-import fetch fetch-pack fmt-merge-msg
for-each-ref for-each-repo format-patch fsck fsmonitor--daemon gc get-tar-commit-id
grep hash-object help hook index-pack init init-db interpret-trailers log ls-files
ls-remote ls-tree mailinfo mailsplit maintenance merge merge-base merge-file
merge-index merge-ours merge-recursive merge-subtree merge-tree mktag mktree multi-pack-index mv
name-rev notes pack-objects pack-redundant pack-refs patch-id prune prune-packed
pull push range-diff read-tree rebase receive-pack reflog refs remote repack replace
rerere reset restore rev-list rev-parse revert rm send-pack shortlog show show-branch
show-index show-ref sparse-checkout stage stash status stripspace submodule
submodule--helper switch symbolic-ref tag unpack-file unpack-objects update-index
update-ref update-server-info upload-archive upload-pack var verify-commit
verify-pack verify-tag version whatchanged worktree write-tree
""".split())


def artifact_consumer_position(words: list[str]) -> int | None:
    """Return an executable artifact consumer, never a data argument."""
    if not words:
        return None
    position = 0
    if Path(words[0]).name in {"node", "python", "python3", "bun", "deno"}:
        position = 1
        while position < len(words) and words[position].startswith("-"):
            position += 1
    if (position + 1 < len(words) and words[position].endswith("release-gate.mjs")
            and words[position + 1].startswith("deploy")):
        return position
    return None


def wrangler_operation(args: list[str]) -> str | None:
    """Classify actual Wrangler command position, including Pages aliases."""
    index, rest = 0, []
    while index < len(args) and len(rest) < 3:
        flag = args[index]
        index += 1
        if flag == "--":
            rest.extend(args[index:])
            break
        if flag in {"--cwd", "--config", "-c", "--env", "-e", "--env-file", "--log-level"}:
            index += 1
        elif not flag.startswith("-"):
            rest.append(flag)
    if rest[:1] == ["deploy"] or rest[:2] in (["versions", "deploy"], ["triggers", "deploy"]):
        return "worker"
    if rest[:2] in (["pages", "deploy"], ["pages", "publish"]) or rest[:3] == ["pages", "deployment", "create"]:
        return "pages"
    if rest[:2] == ["d1", "execute"] and any(a.split("=")[0] == "--remote" for a in args):
        return "database"
    return None


class Inspection(NamedTuple):
    commands: list[list[str]]
    separators: list[str]
    publication: bool
    restricted: bool
    publication_indices: list[int]
    write_indices: list[int]


class ShellSyntax(NamedTuple):
    commands: list[list[str]]
    nested: list[str]
    separators: list[str]
    grouped: bool
    write_indices: list[int]
    dynamic: bool
    redirections: list[tuple[int, str, str]]
    heredocs: list[tuple[int, str]]
    nested_commands: list[tuple[int, str]]
    dynamic_indices: list[int]


def _substitution_end(text: str, start: int) -> int:
    depth, quote, i = 1, None, start
    while i < len(text):
        c = text[i]
        if c == "\\" and quote != "'":
            i += 2
            continue
        if quote:
            if c == quote:
                quote = None
        elif c in "'\"`":
            quote = c
        elif text.startswith("case", i) and (i == start or text[i - 1].isspace()) and text[i + 4:i + 5].isspace():
            # A case-pattern ')' is not a substitution boundary. Refuse the
            # grammar we cannot balance rather than dropping executable text.
            raise ValueError("case syntax inside command substitution is not supported")
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if not depth:
                return i
        i += 1
    raise ValueError("unterminated shell substitution")


def _word(text: str, start: int, nested: list[str], dynamic: list[bool]) -> tuple[str, int, bool]:
    value, i, quoted = [], start, False
    quote = None
    while i < len(text):
        c = text[i]
        if quote is None and (c.isspace() or c in ";&|()<>"):
            break
        if c == "\\" and quote != "'":
            if i + 1 == len(text):
                raise ValueError("unfinished escape")
            following = text[i + 1]
            if quote == '"' and following not in '\\"$`\n':
                value.append(c)
                i += 1
                continue
            if following != "\n":
                value.append(following)
            quoted = True
            i += 2
            continue
        if quote is None and c in "'\"":
            quote, quoted = c, True
            i += 1
            continue
        if quote and c == quote:
            quote = None
            i += 1
            continue
        if quote != "'" and c in "$`":
            dynamic.append(True)
        if quote != "'" and text.startswith("$(", i):
            end = _substitution_end(text, i + 2)
            nested.append(text[i + 2:end])
            value.append(text[i:end + 1])
            i = end + 1
            continue
        if quote != "'" and c == "`":
            end = i + 1
            while end < len(text):
                if text[end] == "\\":
                    end += 2
                elif text[end] == "`":
                    break
                else:
                    end += 1
            if end >= len(text):
                raise ValueError("unterminated backtick substitution")
            nested.append(text[i + 1:end])
            value.append(text[i:end + 1])
            i = end + 1
            continue
        value.append(c)
        i += 1
    if quote:
        raise ValueError("unterminated shell quote")
    return "".join(value), i, quoted


def unwrap_argv(words: list[str]) -> list[str]:
    args = list(words)
    while args and (ASSIGNMENT.match(args[0]) or args[0] in {"if", "then", "elif", "do", "!", "{"}):
        args.pop(0)
    while args and Path(args[0]).name in {"env", "command", "builtin", "nohup", "sudo", "time", "nice", "timeout", "stdbuf", "exec", "xargs"}:
        wrapper = Path(args.pop(0)).name
        value_flags = {
            "env": {"-u", "--unset", "-C", "--chdir", "--argv0", "-a", "-P"},
            "sudo": {"-u", "--user", "-g", "--group", "-h", "--host", "-D", "--chdir", "-R", "--chroot", "-p", "--prompt", "-C", "--close-from", "-T", "--command-timeout", "-r", "--role", "-t", "--type", "-U", "--other-user"},
            "nice": {"-n", "--adjustment"}, "timeout": {"-s", "--signal", "-k", "--kill-after"},
            "stdbuf": {"-i", "-o", "-e", "--input", "--output", "--error"}, "exec": {"-a"},
            "time": {"-o", "--output", "-f", "--format"},
            "xargs": {"-n", "--max-args", "-P", "--max-procs", "-I", "--replace", "-L", "--max-lines", "-s", "--max-chars", "-E", "--eof", "-d", "--delimiter"},
        }.get(wrapper, set())
        while args and (args[0].startswith("-") or ASSIGNMENT.match(args[0])):
            flag = args.pop(0)
            if flag == "--":
                break
            if wrapper == "command" and flag in {"-v", "-V"}:
                return []  # command lookup does not execute its arguments
            if wrapper == "env" and (flag in {"-S", "--split-string"} or flag.startswith(("--split-string=", "-S"))):
                value = flag.split("=", 1)[1] if flag.startswith("--split-string=") else flag[2:] if flag.startswith("-S") and len(flag) > 2 else args.pop(0) if args else ""
                if not value or any(c in value for c in "$`"):
                    raise ValueError("unresolved environment split-string")
                args[:0] = shlex.split(value)
                break
            if flag in value_flags:
                if not args:
                    raise ValueError("missing command wrapper option")
                args.pop(0)
        while args and ASSIGNMENT.match(args[0]):
            args.pop(0)
        if wrapper == "timeout":
            if not args:
                raise ValueError("timeout duration is absent")
            args.pop(0)
    return args


def parse_shell(text: str) -> ShellSyntax:
    """Parse executable shell structure without evaluating argument or input data."""
    commands, nested, words, pending, separators, here_strings = [], [], [], [], [], []
    supplied_input: list[list[str]] = []
    writes: list[list[str]] = []
    dynamic: list[bool] = []
    dynamic_owners: list[list[str]] = []
    redirections: list[tuple[list[str], str, str]] = []
    heredocs: list[tuple[list[str], str]] = []
    nested_commands: list[tuple[list[str], str]] = []
    def has_command(owner: list[str]) -> bool:
        return bool(owner) or any(owner is command for command, _, _ in redirections)
    grouped = False
    last_end, last_quoted = -1, False
    i = 0
    while i < len(text):
        c = text[i]
        if c in " \t\r":
            i += 1
            continue
        if c == "#":
            end = text.find("\n", i)
            i = len(text) if end < 0 else end
            continue
        if c == "\n":
            if has_command(words):
                commands.append(words)
                separators.append("\n")
                words = []
            i += 1
            for delimiter, expand, strip_tabs, owner in pending:
                body = []
                while i < len(text):
                    end = text.find("\n", i)
                    end = len(text) if end < 0 else end
                    line = text[i:end]
                    i = min(end + 1, len(text))
                    if (line.lstrip("\t") if strip_tabs else line) == delimiter:
                        break
                    body.append(line)
                else:
                    raise ValueError("unterminated heredoc")
                data = "\n".join(body)
                heredocs.append((owner, data))
                argv = unwrap_argv(owner)
                if argv and _reads_shell_input(argv):
                    nested.append(data)
                    nested_commands.append((owner, data))
                    supplied_input.append(owner)
                elif expand:
                    # Here-documents expand substitutions even inside quote
                    # characters in their body. Only the delimiter controls it.
                    j = 0
                    while j < len(data):
                        if data[j] == "\\":
                            j += 2
                        elif data.startswith("$(", j):
                            dynamic_owners.append(owner)
                            end = _substitution_end(data, j + 2)
                            nested.append(data[j + 2:end])
                            nested_commands.append((owner, data[j + 2:end]))
                            j = end + 1
                        elif data[j] == "`":
                            dynamic_owners.append(owner)
                            end = data.find("`", j + 1)
                            if end < 0:
                                raise ValueError("unterminated heredoc substitution")
                            nested.append(data[j + 1:end])
                            nested_commands.append((owner, data[j + 1:end]))
                            j = end + 1
                        elif data[j] == "$":
                            dynamic.append(True)
                            dynamic_owners.append(owner)
                            j += 1
                        else:
                            j += 1
            pending = []
            continue
        if (c in ";&|()" and not text.startswith("&>", i)) or (c in "{}" and (i + 1 == len(text) or text[i + 1].isspace())):
            operator = text[i:i + 2] if text[i:i + 2] in {"&&", "||", "|&", ";;"} else c
            grouped = grouped or c in "(){}"
            if has_command(words):
                commands.append(words)
                separators.append(operator)
                words = []
            i += len(operator)
            continue
        if c in "<>" or text.startswith("&>", i):
            combined_output = c == "&"
            if combined_output:
                i += 1
                c = ">"
            if c == ">":
                writes.append(words)
            operator_start = i
            operator = c
            i += 1
            while i < len(text) and text[i] == c and len(operator) < 3:
                operator += c
                i += 1
            strip_tabs = operator == "<<" and text[i:i + 1] == "-"
            if strip_tabs:
                i += 1
            while i < len(text) and text[i] in " \t":
                i += 1
            if text[i:i + 1] == "&":
                operator += "&"
                i += 1
            if words and words[-1].isdigit() and last_end == operator_start and not last_quoted:
                words.pop()
            nested_start = len(nested)
            dynamic_start = len(dynamic)
            operand, i, quoted = _word(text, i, nested, dynamic)
            if len(dynamic) > dynamic_start:
                dynamic_owners.append(words)
            nested_commands.extend((words, script) for script in nested[nested_start:])
            if not operand:
                raise ValueError("missing redirection operand")
            redirections.append((words, ("&" if combined_output else "") + operator, operand))
            if operator == "<<":
                pending.append((operand, not quoted, strip_tabs, words))
            elif operator == "<<<":
                here_strings.append((operand, words))
            continue
        nested_start = len(nested)
        dynamic_start = len(dynamic)
        word, end, quoted = _word(text, i, nested, dynamic)
        if len(dynamic) > dynamic_start:
            dynamic_owners.append(words)
        nested_commands.extend((words, script) for script in nested[nested_start:])
        if end == i:
            raise ValueError("unrecognized shell token")
        words.append(word)
        last_end, last_quoted = end, quoted
        i = end
    if pending:
        raise ValueError("heredoc body is absent")
    if has_command(words):
        commands.append(words)
        separators.append("")
    for operand, owner in here_strings:
        argv = unwrap_argv(owner)
        if argv and _reads_shell_input(argv):
            nested.append(operand)
            nested_commands.append((owner, operand))
            supplied_input.append(owner)
    for index, words in enumerate(commands):
        argv = unwrap_argv(words)
        if argv:
            executable = Path(argv[0]).name
            script = " ".join(argv[1:]) if executable == "eval" else _shell_program(argv[1:]) if executable in SHELLS else None
            if script is not None:
                nested.append(script)
                nested_commands.append((words, script))
        if argv and _reads_shell_input(argv) and index and separators[index - 1] in {"|", "|&"}:
            # The preceding process can compute arbitrary shell source. Its
            # quoted argv/heredoc is no longer inert data at this boundary.
            if _shell_program(argv[1:]) is None and not any(words is owner for owner in supplied_input):
                raise ValueError("piped shell input is executable and cannot be resolved without execution")
    indices = {id(words): i for i, words in enumerate(commands)}
    return ShellSyntax(
        commands, nested, separators, grouped,
        [indices[id(owner)] for owner in writes if id(owner) in indices], bool(dynamic),
        [(indices.get(id(owner), -1), operator, operand) for owner, operator, operand in redirections],
        [(indices.get(id(owner), -1), body) for owner, body in heredocs],
        [(indices.get(id(owner), -1), script) for owner, script in nested_commands],
        sorted({indices[id(owner)] for owner in dynamic_owners if id(owner) in indices}),
    )


def _shell_program(args: list[str]) -> str | None:
    index = 0
    while index < len(args):
        arg = args[index]
        if arg.startswith("--command="):
            return arg.split("=", 1)[1]
        if arg == "--command" or (arg.startswith("-") and "c" in arg[1:] and not arg.startswith("--")):
            if index + 1 >= len(args):
                raise ValueError("shell command argument is absent")
            return args[index + 1]
        if arg == "--":
            break
        if not arg.startswith(("-", "+")):
            break  # later options are arguments to a script file
        index += 2 if arg in {"-o", "+o", "-O", "+O", "--rcfile", "--init-file"} else 1
    return None


def _reads_shell_input(argv: list[str]) -> bool:
    executable, args = ("." if argv[0] == "." else Path(argv[0]).name), argv[1:]
    if executable in {".", "source"}:
        if args[:1] == ["--"]:
            args = args[1:]
        return bool(args and args[0] in STDIN_PATHS)
    if executable not in SHELLS or _shell_program(args) is not None:
        return False
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "-" or (arg.startswith("-") and not arg.startswith("--") and "s" in arg[1:]):
            return True
        if arg == "--":
            return index + 1 == len(args) or args[index + 1] in STDIN_PATHS
        if not arg.startswith(("-", "+")):
            return arg in STDIN_PATHS
        index += 2 if arg in {"-o", "+o", "-O", "+O", "--rcfile", "--init-file"} else 1
    return True


def inspect_command(command: str, *, depth: int = 0) -> Inspection:
    """Classify execution; restricted publication must fail closed, not vanish."""
    if depth > 16:
        raise ValueError("shell nesting exceeds inspection limit")
    syntax = parse_shell(command)
    commands, nested, separators, grouped, write_indices = syntax[:5]
    publication, restricted = False, False
    publication_indices: list[int] = []
    for command_index, words in enumerate(commands):
        args = unwrap_argv(words)
        if not args:
            continue
        executable, rest = Path(args[0]).name, args[1:]
        if any(c in executable for c in "$`"):
            raise ValueError("unresolved executable expansion")
        hit = False
        if executable == "git":
            i = 0
            while i < len(rest) and rest[i].startswith("-"):
                flag = rest[i]
                i += 1
                if flag == "--":
                    break
                if flag in {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env", "--super-prefix"}:
                    i += 1
            if i < len(rest) and rest[i] == "push":
                hit = True
            elif i < len(rest) and rest[i] == "for-each-repo":
                tail = rest[i + 1:]
                while tail and tail[0].startswith("-"):
                    flag = tail.pop(0)
                    if flag == "--":
                        break
                    if flag == "--config":
                        if not tail:
                            raise ValueError("bulk Git configuration is absent")
                        tail.pop(0)
                    elif flag != "--keep-going" and not flag.startswith("--config="):
                        raise ValueError("unresolved bulk Git option")
                if tail:
                    nested.append(shlex.join(["git", *tail]))
            elif i < len(rest) and rest[i] in {"submodule", "submodule--helper"}:
                tail = rest[i + 1:]
                while tail and tail[0] in {"--quiet", "-q", "--"}:
                    tail.pop(0)
                if tail[:1] == ["foreach"]:
                    tail = tail[1:]
                    while tail and tail[0] in {"--quiet", "-q", "--recursive", "--"}:
                        tail.pop(0)
                    nested.append(" ".join(tail))
            elif i < len(rest) and any(c in rest[i] for c in "$`"):
                raise ValueError("unresolved Git subcommand expansion")
            elif i < len(rest) and rest[i] not in GIT_BUILTINS:
                raise ValueError("unresolved Git alias or external subcommand")
        else:
            if executable in {"npm", "pnpm", "yarn"} and rest and rest[0] in {"exec", "dlx"}:
                rest = rest[1:]
                executable = "npx"
            if executable in {"npx", "pnpx", "bunx"}:
                while rest and rest[0].startswith("-"):
                    option = rest.pop(0)
                    if option == "--":
                        break
                    if option.startswith("--call="):
                        nested.append(option.split("=", 1)[1])
                        break
                    if option in {"-c", "--call"}:
                        if not rest:
                            raise ValueError("package-runner command is absent")
                        nested.append(rest.pop(0))
                        break
                    if option in {"-p", "--package", "--cache", "--userconfig", "--registry"}:
                        if not rest:
                            raise ValueError("package-runner option value is absent")
                        rest.pop(0)
                executable, rest = (Path(rest[0]).name, rest[1:]) if rest else ("", [])
            if executable in {"node", "python", "python3", "bun", "deno"} and rest:
                while rest and rest[0].startswith("-"):
                    rest.pop(0)
                executable, rest = (Path(rest[0]).name, rest[1:]) if rest else ("", [])
            if executable in {"wrangler", "wrangler.js"}:
                if wrangler_operation(rest):
                    hit = True
            if executable.endswith("release-gate.mjs") and rest and rest[0].startswith("deploy"):
                hit = True
        if hit:
            publication = True
            publication_indices.append(command_index)
            # Wrappers affect identity, cwd or executable selection. They are
            # detected here and refused unless the strict consumer owns them.
            restricted = restricted or args != words or grouped
            if executable in {"wrangler", "wrangler.js"}:
                supported = Path(words[0]).name in {"wrangler", "wrangler.js"} or (
                    len(words) > 1 and Path(words[0]).name in {"npx", "node"} and Path(words[1]).name in {"wrangler", "wrangler.js"})
                restricted = restricted or not supported
    for script in nested:
        inner = inspect_command(script, depth=depth + 1)
        if inner.publication:
            publication, restricted = True, True
    # Argument evaluation can change a remote, HEAD, directory lookup, or
    # shell state before a later operation. Quoted literal expansion text is
    # not marked dynamic by the lexer and remains data.
    restricted = restricted or publication and (syntax.dynamic or bool(nested))
    return Inspection(commands, separators, publication, restricted, publication_indices, write_indices)


def may_publish(command: str, *, depth: int = 0) -> bool:
    return inspect_command(command, depth=depth).publication
