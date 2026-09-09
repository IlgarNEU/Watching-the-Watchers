#!/usr/bin/env python3
"""
Sony Bravia ACR Experiment — Rich Terminal UI
==============================================
Drop-in replacement for SonyAutomationManager.py.

Usage:
    python TUISonyExperiment.py
"""

import ast
import asyncio
import logging
import time
from collections import deque
from datetime import datetime, timedelta

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from SonyAutomation import *

# ─── Scenario metadata ───────────────────────────────────────────────────

SCENARIO_ICONS = {
    "IDLE":         "💤",
    "FAST":         "⚡",
    "HDMI":         "🔌",
    "ANTENNA 14.1": "📡",
    "ANTENNA":      "📡",
    "NETFLIX":      "🎬",
    "YOUTUBE":      "▶ ",
    "TUBI":         "📺",
}

SCENARIO_COLORS = {
    "IDLE":         "bright_black",
    "FAST":         "bright_yellow",
    "HDMI":         "green",
    "ANTENNA 14.1": "bright_cyan",
    "ANTENNA":      "cyan",
    "NETFLIX":      "red",
    "YOUTUBE":      "bright_red",
    "TUBI":         "magenta",
}

PHASE_LABELS = {
    "idle":        "[dim]Idle[/]",
    "boot":        "[yellow]⏻  Booting[/]",
    "home":        "[blue]🏠 Going Home[/]",
    "launch":      "[green]🚀 Launching[/]",
    "watch":       "[bright_green]👁  Watching[/]",
    "exit":        "[blue]🚪 Exiting[/]",
    "acr_toggle":  "[bright_magenta]🔒 Toggling ACR[/]",
    "power_off":   "[red]⏻  Powering Off[/]",
}


# ─── Log capture ──────────────────────────────────────────────────────────

class TUILogHandler(logging.Handler):
    def __init__(self, maxlen=80):
        super().__init__()
        self.records: deque[str] = deque(maxlen=maxlen)

    def emit(self, record):
        ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        lvl = record.levelname[0]
        color = {"I": "dim", "W": "yellow", "E": "red bold"}.get(lvl, "")
        self.records.append(f"[{color}]{ts} {lvl} {record.getMessage()}[/]")


# ─── TUI state ────────────────────────────────────────────────────────────

class ExperimentState:
    def __init__(self, total_iterations: int, scenarios_per_seq: int):
        self.total_iterations = total_iterations
        self.scenarios_per_seq = scenarios_per_seq
        self.total_scenarios = total_iterations * scenarios_per_seq

        self.iteration = 0
        self.scenario_idx_in_seq = 0
        self.scenarios_completed = 0
        self.acr_toggles = 0

        self.acr_state = "ON"
        self.current_scenario = ""
        self.current_seq_num = 0
        self.current_seq_scenarios: tuple = ()
        self.phase = "idle"

        self.experiment_start = time.monotonic()
        self.scenario_start = time.monotonic()
        self.errors = 0


# ─── Layout ───────────────────────────────────────────────────────────────

def build_layout() -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header",  size=3),
        Layout(name="body",    ratio=1),
        Layout(name="footer",  size=3),
    )
    layout["body"].split_row(
        Layout(name="left",  ratio=2),
        Layout(name="right", ratio=3),
    )
    layout["left"].split_column(
        Layout(name="status",   ratio=3),
        Layout(name="sequence", ratio=2),
    )
    return layout


def render_header(state: ExperimentState) -> Panel:
    elapsed = timedelta(seconds=int(time.monotonic() - state.experiment_start))
    grid = Table.grid(expand=True)
    grid.add_column(justify="left",  ratio=1)
    grid.add_column(justify="center", ratio=1)
    grid.add_column(justify="right", ratio=1)
    grid.add_row(
        "[bold bright_white]🎌 Sony Bravia ACR Experiment[/]",
        f"[dim]{TV_IP}:{TV_PORT}[/]  [dim]MAC {TV_MAC}[/]",
        f"[bold]⏱  {elapsed}[/]",
    )
    return Panel(grid, style="bright_blue")


