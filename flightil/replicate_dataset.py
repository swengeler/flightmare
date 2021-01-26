import os
import re
import numpy as np
import pandas as pd
import cv2
import time

from typing import Type
from tqdm import tqdm

from mpc.simulation.mpc_test_env import MPCTestEnv
from mpc.simulation.mpc_test_wrapper import MPCTestWrapper
from mpc.mpc.mpc_solver import MPCSolver
from mpc.simulation.planner import TrajectoryPlanner
from run_tests import sample_from_trajectory


def iterate_directories(data_root, track_names=None):
    if track_names is None:
        track_names = ["flat"]

    directories = []
    if re.search(r"/\d\d_", data_root):
        directories.append(data_root)
    elif re.search(r"/s0\d\d", data_root):
        for run in sorted(os.listdir(data_root)):
            run_dir = os.path.join(data_root, run)
            if os.path.isdir(run_dir) and run[3:] in track_names:
                directories.append(run_dir)
    else:
        for subject in sorted(os.listdir(data_root)):
            subject_dir = os.path.join(data_root, subject)
            if os.path.isdir(subject_dir) and subject.startswith("s"):
                for run in sorted(os.listdir(subject_dir)):
                    run_dir = os.path.join(subject_dir, run)
                    if os.path.isdir(run_dir) and run[3:] in track_names:
                        directories.append(run_dir)

    return directories


def parse_run_info(run_dir):
    if run_dir[-1] == "/":
        run_dir = run_dir[:-1]

    # return the subject number, run number and track name
    result = re.search(r"/s0\d\d", run_dir)
    subject_number = None if result is None else int(result[0][2:])

    result = re.search(r"/s0\d\d/\d\d_", run_dir)
    run_number = None if result is None else int(result[0][6:8])

    result = re.search(r"/s0\d\d/\d\d_.+", run_dir)
    track_name = None if result is None else result[0][9:]

    info = {
        "subject": subject_number,
        "run": run_number,
        "track_name": track_name
    }

    return info


def run_info_to_path(subject, run, track_name):
    return os.path.join("s{:03d}".format(subject), "{:02d}_{}".format(run, track_name))


def pair(arg):
    # custom argparse type
    if ":" in arg:
        arg_split = arg.split(":")
        property_name = arg_split[0]
        property_value = arg_split[1]

        try:
            property_value = int(arg_split[1])
        except ValueError:
            try:
                property_value = float(arg_split[1])
            except ValueError:
                pass
    else:
        property_name = arg
        property_value = 1

    return property_name, property_value


class DatasetReplicator:

    def __init__(self, config):
        self.run_dir_list = iterate_directories(config["data_root"], track_names=config["track_name"])
        if config["directory_index"] is not None:
            self.run_dir_list = self.run_dir_list[int(config["directory_index"][0]):config["directory_index"][1]]

        for r_idx, r in enumerate(self.run_dir_list):
            print(r_idx, ":", r)
        # exit()

    def compute_new_data(self, run_dir):
        raise NotImplementedError()

    def finish(self):
        raise NotImplementedError()

    def generate(self):
        for rd in tqdm(self.run_dir_list[:15], disable=True):
            self.compute_new_data(rd)
        self.finish()


