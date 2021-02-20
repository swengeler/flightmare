import numpy as np

from collections import deque
from mpc.simulation.planner import TrajectorySampler
from mpc.simulation.mpc_test_wrapper import MPCTestWrapper, RacingEnvWrapper

# TODO: remove this stuff or put it somewhere else
# state index
kPosX = 0
kPosY = 1
kPosZ = 2
kQuatW = 3
kQuatX = 4
kQuatY = 5
kQuatZ = 6
kVelX = 7
kVelY = 8
kVelZ = 9

# action index
kThrust = 0
kWx = 1
kWy = 2
kWz = 3


class Simulation:

    def __init__(self, config):
        # TODO: change these to dummy values
        self.current_image = None
        self.current_state = None
        self.current_state_estimate = None
        self.current_reference = None

        self.base_frequency = config.base_frequency  # 100.0
        self.image_frequency = config.image_frequency  # 30.0
        self.ref_frequency = config.ref_frequency  # 50.0
        self.command_frequency = config.command_frequency  # 100.0
        self.expert_command_frequency = config.expert_command_frequency  # 20.0

        assert self.base_frequency >= self.command_frequency

        self.base_time_step = 1.0 / self.base_frequency
        self.image_time_step = 1.0 / self.image_frequency
        self.ref_time_step = 1.0 / self.ref_frequency
        self.command_time_step = 1.0 / self.command_frequency
        self.expert_command_time_step = 1.0 / self.expert_command_frequency

        base_time_step_int = self.base_time_step / self.base_time_step
        image_time_step_int = self.image_time_step / self.base_time_step
        ref_time_step_int = self.ref_time_step / self.base_time_step
        command_time_step_int = self.command_time_step / self.base_time_step
        expert_command_time_step_int = self.expert_command_time_step / self.base_time_step

        """
        print(base_time_step_int, image_time_step_int, ref_time_step_int,
              command_time_step_int, expert_command_time_step_int, sep="\n")
        print()
        print(np.lcm.reduce([self.base_frequency, self.image_frequency, self.ref_frequency, self.command_frequency, self.expert_command_frequency]))
        print(np.lcm.reduce([100, 20, 50, 100, 20]))
        print()
        """

        self.base_time = 0.0
        self.image_time = 0.0
        self.ref_time = 0.0
        self.command_time = 0.0
        self.expert_command_time = 0.0

        self.total_time = 10.0  # TODO: make this dependent on the trajectory
        self.trajectory_done = False

        self.image_updated = False
        self.reference_updated = False
        self.command_to_be_updated = False
        self.expert_to_be_updated = False

    def reset(self):
        self.base_time = 0.0
        self.image_time = 0.0
        self.ref_time = 0.0
        self.command_time = 0.0
        self.expert_command_time = 0.0

        self.total_time = 10.0
        self.trajectory_done = False

        self.image_updated = False
        self.reference_updated = False
        self.command_to_be_updated = False
        self.expert_to_be_updated = False

        self._reset()

        self.current_state, success = self._get_state()
        self.current_state_estimate = self._get_state_estimate()
        self.current_image = self._get_image()
        self.current_reference = self._get_reference()
        self.expert_to_be_updated = self._determine_expert_update()

        result = {
            "done": self.trajectory_done,
            "time": self.base_time,
            "state": self.current_state,
            "state_estimate": self.current_state_estimate,
            "image": self.current_image,
            "reference": self.current_reference,
            "update": {
                "image": self.image_updated,
                "reference": self.reference_updated,
                "command": self.command_to_be_updated,
                "expert": self.expert_to_be_updated,
            },
        }
        return result

    def step(self, action):
        # self.command_time += self.command_time_step

        self.image_updated = False
        self.reference_updated = False
        self.command_to_be_updated = False
        self.expert_to_be_updated = False

        # successes = []

        # TODO: somehow need to change this so that even at faster rates the correct thing is returned...
        #  => just return after one "base step"?
        #  => have queues of stuff...
        #  => also, images should probably have time_stamps attached, since otherwise the velocity calc will be wrong

        # while self.base_time < self.command_time <= self.total_time:
        # TODO: this apparently leads to numerical problems... would probably be better to use integers for counting... somehow
        self.base_time += self.base_time_step
        if self.command_time <= self.base_time:
            self.command_time += self.command_time_step
            self.command_to_be_updated = True

        self.current_state, success = self._get_state(action)
        self.current_state_estimate = self._get_state_estimate()
        self.current_image = self._get_image()
        self.current_reference = self._get_reference()
        self.expert_to_be_updated = self._determine_expert_update()
        # successes.append(success)

        if self.base_time > self.total_time:  # or self.command_time > self.total_time:
            # TODO: there should be a more elegant way of doing this than having to check the command_time separately
            self.trajectory_done = True

        result = {
            "done": self.trajectory_done,
            "time": self.base_time,
            "state": self.current_state,
            "state_estimate": self.current_state_estimate,
            "image": self.current_image,
            "reference": self.current_reference,
            "update": {
                "image": self.image_updated,
                "reference": self.reference_updated,
                "command": self.command_to_be_updated,
                "expert": self.expert_to_be_updated,
            },
        }

        return result

    def _reset(self):
        pass

    def _get_state(self, action=None):
        raise NotImplementedError()

    def _get_state_estimate(self):
        raise NotImplementedError()

    def _get_image(self):
        raise NotImplementedError()

    def _get_reference(self):
        raise NotImplementedError()

    def _determine_expert_update(self):
        if self.expert_command_time <= self.base_time:
            self.expert_command_time += self.expert_command_time_step
            self.expert_to_be_updated = True
        return self.expert_to_be_updated


