import os
import cv2
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from dda.simulation import FlightmareSimulation
from dda.learning import ControllerLearning
from dda.config.settings import create_settings

from run_tests import ensure_quaternion_consistency, visualise_actions, visualise_states


def show_state_action_plots(trajectory_path, states, actions, network_actions, time_step, time_total, save_path=None):
    trajectory = pd.read_csv(trajectory_path)
    trajectory = trajectory[trajectory["time-since-start [s]"] <= time_total]
    trajectory = ensure_quaternion_consistency(trajectory)
    trajectory = trajectory[[
        "position_x [m]",
        "position_y [m]",
        "position_z [m]",
        "rotation_w [quaternion]",
        "rotation_x [quaternion]",
        "rotation_y [quaternion]",
        "rotation_z [quaternion]",
        "velocity_x [m/s]",
        "velocity_y [m/s]",
        "velocity_z [m/s]",
        "time-since-start [s]",
    ]].values

    visualise_states(states, trajectory, time_total, time_step, True, False if save_path is None else True)
    if save_path is not None:
        plt.savefig(os.path.join(save_path, "states.png"))
        plt.close()

    visualise_actions(actions, time_total, time_step, True, False if save_path is None else True,
                      comparison_actions=network_actions, comparison_label="(network)")
    if save_path is not None:
        plt.savefig(os.path.join(save_path, "actions.png"))
        plt.close()


def save_trajectory_data(time_stamps, mpc_actions, network_actions, states,
                         network_used, max_time, switch_time, repetition, save_path):
    data = {
        "time-since-start [s]": time_stamps,
        "throttle_mpc": mpc_actions[:, 0],
        "roll_mpc": mpc_actions[:, 1],
        "pitch_mpc": mpc_actions[:, 2],
        "yaw_mpc": mpc_actions[:, 3],
        "throttle_nw": network_actions[:, 0],
        "roll_nw": network_actions[:, 1],
        "pitch_nw": network_actions[:, 2],
        "yaw_nw": network_actions[:, 3],
        "position_x [m]": states[:, 0],
        "position_y [m]": states[:, 1],
        "position_z [m]": states[:, 2],
        "rotation_w [quaternion]": states[:, 3],
        "rotation_x [quaternion]": states[:, 4],
        "rotation_y [quaternion]": states[:, 5],
        "rotation_z [quaternion]": states[:, 6],
        "velocity_x [m]": states[:, 7],
        "velocity_y [m]": states[:, 8],
        "velocity_z [m]": states[:, 9],
        "omega_x [rad/s]": states[:, 10],
        "omega_y [rad/s]": states[:, 11],
        "omega_z [rad/s]": states[:, 12],
        "network_used": np.array(network_used).astype(int)
    }
    data = pd.DataFrame(data)
    data.to_csv(os.path.join(save_path, "trajectory_mpc2nw_mt-{:02d}_st-{:02d}_{:02d}.csv"
                             .format(int(max_time * 10), int(switch_time * 10), repetition)), index=False)


def test():
    # paths
    trajectories = [
        "/home/simon/Downloads/trajectory_s016_r05_flat_li01.csv",  # medium (median)
        "/home/simon/Downloads/trajectory_mpc_20_s016_r05_flat_li01.csv",  # medium (median) MPC
        "/home/simon/Downloads/trajectory_s016_r05_flat_li01_buffer10.csv",  # medium (median) w/ "buffer"
        "/home/simon/Downloads/trajectory_s024_r08_flat_li09.csv",  # fast
        "/home/simon/Downloads/trajectory_s018_r09_wave_li04.csv",  # medium wave
        "/home/simon/Downloads/trajectory_s020_r13_wave_li04.csv",  # fast wave
    ]
    trajectory_path = trajectories[2]
    model_load_path = os.path.join(os.getenv("FLIGHTMARE_PATH"),
                                   "flightil/dda/results/loop/20210211-002220/train/ckpt-156")

    # defining some settings
    show_plots = True
    save_data = False
    write_video = False
    max_time = 7.0
    switch_times = np.arange(0.0, 5.0, step=0.5).tolist() + [max_time + 1.0]
    switch_times = [max_time + 1.0]
    repetitions = 1
    experiment_path = "/home/simon/Desktop/weekly_meeting/meeting18/dda_0"

    # creating settings
    settings = create_settings("./dda/config/dagger_settings.yaml", mode="dagger")
    settings.resume_training = True
    settings.resume_ckpt_file = model_load_path

    # using "learner" as controller
    controller = ControllerLearning(settings, trajectory_path, mode="testing", max_time=max_time)

    # creating simulation
    simulation = FlightmareSimulation(settings, trajectory_path, max_time=max_time)

    # TODO: add loop for testing multiple start times here
    switch_time = 0.0
    for switch_time in switch_times:
        for repetition in range(repetitions if switch_time < max_time else 1):
            # video writer
            writer = None
            if write_video:
                writer = cv2.VideoWriter(
                    "/home/simon/Desktop/flightmare_cam_test/test_network_eval_tf.mp4",
                    cv2.VideoWriter_fourcc("m", "p", "4", "v"),
                    simulation.image_time_step,
                    (simulation.flightmare_wrapper.image_width, simulation.flightmare_wrapper.image_height),
                    True,
                )

            # data to record
            states = []
            reduced_states = []
            mpc_actions = []
            network_actions = []
            network_used = []
            time_stamps = []

            # whether to use the network instead of the MPC
            use_network = False

            # resetting everything
            trajectory_done = False
            info_dict = simulation.reset()
            controller.reset()
            controller.use_network = use_network
            controller.record_data = False
            controller.update_info(info_dict)
            controller.prepare_expert_command()
            action = controller.get_control_command()

            # TODO: try also setting the acceleration and body rates from the reference when resetting,
            #  maybe this helps with the unwanted MPC behaviour at the start?

            # connect to the simulation either at the start or after training has been run
            simulation.connect_unity(settings.flightmare_pub_port, settings.flightmare_sub_port)

            # run the main loop until the simulation "signals" that the trajectory is done
            while not trajectory_done:
                if info_dict["time"] > switch_time:
                    use_network = True
                    controller.use_network = use_network

                # record states first
                time_stamps.append(info_dict["time"])
                states.append(info_dict["state"])
                reduced_states.append(info_dict["state"][:10])

                # write to video
                if write_video:
                    writer.write(info_dict["image"])

                # record actions after the decision has been made for the current state
                # TODO: actually, the ordering is kind of off here...
                mpc_actions.append(action["expert"])  # action["expert_action"]
                network_actions.append(action["network"])  # action["network_action"]
                network_used.append(action["use_network"])  # action["network_used"]

                info_dict, successes = simulation.step(action["network"] if action["use_network"] else action["expert"])
                trajectory_done = info_dict["done"]
                if not trajectory_done:
                    controller.update_info(info_dict)
                    action = controller.get_control_command()

            if write_video:
                writer.release()

            states = np.vstack(states)
            reduced_states = np.vstack(reduced_states)
            mpc_actions = np.vstack(mpc_actions)
            network_actions = np.vstack(network_actions)

            if show_plots:
                show_state_action_plots(trajectory_path, reduced_states, mpc_actions, network_actions,
                                        simulation.command_time_step, simulation.total_time)
            if save_data:
                save_trajectory_data(time_stamps, mpc_actions, network_actions, states, network_used, max_time,
                                     switch_time, repetition, experiment_path)


if __name__ == "__main__":
    test()
    # TODO: add CLI argument stuff instead of hard-coding
