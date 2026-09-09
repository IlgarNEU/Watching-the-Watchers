import pprint
import ast
from FireTVAutomation import *


class AutomateFireTV:
    def __init__(self):
        self.ivd_states = []
        self.ivd_scenario = []
        with open("scenarios.txt", "r") as file:
            self.scenarios = [line.strip() for line in file.readlines()]

        with open("states.txt", "r") as file:
            self.states = [line.strip() for line in file.readlines()]

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

    async def run_experiment(self):
        self.convert_states_to_list()
        self.convert_scenarios_to_list()
        scenario_sequence_number = 0
        last_acr_state = "OFF"
        await connect()
        await power_off()
        for i in range(len(self.ivd_scenario)):
            current_acr_state = self.ivd_states[i]
            if current_acr_state != last_acr_state:
                await power_on()
                await connect()
                await go_home()
                # Toggle ACR based on the new state
                if current_acr_state == "ON":
                    await toggle_acr_on()
                else:
                    await toggle_acr_off()
                # toggle_acr_on/off already calls power_off() at the end
            last_acr_state = current_acr_state
            scenario_sequence_number = i // 2
            for current_test_scenario in self.ivd_scenario[scenario_sequence_number]:
                await power_on()
                await connect()
                await go_home()

                if current_test_scenario == 'FAST':
                    await open_fast()
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

                elif current_test_scenario == 'ANTENNA':
                    await open_antenna()
                    await exit_to_home()

                elif current_test_scenario == 'ANTENNA 14.1':
                    await open_antenna_14_1()
                    await exit_to_home()
                
                elif current_test_scenario == 'ANTENNA 10.1':
                    await open_antenna_10_1()
                    await exit_to_home()

                elif current_test_scenario == 'HDMI':
                    await open_hdmi()
                    await exit_to_home()

                await go_home()
                await power_off()


if __name__ == "__main__":
    sa = AutomateFireTV()
    asyncio.run(sa.run_experiment())