class FlightmareReplicator(DatasetReplicator):

    COLUMN_DICT = {
        "ts": "time-since-start [s]",
        "PositionX": "position_x [m]",
        "PositionY": "position_y [m]",
        "PositionZ": "position_z [m]",
        "VelocityX": "velocity_x [m/s]",
        "VelocityY": "velocity_y [m/s]",
        "VelocityZ": "velocity_z [m/s]",
        "AccX": "acceleration_x [m/s/s]",
        "AccY": "acceleration_y [m/s/s]",
        "AccZ": "acceleration_z [m/s/s]",
        "rot_w_quat": "rotation_w [quaternion]",
        "rot_x_quat": "rotation_x [quaternion]",
        "rot_y_quat": "rotation_y [quaternion]",
        "rot_z_quat": "rotation_z [quaternion]",
    }

    def __init__(self, config):
        super().__init__(config)
        self.skip_existing = config["skip_existing"]
        self.trajectory_only = config["trajectory_only"]
        self.fps = config["frames_per_second"]

        assert 60 % self.fps == 0, "Original FPS (60) should be divisible by new FPS ({}).".format(self.fps)

        self.frame_skip = int(60 / self.fps)

        self.wave_track = config["track_name"] == "wave"
        self.env = MPCTestWrapper(wave_track=self.wave_track)
        self.env.connect_unity(pub_port=config["pub_port"], sub_port=config["sub_port"])

    def finish(self):
        self.env.disconnect_unity()

    def compute_new_data(self, run_dir):
        start = time.time()

        # check that the thingy is working
        video_capture = cv2.VideoCapture(os.path.join(run_dir, "screen.mp4"))
        w, h = video_capture.get(3), video_capture.get(4)
        if not (w == 800 and h == 600):
            print("WARNING: Screen video does not have the correct dimensions for directory '{}'.".format(run_dir))
            return

        print("Processing '{}'.".format(run_dir))

        # get info about the current run
        run_info = parse_run_info(run_dir)
        subject = run_info["subject"]
        run = run_info["run"]
        
        # load the correct drone.csv and laptimes.csv
        inpath_drone = os.path.join(run_dir, "drone.csv")
        inpath_ts = os.path.join(run_dir, "screen_timestamps.csv")

        df_ts = pd.read_csv(inpath_ts)
        df_traj = pd.read_csv(inpath_drone)
    
        # select columns and use new column headers
        df_traj = df_traj[[co for co in FlightmareReplicator.COLUMN_DICT]]
        df_traj = df_traj.rename(FlightmareReplicator.COLUMN_DICT, axis=1)
        
        # save the adjusted trajectory (including setting start to 0? probably not)
        # df_traj["time-since-start [s]"] = df_traj["time-since-start [s]"] - df_traj["time-since-start [s]"].min()
        df_traj.to_csv(os.path.join(run_dir, "trajectory.csv"), index=False)

        if self.trajectory_only:
            return

        # use this (not time-adjusted) trajectory to generate data
        video_writer = cv2.VideoWriter(
            os.path.join(run_dir, "flightmare_{}.mp4".format(self.fps)),
            cv2.VideoWriter_fourcc("m", "p", "4", "v"),
            float(self.fps),
            (800, 600),
            True
        )

        # if there are screen timestamps < the first drone timestamp, should just "wait" in the first position
        for i in tqdm(range(0, len(df_ts.index), self.frame_skip), disable=False):
            time_current = df_ts["ts"].iloc[i]
            sample = sample_from_trajectory(df_traj, time_current)
            image = self.env.step(sample)
            video_writer.write(image)

        """
        for _, row in tqdm(df_ts.iterrows(), total=len(df_ts.index)):
            time_current = row["ts"]
            sample = sample_from_trajectory(df_traj, time_current)
            image = self.env.step(sample)
            video_writer.write(image)
        """
    
        video_writer.release()

        print("Processed '{}'. in {:.2f}s".format(run_dir, time.time() - start))

        time.sleep(0.1)