def render_status(state: ExperimentState) -> Panel:
    tbl = Table.grid(padding=(0, 2))
    tbl.add_column(justify="right", style="bold", min_width=16)
    tbl.add_column(justify="left")

    acr_color = "green" if state.acr_state == "ON" else "red"
    acr_icon = "● " if state.acr_state == "ON" else "○ "
    tbl.add_row("ACR State", f"[bold {acr_color}]{acr_icon}{state.acr_state}[/]")
    tbl.add_row("Iteration", f"[bold]{state.iteration + 1}[/] / {state.total_iterations}")
    tbl.add_row("Sequence #", f"[bold]{state.current_seq_num + 1}[/] / {(state.total_iterations - 1) // 2 + 1}")

    sc = state.current_scenario
    if sc:
        icon = SCENARIO_ICONS.get(sc, "")
        color = SCENARIO_COLORS.get(sc, "white")
        tbl.add_row("Scenario", f"[bold {color}]{icon} {sc}[/]  ({state.scenario_idx_in_seq + 1}/{state.scenarios_per_seq})")
    else:
        tbl.add_row("Scenario", "[dim]—[/]")

    tbl.add_row("Phase", PHASE_LABELS.get(state.phase, state.phase))
    tbl.add_row("", "")
    tbl.add_row("Completed", f"[bold green]{state.scenarios_completed}[/] / {state.total_scenarios}")
    tbl.add_row("ACR Toggles", f"[bold magenta]{state.acr_toggles}[/]")
    if state.errors:
        tbl.add_row("Errors", f"[bold red]{state.errors}[/]")

    return Panel(tbl, title="[bold]Status[/]", border_style="bright_blue")


def render_sequence(state: ExperimentState) -> Panel:
    if not state.current_seq_scenarios:
        return Panel("[dim]Waiting to start...[/]", title="[bold]Current Sequence[/]", border_style="bright_blue")

    items = []
    for idx, sc in enumerate(state.current_seq_scenarios):
        icon = SCENARIO_ICONS.get(sc, " ")
        color = SCENARIO_COLORS.get(sc, "white")
        if idx < state.scenario_idx_in_seq:
            items.append(f"  [dim strikethrough]{icon} {sc}[/]  [green]✓[/]")
        elif idx == state.scenario_idx_in_seq and state.current_scenario == sc:
            items.append(f"  [bold {color}]▸ {icon} {sc}[/]  [bright_yellow]◀[/]")
        else:
            items.append(f"  [dim]{icon} {sc}[/]")

    return Panel("\n".join(items), title=f"[bold]Sequence {state.current_seq_num + 1}[/]", border_style="bright_blue")


def render_log(log_handler: TUILogHandler) -> Panel:
    lines = list(log_handler.records)
    display = "\n".join(lines[-40:]) if lines else "[dim]No log messages yet...[/]"
    return Panel(display, title="[bold]Log[/]", border_style="dim")


def render_footer(overall_progress: Progress) -> Panel:
    return Panel(overall_progress, style="bright_blue")


# ─── Experiment runner with TUI ───────────────────────────────────────────

