import numpy as np

from old.mpc.simulation.quadrotor import QuadRotor


class MPCTestEnv(object):

    def __init__(self, mpc_solver, planner, simulation_time_horizon=5.0, simulation_time_step=0.02):
        self.mpc_solver = mpc_solver
        self.planner = planner

        # simulation parameters
        self.simulation_time_horizon = simulation_time_horizon
        self.simulation_time_step = simulation_time_step
        # self.max_episode_steps = int(self.simulation_time_horizon / self.simulation_time_step)

        # quadrotor simulator
        self.quad_rotor = QuadRotor(simulation_time_step=self.simulation_time_step)
        self.quad_state = self.quad_rotor.get_state()

        # TODO: add unity wrapper => might actually want to have this outside this simulation...
        self.flightmare_wrapper = None

        # reset the environment
        self.current_time = 0
        self.reset()

    def seed(self, seed):
        np.random.seed(seed=seed)

    def reset(self):
        self.current_time = 0

        # state for ODE
        # self.quad_state = self.quad_rotor.reset()
        self.quad_rotor.set_state(self.planner.get_initial_state())
        self.quad_state = self.quad_rotor.get_state()
        # TODO: also set the state in the unity environment

        return self.quad_state

    def step(self, action=None, return_previous_state=False):
        self.current_time += self.simulation_time_step
        previous_state = self.quad_rotor.get_state()

        optimal_action = action
        if optimal_action is None:
            planned_traj = self.planner.plan(self.quad_rotor.get_state(), self.current_time)
            planned_traj = np.array(planned_traj)

            # print("\n", self.t, ":")
            # print("\n{} (quad_state = {}):".format(self.current_time, self.quad_state))
            # print(planned_traj.shape)

            # might still want something like the reference trajectory below, particularly the goal state?
            # quad_state_current = self.quad_state.tolist()
            # reference_traj = quad_state_current + planned_traj + self.quad_state_final

            # seems like at every step the MPC optimises over the entire trajectory again? but with different
            # initial states? that doesn't really make sense to me at all...
            # => maybe it just optimises from the current state towards the final state, and it might
            #    just optimise to stay at the final state if the planning horizon exceeds reaching the final state

            # run non-linear model predictive control
            optimal_action, predicted_traj, cost = self.mpc_solver.solve(planned_traj)

            """
            previous_state = planned_traj[:3]
            planned_state = planned_traj[10:13]
            predicted_state = predicted_traj[0, :3]
            predicted_action = predicted_traj[0:3, -4:]

            print("\ncost:", cost)
            print("previous:", previous_state)
            print("planned:", planned_state)
            print("predicted:", predicted_state)
            """

        optimal_action = optimal_action.squeeze()

        # optimal_action = np.array([15.0, 0.0, 0.0, 0.0])

        # run the actual control command on the quadrotor
        self.quad_state = self.quad_rotor.run(optimal_action)
        self.quad_state = self.quad_rotor.get_state()

        # print("action:", optimal_action.squeeze())
        # print("action[0] >= 9.81:", optimal_action.squeeze()[0] >= 9.81)
        # print("predicted action:", predicted_action)

        if return_previous_state:
            return previous_state, self.quad_state, optimal_action

        return self.quad_state, optimal_action