class MPCReplicator_v0(DatasetReplicator):

    # TODO: use the new simulation interface for DDA once its properly done (I think?)
    #  => only "problem" with that might be that images might e.g. not be returned at the correct rate
    #  => could e.g. implement a mode where images/states are queued until a new command has to be returned

    def __init__(self, config):
        super().__init__(config)
        self.skip_existing = config["skip_existing"]
        self.trajectory_only = config["trajectory_only"]
        self.disconnect = config["unity_disconnect"]
        self.fps = config["frames_per_second"]
        assert 60 % self.fps == 0, "Original FPS (60) should be divisible by new FPS ({}).".format(self.fps)
        self.frame_skip = int(60 / self.fps)

        self.base_frequency = 60
        self.command_frequency = 20

        # TODO: probably use integer stuff here
        self.base_time_step = 1.0 / self.base_frequency
        self.image_time_step = 1.0 / self.fps
        self.command_time_step = 1.0 / self.command_frequency

        self.plan_time_step = 0.1
        self.plan_time_horizon = 3.0

        self.mpc_solver = MPCSolver(self.plan_time_horizon, self.plan_time_step)
        self.wave_track = config["track_name"] == "wave"
        self.fm_wrapper = MPCTestWrapper(wave_track=self.wave_track)
        self.pub_port = config["pub_port"]
        self.sub_port = config["sub_port"]
        if not self.disconnect:
            self.fm_wrapper.connect_unity(self.pub_port, self.sub_port)

    def finish(self):
        self.fm_wrapper.disconnect_unity()

    def compute_new_data(self, run_dir):
        from run_tests import ensure_quaternion_consistency, visualise_actions, visualise_states

        start = time.time()

        # check that the thingy is working
        video_capture = cv2.VideoCapture(os.path.join(run_dir, "screen.mp4"))
        w, h = video_capture.get(3), video_capture.get(4)
        if not (w == 800 and h == 600):
            print("WARNING: Screen video does not have the correct dimensions for directory '{}'.".format(run_dir))
            return

        print("\nProcessing '{}'.".format(run_dir))

        # load the correct trajectory
        inpath_traj = os.path.join(run_dir, "trajectory.csv")
        df_traj = pd.read_csv(inpath_traj)
        df_traj["time-since-start [s]"] = df_traj["time-since-start [s]"] - df_traj["time-since-start [s]"].min()

        """
        test = df_traj[["rotation_w [quaternion]", "rotation_x [quaternion]",
                        "rotation_y [quaternion]", "rotation_z [quaternion]"]] ** 2
        # test = df_traj["rotation_w [quaternion]"] + df_traj["rotation_x [quaternion]"] + df_traj["rotation_y [quaternion]"] + df_traj["rotation_z [quaternion]"]
        test = test.sum(axis=1)
        test = np.sqrt(test)
        print(all(test.between(0.999999, 1.000001)))
        exit()
        """

        # planner
        print("Ensuring quaternion consistency in planner...")
        planner = TrajectoryPlanner(inpath_traj, self.plan_time_horizon, self.plan_time_step)

        # simulation parameters (after planner to get max time)
        simulation_time_step = self.base_time_step
        simulation_time_horizon = total_time = planner.get_final_time_stamp()

        # environment
        env = MPCTestEnv(self.mpc_solver, planner, simulation_time_horizon, simulation_time_step)
        env.reset()
        if self.disconnect:
            self.fm_wrapper.connect_unity(pub_port=self.pub_port, sub_port=self.sub_port)

        # use this (not time-adjusted) trajectory to generate data
        video_writer = cv2.VideoWriter(
            os.path.join(run_dir, "flightmare_mpc_{}_{}.mp4".format(self.fps, self.command_frequency)),
            cv2.VideoWriter_fourcc("m", "p", "4", "v"),
            float(self.fps),
            (self.fm_wrapper.image_width, self.fm_wrapper.image_height),
            True
        )

        # "reset" counters
        base_time = 0.0
        image_time = 0.0
        command_time = 0.0
        frame_counter = 0

        # data to record
        time_stamps = []
        frames = []
        frames_original = []
        states = []
        actions = []

        prev_state, state, action, image = None, None, None, None

        total_time = 3.0

        print("Running main loop...")
        progress_bar = tqdm(total=int(total_time / self.base_time_step))
        while base_time <= total_time:
            time_stamps.append(base_time)
            frames.append(frame_counter)
            frames_original.append(frame_counter * self.frame_skip)

            if command_time <= base_time:
                command_time += self.command_time_step
                prev_state, state, action = env.step(return_previous_state=True)
            else:
                prev_state, state, _ = env.step(action, return_previous_state=True)

            if image_time <= base_time:
                image_time += self.image_time_step
                image = self.fm_wrapper.step(state)
                video_writer.write(image)
                frame_counter += 1  # this is actually not really going to work is it? all the associated states etc. will not "belong" to these frames
                # does it actually make sense to just add stuff to the fpv_saliency_maps code do deal with exclusively
                # this new data?

            base_time += self.base_time_step

            actions.append(action)
            states.append(prev_state)

            progress_bar.update()

        states = np.vstack(states)
        actions = np.vstack(actions)

        data = {
            "time-since-start [s]": time_stamps,
            "frame": frames,
            "frame_original": frames_original,
            "thrust": actions[:, 0],
            "roll": actions[:, 1],
            "pitch": actions[:, 2],
            "yaw": actions[:, 3],
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
        }
        data = pd.DataFrame(data)
        data.to_csv(os.path.join(run_dir, "trajectory_mpc_{}_{}.csv".format(self.fps, self.command_frequency)), index=False)

        # TODO: also need timestamps
        #  => should there also be frame numbers? wouldn't hurt I guess; also the original frame numbers?
        #  => what about the original timestamps in screen_timestamps.csv
        #  => also, what about the original timestamps? aren't those mostly used for "synchronising" between
        #     the frame timestamps and the control/state w/e

        video_writer.release()

        # TODO: should probably write control GT to one big file or something like that, so that it can
        #  easily be used with the existing training framework... THIS IS IMPORTANT FOR TRAINING!
        #  (see generate_ground_truth.py)

        print("Processed '{}'. in {:.2f}s".format(run_dir, time.time() - start))

        if self.disconnect:
            self.fm_wrapper.disconnect_unity()
            # TODO: maybe implement disconnect message type that
            #  immediately "releases" the unity server (when specified)

        # problem with this is that unity has a very long timeout during which it will still try to listen
        # to new messages (I think)

        # time.sleep(0.1)

        # exit()

        """
        # trajectory = pd.read_csv(trajectory_path)
        # trajectory = trajectory[trajectory["time-since-start [s]"] <= simulation_time_horizon]
        trajectory = df_traj
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

        visualise_states(states, trajectory, simulation_time_horizon, self.base_time_step, True, False)
        # plt.savefig("/home/simon/Desktop/weekly_meeting/meeting14/cam_angle_test_mpc_wave_fast_rot_states.png")
        # plt.close()
        visualise_actions(actions, simulation_time_horizon, self.base_time_step, True, False)
        # plt.savefig("/home/simon/Desktop/weekly_meeting/meeting14/cam_angle_test_mpc_wave_fast_rot_actions.png")
        # plt.close()

        exit()
        """