class PythonSimulation(Simulation):

    def __init__(self, config, trajectory_path):
        super().__init__(config)

        self.state_dim = 10
        self.action_dim = 4

        # Flightmare wrapper/bridge, in this class mostly to get images
        self.flightmare_wrapper = MPCTestWrapper(wave_track=False)
        self.current_image = np.zeros((self.flightmare_wrapper.image_width, self.flightmare_wrapper.image_height, 3),
                                      dtype=np.uint8)

        # sampler to get reference states for the network only (not for the MPC expert)
        self.reference_sampler = TrajectorySampler(trajectory_path)
        self.current_reference = np.zeros((self.state_dim,), dtype=np.float64)

        self.total_time = self.reference_sampler.get_final_time_stamp()

        # quadrotor/dynamics stuff
        self.quad_mass = 1.0
        self.quad_state = self.reference_sampler.get_initial_state()
        self.current_state = self.quad_state  # TODO: need some sort of reset/init state thingy

        self.gravity = 9.81

    #####################################
    # TAKING CARE OF FLIGHTMARE WRAPPER # (not sure if$ overkill, but it's kinda neat)
    #####################################

    def connect_unity(self):
        self.flightmare_wrapper.connect_unity()

    def disconnect_unity(self):
        self.flightmare_wrapper.disconnect_unity()

    ##################
    # GETTER METHODS #
    ##################

    def _get_state(self, action):
        self.current_state = self._dynamics_integration(action)
        return self.current_state

    def _get_state_estimate(self):
        self.current_state_estimate = self.current_state
        return self.current_state_estimate

    def _get_image(self):
        if self.image_time <= self.base_time:
            self.image_time += self.image_time_step
            self.current_image = self.flightmare_wrapper.step(self.current_state)
            self.image_updated = True
        return self.current_image

    def _get_reference(self):
        if self.ref_time <= self.base_time:
            self.ref_time += self.ref_time_step
            self.current_reference = self.reference_sampler.sample_from_trajectory(self.base_time)  # TODO: should this be ref_time?
            self.reference_updated = True
        return self.current_reference

    ########################
    # QUADROTOR SIMULATION #
    ########################

    def _dynamics_integration(self, action):
        refine_steps = 4
        refine_dt = self.base_time_step / refine_steps

        # Runge-Kutta 4th order integration
        state = self.quad_state
        for i in range(refine_steps):
            k1 = refine_dt * self._quad_dynamics(state, action)
            k2 = refine_dt * self._quad_dynamics(state + 0.5 * k1, action)
            k3 = refine_dt * self._quad_dynamics(state + 0.5 * k2, action)
            k4 = refine_dt * self._quad_dynamics(state + k3, action)

            state = state + (k1 + 2.0 * (k2 + k3) + k4) / 6.0

        self.quad_state = state
        return self.quad_state

    def _quad_dynamics(self, state, action):
        thrust, wx, wy, wz = action
        thrust /= self.quad_mass

        qw, qx, qy, qz = self._get_quaternion(state)

        # dynamics
        state_dot = np.zeros(self.state_dim)

        # linear velocity
        state_dot[kPosX:kPosZ + 1] = state[kVelX:kVelZ + 1]

        # angular velocity (?)
        state_dot[kQuatW] = 0.5 * (-wx * qx - wy * qy - wz * qz)
        state_dot[kQuatX] = 0.5 * (wx * qw + wz * qy - wy * qz)
        state_dot[kQuatY] = 0.5 * (wy * qw - wz * qx + wx * qz)
        state_dot[kQuatZ] = 0.5 * (wz * qw + wy * qx - wx * qy)

        # linear acceleration (?)
        state_dot[kVelX] = 2 * (qw * qy + qx * qz) * thrust
        state_dot[kVelY] = 2 * (qy * qz - qw * qx) * thrust
        state_dot[kVelZ] = (qw * qw - qx * qx - qy * qy + qz * qz) * thrust - self.gravity

        return state_dot

    def _get_quaternion(self, state=None):
        if state is None:
            state = self.quad_state
        quat = state[kQuatW:kQuatZ + 1]
        quat = quat / np.linalg.norm(quat)
        return quat


