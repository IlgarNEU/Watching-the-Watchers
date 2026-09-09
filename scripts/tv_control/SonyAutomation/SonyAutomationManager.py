import pprint
import ast
import json
import os
from SonyAutomation import *

experiment_logger = logging.getLogger("experiment")
experiment_logger.setLevel(logging.INFO)
experiment_logger.propagate = False
experiment_logger.addHandler(
    logging.FileHandler(f"SONYHIGHLEVEL_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
)
experiment_logger.handlers[0].setFormatter(logging.Formatter(
    fmt="%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
))

PROGRESS_FILE = "experiment_progress.json"
RETRY_WAIT = 30
MAX_RETRIES = 3


class AutomateSony:
    def __init__(self):
        self.ivd_states = []
        self.ivd_scenario = []
        with open("scenarios.txt", "r") as file:
            self.scenarios = [line.strip() for line in file.readlines()]
        with open("states.txt", "r") as file:
            self.states = [line.strip() for line in file.readlines()]

    def save_progress(self, i, scenario_index, last_acr_state):
        with open(PROGRESS_FILE, "w") as f:
            json.dump({"iteration": i, "scenario_index": scenario_index, "last_acr_state": last_acr_state}, f)

    def load_progress(self):
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, "r") as f:
                data = json.load(f)
                experiment_logger.info(f"Resuming from iteration {data['iteration']}, scenario {data['scenario_index']}")
                return data["iteration"], data["scenario_index"], data.get("last_acr_state", "ON")
        return 0, 0, "ON"

    def clear_progress(self):
        if os.path.exists(PROGRESS_FILE):
            os.remove(PROGRESS_FILE)

    def convert_states_to_list(self):
        for element in self.states:
            tpl = ast.literal_eval(element)
            for transition in tpl:
                for low_transition in transition:
                    states = low_transition.replace(" ", "").strip().split("-")
                    self.ivd_states.append(states[0])
                    self.ivd_states.append(states[1])

    def convert_scenarios_to_list(self):
        for element in self.scenarios:
            tpl = ast.literal_eval(element)
            self.ivd_scenario.append(tpl)

    async def run_scenario(self, current_test_scenario):
        if current_test_scenario == 'IDLE':
            await open_idle()
            await exit_to_home()

        elif current_test_scenario == 'FAST':
            await open_fast()
            await exit_to_home()

        elif current_test_scenario == 'HDMI':
            await open_hdmi()
            await exit_to_home()

        elif current_test_scenario == 'ANTENNA 14.1':
            await open_antenna_14_1()
            await exit_to_home()

        elif current_test_scenario == 'ANTENNA 10.1':
            await open_antenna_10_1()
            await exit_to_home()

        elif current_test_scenario == 'ANTENNA':
            await open_antenna()
            await exit_to_home()

        elif current_test_scenario == 'NETFLIX':
            await open_netflix()
            await exit_to_home()

        elif current_test_scenario == 'YOUTUBE':
            await open_youtube()
            await exit_to_home()

        elif current_test_scenario == 'TUBI':
            await open_tubi()
            await exit_to_home()

    async def run_experiment(self):
        self.convert_states_to_list()
        self.convert_scenarios_to_list()

        start_i, start_scenario_index, last_acr_state = self.load_progress()
        await power_off()

        for i in range(start_i, len(self.ivd_scenario)):
            current_acr_state = self.ivd_states[i]
            seq = i // 2

            experiment_logger.info(f"Experiment starts - Iteration {i}, Sequence {seq}")

            if current_acr_state != last_acr_state:
                experiment_logger.info(f"ACR state change: {last_acr_state} → {current_acr_state}")
                await power_on()
                if current_acr_state == "ON":
                    await toggle_acr_on()
                else:
                    await toggle_acr_off()
                await power_off()

            last_acr_state = current_acr_state
            scenario_sequence_number = i // 2
            scenarios_to_run = self.ivd_scenario[scenario_sequence_number]

            scenario_start = start_scenario_index if i == start_i else 0

            for j in range(scenario_start, len(scenarios_to_run)):
                current_test_scenario = scenarios_to_run[j]
                experiment_logger.info(f"=== Running scenario: {current_test_scenario} (ACR={current_acr_state}) ===")

                for attempt in range(1, MAX_RETRIES + 1):
                    try:
                        await power_on()

                        await self.run_scenario(current_test_scenario)

                        experiment_logger.info(f"=== Done scenario: {current_test_scenario} (ACR={current_acr_state}) ===")
                        await go_home()
                        await power_off()

                        self.save_progress(i, j + 1, last_acr_state)
                        break

                    except asyncio.CancelledError:
                        raise

                    except Exception as e:
                        experiment_logger.error(
                            f"[Attempt {attempt}/{MAX_RETRIES}] Scenario '{current_test_scenario}' "
                            f"failed at iteration {i}, scenario {j}: {e}"
                        )
                        if attempt < MAX_RETRIES:
                            experiment_logger.info(f"Waiting {RETRY_WAIT}s before retry...")
                            await asyncio.sleep(RETRY_WAIT)
                        else:
                            experiment_logger.critical(
                                f"Scenario '{current_test_scenario}' failed after {MAX_RETRIES} attempts. Skipping."
                            )
                            self.save_progress(i, j + 1, last_acr_state)

        self.clear_progress()
        experiment_logger.info("Experiment complete.")


if __name__ == "__main__":
    sa = AutomateSony()
    asyncio.run(sa.run_experiment())