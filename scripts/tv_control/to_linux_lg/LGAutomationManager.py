import pprint
import ast
import json
import os
from LGAutomation import *

experiment_logger = logging.getLogger("experiment")
experiment_logger.setLevel(logging.INFO)
experiment_logger.propagate = False
experiment_logger.addHandler(
    logging.FileHandler(f"LGHIGHLEVEL_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
)
experiment_logger.handlers[0].setFormatter(logging.Formatter(
    fmt="%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
))

PROGRESS_FILE = "lg_experiment_progress.json"
RETRY_WAIT = 30
MAX_RETRIES = 3


class AutomateLG:
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

    async def safe_connect(self):
        for attempt in range(MAX_RETRIES):
            try:
                client = await connect()
                return client
            except Exception as e:
                experiment_logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_WAIT)
        raise RuntimeError("Could not connect to LG TV after multiple attempts")

    async def run_scenario(self, client, current_test_scenario):
        if current_test_scenario == 'IDLE':
            client = await open_idle(client)

        elif current_test_scenario == 'FAST':
            client = await open_fast(client)
            client = await exit_anything(client)

        elif current_test_scenario == 'NETFLIX':
            client = await open_netflix(client)
            client = await exit_anything(client)

        elif current_test_scenario == 'YOUTUBE':
            client = await open_youtube(client)
            client = await exit_anything(client)

        elif current_test_scenario == 'TUBI':
            client = await open_tubi(client)
            client = await exit_anything(client)

        elif current_test_scenario == 'ANTENNA':
            client = await open_antenna(client)
            client = await exit_anything(client)

        elif current_test_scenario == 'ANTENNA 10.1':
            client = await open_antenna_custom(client)
            client = await exit_anything(client)

        elif current_test_scenario == 'ANTENNA 14.1':
            client = await open_antenna_custom_2(client)
            client = await exit_anything(client)

        elif current_test_scenario == 'HDMI':
            client = await open_hdmi(client)
            client = await exit_anything(client)

        else:
            logger.warning(f"Unknown scenario: {current_test_scenario}")

        return client

    async def run_experiment(self):
        self.convert_states_to_list()
        self.convert_scenarios_to_list()

        start_i, start_scenario_index, last_acr_state = self.load_progress()
        client = await self.safe_connect()
        await power_off(client)

        for i in range(start_i, len(self.ivd_scenario)):
            current_acr_state = self.ivd_states[i]
            seq = i // 2

            experiment_logger.info(f"Experiment starts - Iteration {i}, Sequence {seq}")

            if current_acr_state != last_acr_state:
                logger.info(f"ACR state change: {last_acr_state} → {current_acr_state}")
                experiment_logger.info(f"ACR state change: {last_acr_state} → {current_acr_state}")
                client = await power_on()
                client = await go_home(client)
                client = await toggle_acr(client)
                client = await go_home(client)
                await power_off(client)

            last_acr_state = current_acr_state
            scenario_sequence_number = i // 2
            scenarios_to_run = self.ivd_scenario[scenario_sequence_number]

            scenario_start = start_scenario_index if i == start_i else 0

            for j in range(scenario_start, len(scenarios_to_run)):
                current_test_scenario = scenarios_to_run[j]
                logger.info(f"=== Running scenario: {current_test_scenario} (ACR={current_acr_state}) ===")
                experiment_logger.info(f"=== Running scenario: {current_test_scenario} (ACR={current_acr_state}) ===")

                for attempt in range(1, MAX_RETRIES + 1):
                    try:
                        client = await power_on()
                        client = await go_home(client)

                        client = await self.run_scenario(client, current_test_scenario)

                        experiment_logger.info(f"=== Done scenario: {current_test_scenario} (ACR={current_acr_state}) ===")
                        client = await go_home(client)
                        await power_off(client)

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
                            try:
                                client = await self.safe_connect()
                            except Exception as reconnect_err:
                                experiment_logger.error(f"Reconnect failed: {reconnect_err}")
                        else:
                            experiment_logger.critical(
                                f"Scenario '{current_test_scenario}' failed after {MAX_RETRIES} attempts. Skipping."
                            )
                            self.save_progress(i, j + 1, last_acr_state)

        self.clear_progress()
        experiment_logger.info("Experiment complete.")


if __name__ == "__main__":
    sa = AutomateLG()
    asyncio.run(sa.run_experiment())