class SonyExperimentTUI:
    def __init__(self):
        self.ivd_states: list[str] = []
        self.ivd_scenario: list[tuple] = []
        self.console = Console()

        with open("scenarios.txt", "r") as f:
            self.raw_scenarios = [l.strip() for l in f.readlines() if l.strip()]
        with open("states.txt", "r") as f:
            self.raw_states = [l.strip() for l in f.readlines() if l.strip()]

    def convert_states_to_list(self):
        for element in self.raw_states:
            tpl = ast.literal_eval(element)
            for transition in tpl:
                for low_transition in transition:
                    states = low_transition.replace(" ", "").strip().split("-")
                    self.ivd_states.append(states[0])
                    self.ivd_states.append(states[1])

    def convert_scenarios_to_list(self):
        for element in self.raw_scenarios:
            tpl = ast.literal_eval(element)
            self.ivd_scenario.append(tpl)

    async def run(self):
        self.convert_states_to_list()
        self.convert_scenarios_to_list()

        n_iterations = len(self.ivd_scenario)
        n_per_seq = len(self.ivd_scenario[0])

        state = ExperimentState(n_iterations, n_per_seq)
        log_handler = TUILogHandler(maxlen=200)

        root_logger = logging.getLogger()
        log_handler.setLevel(logging.DEBUG)
        root_logger.addHandler(log_handler)

        overall_progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold]{task.description}"),
            BarColumn(bar_width=None),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TextColumn("ETA"),
            TimeRemainingColumn(),
            expand=True,
        )
        overall_task = overall_progress.add_task("Scenarios", total=state.total_scenarios)

        layout = build_layout()

        with Live(layout, console=self.console, refresh_per_second=4, screen=True):

            async def refresh():
                layout["header"].update(render_header(state))
                layout["status"].update(render_status(state))
                layout["sequence"].update(render_sequence(state))
                layout["right"].update(render_log(log_handler))
                layout["footer"].update(render_footer(overall_progress))

            async def set_phase(phase: str):
                state.phase = phase
                await refresh()

            # ── Experiment loop (separate toggle_acr_on/off) ──

            scenario_sequence_number = 0
            last_acr_state = "ON"

            await set_phase("power_off")
            await power_off()

            for i in range(n_iterations):
                state.iteration = i
                current_acr_state = self.ivd_states[i]
                state.acr_state = current_acr_state
                await refresh()

                if current_acr_state != last_acr_state:
                    state.acr_toggles += 1
                    await set_phase("boot")
                    await power_on()
                    await set_phase("acr_toggle")
                    if current_acr_state == "ON":
                        await toggle_acr_on()
                    else:
                        await toggle_acr_off()
                    await set_phase("power_off")
                    await power_off()

                last_acr_state = current_acr_state
                scenario_sequence_number = i // 2
                seq = self.ivd_scenario[scenario_sequence_number]
                state.current_seq_num = scenario_sequence_number
                state.current_seq_scenarios = seq

                for j, current_test_scenario in enumerate(seq):
                    state.scenario_idx_in_seq = j
                    state.current_scenario = current_test_scenario
                    state.scenario_start = time.monotonic()

                    await set_phase("boot")
                    await power_on()

                    await set_phase("launch")
                    await refresh()

                    try:
                        if current_test_scenario == "IDLE":
                            await open_idle()
                        elif current_test_scenario == "FAST":
                            await open_fast()
                        elif current_test_scenario == "HDMI":
                            await open_hdmi()
                        elif current_test_scenario == "ANTENNA 14.1":
                            await open_antenna_14_1()
                        elif current_test_scenario == "ANTENNA":
                            await open_antenna()
                        elif current_test_scenario == "NETFLIX":
                            await open_netflix()
                        elif current_test_scenario == "YOUTUBE":
                            await open_youtube()
                        elif current_test_scenario == "TUBI":
                            await open_tubi()

                        await set_phase("exit")
                        await exit_to_home()

                    except Exception as e:
                        state.errors += 1
                        logger.error(f"Scenario {current_test_scenario} failed: {e}")

                    await set_phase("home")
                    await go_home()
                    await set_phase("power_off")
                    await power_off()

                    state.scenarios_completed += 1
                    overall_progress.update(overall_task, completed=state.scenarios_completed)
                    await refresh()

            state.phase = "idle"
            state.current_scenario = ""
            await refresh()
            logger.info("🎉 Experiment complete!")
            await asyncio.sleep(5)


if __name__ == "__main__":
    tui = SonyExperimentTUI()
    asyncio.run(tui.run())
