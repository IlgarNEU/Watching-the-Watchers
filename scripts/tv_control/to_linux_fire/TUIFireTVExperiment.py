#!/usr/bin/env python3
"""
FireTV ACR Experiment — Rich Terminal UI
=========================================
Drop-in replacement for FireTVAutomationManager.py.
Runs the identical experiment loop but renders a live
dashboard so you can see exactly what's happening.

Usage:
    python FireTVExperimentTUI.py
"""

import ast
import asyncio
import json
import logging
import os
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

from FireTVAutomation import *

# ─── Constants ───────────────────────────────────────────────────────────

PROGRESS_FILE = "fire_experiment_progress.json"
RETRY_WAIT = 30
MAX_RETRIES = 3

# ─── Scenario metadata ───────────────────────────────────────────────────

SCENARIO_ICONS = {
    "FAST":         "⚡",
    "NETFLIX":      "🎬",
    "TUBI":         "📺",
    "YOUTUBE":      "▶ ",
    "ANTENNA":      "📡",
    "ANTENNA 14.1": "📡",
    "ANTENNA 10.1": "📡",
    "HDMI":         "🔌",
    "IDLE":         "💤",
}

SCENARIO_COLORS = {
    "FAST":         "bright_yellow",
    "NETFLIX":      "red",
    "TUBI":         "magenta",
    "YOUTUBE":      "bright_red",
    "ANTENNA":      "cyan",
    "ANTENNA 14.1": "bright_cyan",
    "ANTENNA 10.1": "bright_cyan",
    "HDMI":         "green",
    "IDLE":         "bright_black",
}

PHASE_LABELS = {
    "idle":        "[dim]Idle[/]",
    "boot":        "[yellow]⏻  Booting[/]",
    "connect":     "[yellow]🔌 Connecting ADB[/]",
    "home":        "[blue]🏠 Going Home[/]",
    "navigate":    "[blue]🧭 Navigating[/]",
    "launch":      "[green]🚀 Launching[/]",
    "watch":       "[bright_green]👁  Watching[/]",
    "exit":        "[blue]🚪 Exiting[/]",
    "acr_toggle":  "[bright_magenta]🔒 Toggling ACR[/]",
    "power_off":   "[red]⏻  Powering Off[/]",
    "retrying":    "[yellow]🔄 Retrying...[/]",
}


# ─── Log capture ──────────────────────────────────────────────────────────

class TUILogHandler(logging.Handler):
    """Captures log records into a bounded deque for the TUI."""

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
    """Mutable state bag the TUI reads on each refresh."""

    def __init__(self, total_iterations: int, scenarios_per_seq: int):
        self.total_iterations = total_iterations
        self.scenarios_per_seq = scenarios_per_seq
        self.total_scenarios = total_iterations * scenarios_per_seq

        # Progress
        self.iteration = 0
        self.scenario_idx_in_seq = 0
        self.scenarios_completed = 0
        self.acr_toggles = 0

        # Current labels
        self.acr_state = "ON"
        self.current_scenario = ""
        self.current_seq_num = 0
        self.current_seq_scenarios: tuple = ()
        self.phase = "idle"

        # Timing
        self.experiment_start = time.monotonic()
        self.scenario_start = time.monotonic()

        # Errors / retries
        self.errors = 0
        self.retries = 0


# ─── Layout builder ───────────────────────────────────────────────────────

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
        f"[bold bright_white]🔥 Fire TV ACR Experiment[/]",
        f"[dim]{FIRETV_IP}:{FIRETV_PORT}[/]  [dim]MAC {FIRETV_MAC}[/]",
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
    if state.retries:
        tbl.add_row("Retries", f"[bold yellow]{state.retries}[/]")
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

    return Panel(
        "\n".join(items),
        title=f"[bold]Sequence {state.current_seq_num + 1}[/]",
        border_style="bright_blue",
    )


def render_log(log_handler: TUILogHandler) -> Panel:
    lines = list(log_handler.records)
    display = "\n".join(lines[-40:]) if lines else "[dim]No log messages yet...[/]"
    return Panel(display, title="[bold]Log[/]", border_style="dim")


def render_footer(state: ExperimentState, overall_progress: Progress) -> Panel:
    return Panel(overall_progress, style="bright_blue")


# ─── Experiment runner with TUI ───────────────────────────────────────────