def resolve_gt_class(new_data_type: str) -> Type[DatasetReplicator]:
    if new_data_type == "copy_original":
        return FlightmareReplicator
    elif new_data_type == "mpc":
        print("DOING MPC THING")
        return MPCReplicator_v0
    return DatasetReplicator


def main(args):
    config = vars(args)

    generator = resolve_gt_class(config["new_data_type"])(config)
    generator.generate()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()

    # general arguments
    parser.add_argument("-r", "--data_root", type=str, default=os.getenv("GAZESIM_ROOT"),
                        help="The root directory of the dataset (should contain only subfolders for each subject).")
    parser.add_argument("-tn", "--track_name", type=str, default="flat", choices=["flat", "wave"],
                        help="The track name (relevant for which simulation).")
    parser.add_argument("-ndt", "--new_data_type", type=str, default="copy_original", choices=["copy_original", "mpc"],
                        help="The method to use to compute the ground-truth.")
    parser.add_argument("-fps", "--frames_per_second", type=int, default=60,
                        help="FPS to use when replicating the data.")
    parser.add_argument("-pp", "--pub_port", type=int, default=10253)
    parser.add_argument("-sp", "--sub_port", type=int, default=10254)
    parser.add_argument("-udc", "--unity_disconnect", action="store_true")
    parser.add_argument("-di", "--directory_index", type=pair, default=None)
    parser.add_argument("-se", "--skip_existing", action="store_true")  # TODO?
    parser.add_argument("-to", "--trajectory_only", action="store_true")

    # parse the arguments
    arguments = parser.parse_args()

    # generate the GT
    main(arguments)

