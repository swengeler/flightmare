# should take the planning time horizon and step size and the trajectory file path
# and then return interpolated states for x steps into the future (maybe even make this flexible)
# => this will all be purely time-based, should maybe be able
#    to find point on trajectory closest to current state as well?
# would also be nice to have some functionality that e.g. repeats the end state to fill up states when
# the end of the trajectory has been reached <=> similarly, what should be done for the start state (assuming
# we don't always want to start at the same position)
# => maybe for now assume that position is the same and e.g. only rotation is different?
# => in that case, might also be a good idea to start before the first gate in our trajectories (?)
# => for the very start, should probably just reset the quadrotor to the very start of the trajectory...

import numpy as np
import pandas as pd


def row_to_state(row):
    # TODO: potentially still do transformation here
    state = np.array([
        row["position_x [m]"],
        row["position_y [m]"],
        row["position_z [m]"] + 0.75,
        row["rotation_w [quaternion]"],
        row["rotation_x [quaternion]"],
        row["rotation_y [quaternion]"],
        row["rotation_z [quaternion]"],
        row["velocity_x [m/s]"],
        row["velocity_y [m/s]"],
        row["velocity_z [m/s]"],
    ], dtype=np.float32)

    return state


class TrajectorySampler:

    def __init__(self, trajectory_path):
        self._trajectory = pd.read_csv(trajectory_path)
        self._ensure_quaternion_consistency()
        self._final_time_stamp = self._trajectory["time-since-start [s]"].max()
        # TODO: maybe implement other ways of sampling from the trajectory, e.g. using the position as well

    def get_final_time_stamp(self):
        return self._final_time_stamp

    def get_initial_state(self):
        return row_to_state(self._trajectory.iloc[0])

    def get_final_state(self):
        return row_to_state(self._trajectory.iloc[-1])

    def sample_from_trajectory(self, time_stamp, interpolation="nearest_below"):
        # TODO: implement some sort of interpolation
        row_idx = self._trajectory["time-since-start [s]"] <= time_stamp
        if all(~row_idx):
            index = 0
        else:
            index = self._trajectory.loc[row_idx, "time-since-start [s]"].idxmax()
        return row_to_state(self._trajectory.iloc[index])

    def _ensure_quaternion_consistency(self):
        flipped = 0
        self._trajectory["flipped"] = 0
        self._trajectory.loc[0, "flipped"] = flipped

        quat_columns = ["rotation_{} [quaternion]".format(c) for c in ["w", "x", "y", "z"]]
        prev_quaternion = self._trajectory.loc[0, quat_columns]
        prev_signs_positive = prev_quaternion >= 0

        for i in range(1, len(self._trajectory.index)):
            current_quaternion = self._trajectory.loc[i, quat_columns]
            current_signs_positive = current_quaternion >= 0
            condition_sign = prev_signs_positive == ~current_signs_positive

            if np.sum(condition_sign) >= 3:
                flipped = 1 - flipped
            self._trajectory.loc[i, "flipped"] = flipped

            prev_signs_positive = current_signs_positive

        self._trajectory.loc[self._trajectory["flipped"] == 1, quat_columns] *= -1.0


class TrajectoryPlanner:

    def __init__(self, trajectory_path, plan_time_horizon=2.0, plan_time_step=0.1):
        self._trajectory_sampler = TrajectorySampler(trajectory_path)

        self._plan_time_horizon = plan_time_horizon
        self._plan_time_step = plan_time_step
        self._num_plan_steps = int(self._plan_time_horizon / self._plan_time_step)

    def plan(self, current_state, current_time):
        latest_non_hover_state = current_state.tolist()
        planned_trajectory = list(current_state)
        for step in range(self._num_plan_steps + 1):
            time = current_time + step * self._plan_time_step

            if time <= self.get_final_time_stamp():
                state = self._trajectory_sampler.sample_from_trajectory(current_time + step * self._plan_time_step).tolist()
                planned_trajectory += state
                latest_non_hover_state = state
            else:
                # hover
                # TODO: probably some kind of interpolation between the last "proper" state and a hover state
                planned_trajectory += latest_non_hover_state[:2] + [3.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        planned_trajectory = np.array(planned_trajectory)

        return planned_trajectory

    def get_final_time_stamp(self):
        return self._trajectory_sampler.get_final_time_stamp()

    def get_initial_state(self):
        return self._trajectory_sampler.get_initial_state()

    def get_final_state(self):
        return self._trajectory_sampler.get_final_state()


class HoverPlanner:

    def __init__(self, plan_time_horizon=2.0, plan_time_step=0.1):
        self._plan_time_horizon = plan_time_horizon
        self._plan_time_step = plan_time_step
        self._num_plan_steps = int(self._plan_time_horizon / self._plan_time_step)

        self._goal_position = np.array([3.0, 0.0, 3.0])

    def plan(self, current_state, current_time):
        planned_trajectory = list(current_state)
        current_position = current_state[:3]
        diff_position = self._goal_position - current_position
        for step in range(self._num_plan_steps + 1):
            # planned_trajectory += planned_trajectory[:3] + [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            incremental_position = current_position + (self._plan_time_step * (step + 1) / self._plan_time_horizon) * diff_position
            planned_trajectory += incremental_position.tolist() + [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            # planned_trajectory += current_position[:2].tolist() + [2.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        planned_trajectory = np.array(planned_trajectory)

        return planned_trajectory


class RisePlanner:

    def __init__(self, plan_time_horizon=2.0, plan_time_step=0.1):
        self._plan_time_horizon = plan_time_horizon
        self._plan_time_step = plan_time_step
        self._num_plan_steps = int(self._plan_time_horizon / self._plan_time_step)

        self._increment = np.array([0.1, 0.0, 0.1])

    def plan(self, current_state, current_time):
        planned_trajectory = list(current_state)
        current_position = current_state[:3]
        for step in range(self._num_plan_steps + 1):
            # planned_trajectory += planned_trajectory[:3] + [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            incremental_position = current_position + (self._increment * (step + 1))
            planned_trajectory += incremental_position.tolist() + [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            # planned_trajectory += current_position[:2].tolist() + [2.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        planned_trajectory = np.array(planned_trajectory)

        return planned_trajectory

    def get_initial_state(self):
        return np.array([0.0, 0.0, 2.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])

