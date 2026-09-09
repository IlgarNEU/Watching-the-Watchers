import pprint
import ast
import json
import os
from SonyAutomation import *

experiment_logger = logging.getLogger("experiment")
experiment_logger.setLevel(logging.INFO)
experiment_logger.propagate = False
experiment_logger.addHandler(
    logging.FileHandler(f"SONY2HIGHLEVEL_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
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
        self.ivd_scenario = []
        with open("scenarios.txt", "r") as file:
            self.scenarios = [line.strip() for line in file.readlines()]

    def save_progress(self, i, scenario_index):
        with open(PROGRESS_FILE, "w") as f:
            json.dump({"iteration": i, "scenario_index": scenario_index}, f)

    def load_progress(self):
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, "r") as f:
                data = json.load(f)
                experiment_logger.info(f"Resuming from iteration {data['iteration']}, scenario {data['scenario_index']}")
                return data["iteration"], data["scenario_index"]
        return 0, 0

    def clear_progress(self):
        if os.path.exists(PROGRESS_FILE):
            os.remove(PROGRESS_FILE)

    def convert_scenarios_to_list(self):
        for element in self.scenarios:
            tpl = ast.literal_eval(element)
            self.ivd_scenario.append(tpl)

    async def ensure_tv_off(self):
        """Power off only if the TV is currently on, to avoid toggling it on."""
        try:
            resp = sony_call("system", "getPowerStatus")
            status = resp.get("result", [{}])[0].get("status") if resp else None
            if status == "active":
                experiment_logger.info("TV is on — powering off before starting.")
                await power_off()
            else:
                experiment_logger.info(f"TV is already off (status={status!r}), skipping power off.")
        except Exception as e:
            experiment_logger.warning(f"Could not check power state before start: {e}")

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

        else:
            experiment_logger.warning(f"Unknown scenario: {current_test_scenario!r} — skipping.")

    async def run_experiment(self):
        self.convert_scenarios_to_list()

        start_i, start_scenario_index = self.load_progress()

        # Only power off if TV is currently on — avoids toggling it on accidentally
        await self.ensure_tv_off()

        for i in range(start_i, len(self.ivd_scenario)):
            experiment_logger.info(f"Experiment starts - Iteration {i}")

            scenarios_to_run = self.ivd_scenario[i]
            scenario_start = start_scenario_index if i == start_i else 0

            for j in range(scenario_start, len(scenarios_to_run)):
                current_test_scenario = scenarios_to_run[j]
                experiment_logger.info(f"=== Running scenario: {current_test_scenario}")

                for attempt in range(1, MAX_RETRIES + 1):
                    try:
                        await power_on()

                        await self.run_scenario(current_test_scenario)

                        experiment_logger.info(f"=== Done scenario: {current_test_scenario} ===")
                        await go_home()
                        await power_off()

                        self.save_progress(i, j + 1)
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
                            self.save_progress(i, j + 1)

        self.clear_progress()
        experiment_logger.info("Experiment complete.")


if __name__ == "__main__":
    sa = AutomateSony()
    asyncio.run(sa.run_experiment())