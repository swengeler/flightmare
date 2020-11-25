from ruamel.yaml import YAML, dump, RoundTripDumper

#
import os
import numpy as np
from time import time

#
from rpg_baselines.ppo.ppo2 import PPO2
from testing.test_env_wrapper import TestEnvWrapper

#
from flightgym import QuadrotorEnv_v1, TestEnv_v0, RacingTestEnv_v0


def main():
    # load the config
    config = YAML().load(open(os.path.join(os.getenv("FLIGHTMARE_PATH"), "flightlib/configs/racing_test_env.yaml"), "r"))
    # TODO: figure out why it complains when using this config as an input argument

    # load a model to get some decent output
    model = PPO2.load("../flightrl/examples/saved/quadrotor_env.zip")

    # get the environment
    env = TestEnvWrapper(RacingTestEnv_v0())
    env.connectUnity()
    observation = env.reset()

    # run loop with predictions from trained model
    start = time()
    last = start

    test = []
    while (time() - start) < 10:
        action, _ = model.predict(observation, deterministic=True)
        observation, _, _, _ = env.step(action)

        current = time()
        test.append(current - last)
        last = current

    env.disconnectUnity()

    print("Step time mean:", np.mean(test), "\nStep time std:", np.std(test))
    print("FPS:", 1.0 / np.mean(test))


if __name__ == "__main__":
    main()