class FireTVExperimentTUI:
    def __init__(self):
        self.ivd_states: list[str] = []
        self.ivd_scenario: list[tuple] = []
        self.console = Console()

        with open("scenarios.txt", "r") as f:
            self.raw_scenarios = [l.strip() for l in f.readlines() if l.strip()]
        with open("states.txt", "r") as f:
            self.raw_states = [l.strip() for l in f.readlines() if l.strip()]

    # ─── Progress persistence ─────────────────────────────────────────────

    def save_progress(self, i, scenario_index, last_acr_state):
        with open(PROGRESS_FILE, "w") as f:
            json.dump({"iteration": i, "scenario_index": scenario_index, "last_acr_state": last_acr_state}, f)

    def load_progress(self):
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, "r") as f:
                data = json.load(f)
                logger.info(f"Resuming from iteration {data['iteration']}, scenario {data['scenario_index']}")
                return data["iteration"], data["scenario_index"], data.get("last_acr_state", "ON")
        return 0, 0, "ON"

    def clear_progress(self):
        if os.path.exists(PROGRESS_FILE):
            os.remove(PROGRESS_FILE)

    # ─── Data conversion ──────────────────────────────────────────────────

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

    # ─── Scenario dispatcher ──────────────────────────────────────────────

    async def run_scenario(self, current_test_scenario):
        if current_test_scenario == "FAST":
            await open_fast()
        elif current_test_scenario == "IDLE":
            await open_idle()
        elif current_test_scenario == "NETFLIX":
            await open_netflix()
        elif current_test_scenario == "YOUTUBE":
            await open_youtube()
        elif current_test_scenario == "TUBI":
            await open_tubi()
        elif current_test_scenario == "ANTENNA":
            await open_antenna()
        elif current_test_scenario == "ANTENNA 14.1":
            await open_antenna_14_1()
        elif current_test_scenario == "ANTENNA 10.1":
            await open_antenna_10_1()
        elif current_test_scenario == "HDMI":
            await open_hdmi()

    # ─── Main loop ────────────────────────────────────────────────────────

    async def run(self):
        self.convert_states_to_list()
        self.convert_scenarios_to_list()

        n_iterations = len(self.ivd_scenario)
        n_per_seq = len(self.ivd_scenario[0])

        start_i, start_scenario_index, last_acr_state = self.load_progress()

        state = ExperimentState(n_iterations, n_per_seq)
        state.acr_state = last_acr_state
        state.scenarios_completed = start_i * n_per_seq + start_scenario_index

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
        overall_task = overall_progress.add_task(
            "Scenarios", total=state.total_scenarios, completed=state.scenarios_completed
        )

        layout = build_layout()

        with Live(layout, console=self.console, refresh_per_second=4, screen=True):

            async def refresh():
                layout["header"].update(render_header(state))
                layout["status"].update(render_status(state))
                layout["sequence"].update(render_sequence(state))
                layout["right"].update(render_log(log_handler))
                layout["footer"].update(render_footer(state, overall_progress))

            async def set_phase(phase: str):
                state.phase = phase
                await refresh()

            await set_phase("connect")
            await connect()
            await set_phase("power_off")
            await power_off()

            for i in range(start_i, n_iterations):
                state.iteration = i
                current_acr_state = self.ivd_states[i]
                state.acr_state = current_acr_state
                await refresh()

                if current_acr_state != last_acr_state:
                    state.acr_toggles += 1
                    await set_phase("boot")
                    await power_on()
                    await set_phase("connect")
                    await connect()
                    await set_phase("home")
                    await go_home()
                    await set_phase("acr_toggle")
                    if current_acr_state == "ON":
                        await toggle_acr_on()
                    else:
                        await toggle_acr_off()

                last_acr_state = current_acr_state
                scenario_sequence_number = i // 2
                seq = self.ivd_scenario[scenario_sequence_number]
                state.current_seq_num = scenario_sequence_number
                state.current_seq_scenarios = seq

                scenario_start = start_scenario_index if i == start_i else 0

                for j in range(scenario_start, len(seq)):
                    current_test_scenario = seq[j]
                    state.scenario_idx_in_seq = j
                    state.current_scenario = current_test_scenario
                    state.scenario_start = time.monotonic()
                    await refresh()

                    for attempt in range(1, MAX_RETRIES + 1):
                        try:
                            await set_phase("boot")
                            await power_on()
                            await set_phase("connect")
                            await connect()
                            await set_phase("home")
                            await go_home()
                            await set_phase("launch")

                            await self.run_scenario(current_test_scenario)

                            await set_phase("exit")
                            await exit_to_home()
                            await set_phase("home")
                            await go_home()
                            await set_phase("power_off")
                            await power_off()

                            state.scenarios_completed += 1
                            overall_progress.update(overall_task, completed=state.scenarios_completed)
                            self.save_progress(i, j + 1, last_acr_state)
                            await refresh()
                            break

                        except asyncio.CancelledError:
                            raise

                        except Exception as e:
                            state.errors += 1
                            state.retries += 1
                            logger.error(f"[Attempt {attempt}/{MAX_RETRIES}] Scenario '{current_test_scenario}' failed: {e}")
                            await set_phase("retrying")
                            if attempt < MAX_RETRIES:
                                logger.info(f"Waiting {RETRY_WAIT}s before retry...")
                                await asyncio.sleep(RETRY_WAIT)
                            else:
                                logger.critical(f"Scenario '{current_test_scenario}' failed after {MAX_RETRIES} attempts. Skipping.")
                                self.save_progress(i, j + 1, last_acr_state)

            self.clear_progress()
            state.phase = "idle"
            state.current_scenario = ""
            await refresh()
            logger.info("🎉 Experiment complete!")
            await asyncio.sleep(5)


# ─── Entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    tui = FireTVExperimentTUI()
    asyncio.run(tui.run())