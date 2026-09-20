#!/usr/bin/env python3
"""The one smart entry: ``synthesis onboard``.

New user or existing, new Mac or fleet join, install or upgrade — the
scenario must not matter. This dispatcher detects what the Mac holds,
recommends the best path, asks its questions through the controlling
terminal (pipe-safe), and chains the existing engines (setup, update,
fleet join, workspace, activate, doctor, repair). Explicit commands
remain for automation and the manual path; humans run this.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import fleet_join


class OnboardError(ValueError):
    """An onboard that cannot proceed, with the remedy in the message."""


HEADLESS_REMEDY = (
    "needs a terminal; for automation run the explicit commands instead: "
    "synthesis setup (add --answers to skip questions), synthesis update, "
    "synthesis fleet join --kb <url-or-path>"
)


def read_setup(home: Path) -> dict | None:
    """Desired state, or None when setup never converged here."""
    try:
        from system_contract import SystemState

        return SystemState(home=Path(home).expanduser()).read_desired()
    except Exception:
        return None


def _fleet_scripts(release_root: Path) -> None:
    scripts = (
        Path(release_root)
        / "skills"
        / "synthesis-project-management"
        / "scripts"
    )
    if scripts.is_dir() and str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))


def read_fleet(home: Path, release_root: Path) -> dict:
    """Fleet enrollment found under this home (empty when unenrolled)."""
    found: dict = {"machine_id": None, "label": None, "role": None}
    try:
        _fleet_scripts(release_root)
        import fleet_identity

        directory = fleet_identity.fleet_dir_for_board(
            Path(home).expanduser()
            / ".synthesis"
            / "coordination"
            / "active-sessions.md"
        )
    except Exception:
        return found
    try:
        machine_id = fleet_identity.read_machine_id(directory)
    except fleet_identity.FleetIdentityError:
        return found
    if not machine_id:
        return found
    found["machine_id"] = machine_id
    try:
        entry = fleet_identity.read_registry(directory)["machines"].get(
            machine_id, {}
        )
    except fleet_identity.FleetIdentityError:
        return found
    if isinstance(entry, dict):
        found["label"] = entry.get("label")
        found["role"] = entry.get("role")
    return found


def _run_cli(*argv: str) -> int:
    import synthesis_cli

    return synthesis_cli.main(list(argv))


def default_fleet_join_args() -> SimpleNamespace:
    return SimpleNamespace(
        kb=None, label=None, role=None, workspace=None,
        json=False, verbose=False,
    )


class Onboarder:
    """Detect, recommend, ask, and chain the existing engines."""

    MENU_FLEET = "Join or verify the personal fleet"
    MENU_UPDATE = "Update to the latest version"
    MENU_WORKSPACE = "Add a workspace"
    MENU_COMPONENTS = "Change installed components"
    MENU_VERIFY = "Verify and repair this Mac"
    MENU_DONE = "Done"

    def __init__(
        self,
        *,
        release_root: Path,
        home: Path,
        announce=None,
        can_prompt: bool = True,
        read_setup_state=None,
        read_fleet_state=None,
        run_setup=None,
        run_fleet_join=None,
        run_update=None,
        run_workspace_ensure=None,
        run_activate=None,
        run_doctor=None,
        run_repair=None,
    ) -> None:
        self.release_root = Path(release_root)
        self.home = Path(home).expanduser()
        self.announce = announce or (
            lambda line: print(line, flush=True)
        )
        self.can_prompt = can_prompt
        self.read_setup_state = read_setup_state or (
            lambda home_dir: read_setup(home_dir)
        )
        self.read_fleet_state = read_fleet_state or (
            lambda home_dir: read_fleet(home_dir, self.release_root)
        )
        self.run_setup = run_setup or (lambda: _run_cli("setup"))
        self.run_fleet_join = run_fleet_join or (
            lambda: fleet_join.join(
                default_fleet_join_args(),
                release_root=self.release_root, home=self.home,
            )
        )
        self.run_update = run_update or (lambda: _run_cli("update"))
        self.run_workspace_ensure = run_workspace_ensure or (
            lambda name, remote: _run_cli(
                "workspace", "ensure", "--name", name,
                *([ "--remote", remote] if remote else []),
            )
        )
        self.run_activate = run_activate or (
            lambda profile: _run_cli("activate", "--profile", profile)
        )
        self.run_doctor = run_doctor or (lambda: _run_cli("doctor"))
        self.run_repair = run_repair or (lambda: _run_cli("repair"))

    def survey(self) -> dict:
        """What this Mac holds: setup desired state plus fleet identity."""
        return {
            "setup": self.read_setup_state(self.home),
            "fleet": self.read_fleet_state(self.home),
        }

    def menu(self, fleet: dict) -> tuple[list[str], int]:
        """(options, 1-based recommended default) for an installed Mac."""
        options = [
            self.MENU_FLEET,
            self.MENU_UPDATE,
            self.MENU_WORKSPACE,
            self.MENU_COMPONENTS,
            self.MENU_VERIFY,
            self.MENU_DONE,
        ]
        if fleet.get("machine_id") is None:
            return options, 1
        return options, 5

    def run_fresh(self) -> int:
        """Install, then offer the fleet; the bare-Mac path."""
        self.announce("nothing installed yet — installing now "
                      "(answer the setup questions first)")
        fleet_join.ensure_setup(
            self.home, setup_check=lambda home_dir: False,
            setup_runner=self.run_setup, announce=self.announce,
            can_prompt=self.can_prompt,
        )
        if fleet_join.prompt_confirm(
            "Join a personal fleet to sync this Mac with your other "
            "Macs?",
            default=False, can_prompt=self.can_prompt,
            hint="rerun this command to join later",
        ):
            return self.run_fleet_join()
        self.announce("done — rerun the same command anytime to join a "
                      "fleet or manage this Mac")
        return 0

    def run_menu(self, fleet: dict) -> int | None:
        """One menu round; None means loop again, an int exits."""
        options, default = self.menu(fleet)
        choice = fleet_join.prompt_choice(
            "What should this Mac do?", options,
            "rerun non-interactively is not supported; use the explicit "
            "commands",
            can_prompt=self.can_prompt, default=default,
        )
        if choice == self.MENU_DONE:
            return 0
        if choice == self.MENU_FLEET:
            code = self.run_fleet_join()
        elif choice == self.MENU_UPDATE:
            code = self.run_update()
        elif choice == self.MENU_WORKSPACE:
            name = fleet_join.prompt_text(
                "Workspace name", "synthesis workspace ensure --name NAME",
                can_prompt=self.can_prompt,
            )
            remote = fleet_join.prompt_text(
                "Workspace remote URL (empty for none)",
                "synthesis workspace ensure --name NAME --remote URL",
                can_prompt=self.can_prompt, default="",
            ) or None
            code = self.run_workspace_ensure(name, remote)
        elif choice == self.MENU_COMPONENTS:
            profile = fleet_join.prompt_choice(
                "Which components should this Mac carry?",
                ["full — everything", "skills-only — just the skills"],
                "synthesis activate --profile full|skills-only",
                can_prompt=self.can_prompt, default=1,
            ).split(" — ", 1)[0]
            code = self.run_activate(profile)
        else:
            code = self.run_doctor()
            if code == 0:
                self.announce("verified — every plane is green")
                return None
            if fleet_join.prompt_confirm(
                "Issues found — run repair?", default=True,
                can_prompt=self.can_prompt,
                hint="run synthesis repair directly",
            ):
                code = self.run_repair()
        self.announce(
            f"{choice}: {'done' if code == 0 else f'exit {code}'}"
        )
        return None

    def run(self) -> int:
        """One entry for every scenario; the interview needs a terminal."""
        if not self.can_prompt:
            raise OnboardError(
                f"synthesis onboard {HEADLESS_REMEDY}"
            )
        state = self.survey()
        if state["setup"] is None:
            return self.run_fresh()
        profile = state["setup"].get("profile", "unknown")
        fleet = state["fleet"]
        if fleet.get("machine_id") is None:
            self.announce(
                f"this Mac is set up ({profile}) but not in a fleet — "
                "joining is recommended"
            )
        else:
            self.announce(
                f"this Mac is set up ({profile}) and enrolled as "
                f"{fleet.get('label')} ({fleet.get('role')})"
            )
        while True:
            state = self.survey()
            result = self.run_menu(state["fleet"])
            if result is not None:
                return result


def onboard(
    args,
    *,
    release_root: Path,
    home: Path | None = None,
    **overrides,
) -> int:
    """Run ``synthesis onboard``; return the process exit code."""
    home = Path(home).expanduser() if home is not None else Path.home()
    as_json = bool(getattr(args, "json", False))
    can_prompt = fleet_join.terminal_available() and not as_json
    try:
        return Onboarder(
            release_root=release_root, home=home, can_prompt=can_prompt,
            **overrides,
        ).run()
    except KeyboardInterrupt:
        print(
            "INTERRUPTED onboard: rerun the same command to resume; "
            "finished steps are kept",
            file=sys.stderr,
        )
        return 130