class FlightmareSimulation(Simulation):
    # TODO: instead of using Python dynamics (as in PythonSimulation), use Flightmare dynamics
    #  => will have to write a different interface/wrapper for that (to e.g. get/set mass, thrust limits etc.)
    def __init__(self, config, trajectory_path, max_time=None):
        super().__init__(config)

        self.state_dim = 13  # TODO: change I guess
        self.action_dim = 4

        # Flightmare wrapper/bridge, in this class mostly to get images
        self.flightmare_wrapper = RacingEnvWrapper(wave_track=("wave" in trajectory_path))
        # self.flightmare_wrapper = RacingEnvWrapper(wave_track=False)
        self.current_image = np.zeros((self.flightmare_wrapper.image_width, self.flightmare_wrapper.image_height, 3),
                                      dtype=np.uint8)

        # sampler to get reference states for the network only (not for the MPC expert)
        self.reference_sampler = TrajectorySampler(trajectory_path, max_time=max_time)
        self.current_reference = np.zeros((self.state_dim,), dtype=np.float64)

        self.total_time = self.reference_sampler.get_final_time_stamp()

        # quadrotor/dynamics stuff
        self.current_state = self.reference_sampler.get_initial_state()
        self.flightmare_wrapper.set_reduced_state(self.current_state)
        self.flightmare_wrapper.set_sim_time_step(self.base_time_step)

    ################
    # RESET METHOD #
    ################

    def _reset(self):
        self.total_time = self.reference_sampler.get_final_time_stamp()

        # self.current_state = state[:10]
        # self.current_state = self.reference_sampler.get_initial_state()
        self.current_state = self.reference_sampler.get_initial_state(columns=["pos", "rot", "vel", "omega"])
        self.flightmare_wrapper.set_reduced_state(self.current_state)

    #####################################
    # TAKING CARE OF FLIGHTMARE WRAPPER # (not sure if$ overkill, but it's kinda neat)
    #####################################

    def connect_unity(self, pub_port=10253, sub_port=10254):
        self.flightmare_wrapper.connect_unity(pub_port, sub_port)

    def disconnect_unity(self):
        self.flightmare_wrapper.disconnect_unity()

    ##################
    # GETTER METHODS #
    ##################

    def _get_state(self, action=None):
        success = False
        if action is not None:
            success = self.flightmare_wrapper.step(action)
        self.current_state = self.flightmare_wrapper.get_state()
        return self.current_state, success

    def _get_state_estimate(self):
        self.current_state_estimate = self.current_state
        return self.current_state_estimate

    def _get_image(self):
        if self.image_time <= self.base_time:
            self.image_time += self.image_time_step
            self.current_image = self.flightmare_wrapper.get_image()
            self.image_updated = True
        return self.current_image

    def _get_reference(self):
        if self.ref_time <= self.base_time:
            self.ref_time += self.ref_time_step
            self.current_reference = self.reference_sampler.sample_from_trajectory(
                self.base_time, columns=["pos", "rot", "vel", "omega"])
            self.reference_updated = True
        return self.current_reference


class TestSimulation:
    # TODO: maybe test with this yield stuff? just a fancy way of doing it though
    def __init__(self):
        self.action_queue = deque(maxlen=1)

    def step(self):
        while True:
            test = self.action_queue.pop()
            yield test


if __name__ == "__main__":
    path = "/home/simon/Downloads/trajectory_s016_r05_flat_li01.csv"
    simulation = PythonSimulation(path)
    simulation.total_time = 2.0

    trajectory_done = False
    act = np.zeros((4,), dtype=np.float32)
    while not trajectory_done:
        res = simulation.step(act)
        trajectory_done = res["done"]
        print("base: {:.3f} - image: {:.3f} - ref: {:.3f} - command: {:.3f} - expert command: {:.3f} (update = {})".format(
            simulation.base_time, simulation.image_time, simulation.ref_time,
            simulation.command_time, simulation.expert_command_time, res["update"]))
