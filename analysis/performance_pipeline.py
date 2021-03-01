import os
import sys

# Add base path
base_path = os.getcwd().split('/flightmare/')[0]+'/flightmare/'
sys.path.insert(0, base_path)

from analysis.utils import *

# What to do
to_process = False
to_performance = False
to_table = True

to_plot_traj_3d = False
to_plot_state = False
to_plot_reference = False

# Buffer time: time runs with  network were started earlier than the reference
# trajectory
buffer = 2.0

# Chose input files and folders for processing.
track_filepaths = {
    'flat': './tracks/flat.csv',
    'wave': './tracks/wave.csv',
    }
logfile_path = './logs/'
reference_filepath = logfile_path+'reference/trajectory_reference_original.csv'
models = [
    # 'dda_flat_med_full_bf2_cf25_decfts',
        ]
if len(models) == 0:
    for w in os.walk(logfile_path):
        if w[0] == logfile_path:
            models = w[1]
models = sorted(models)


# Process individual runs
if to_process:

    for model in models:

        # Make a list of input logfiles of network trajectories.
        log_filepaths = []
        for w in os.walk(os.path.join(logfile_path, model)):
            for f in w[2]:
                if (f.find('.csv') > 0) and (reference_filepath.find(f) < 0):
                    log_filepaths.append(os.path.join(w[0], f))

        # Process individual trajectories flown by the network.
        for filepath in sorted(log_filepaths):
            print('..processing {}'.format(filepath))
            # Make output folder
            data_path = (filepath
                         .replace('.csv', '/')
                         .replace('/logs/', '/process/')
                         .replace('trajectory_', '')
                         )
            make_path(data_path)
            # Copy trajectory, reference, and track files to output folder
            if not os.path.isfile(data_path + 'trajectory.csv'):
                trajectory = trajectory_from_logfile(filepath=filepath)
                # Important: compensate for buffer time (i.e. earlier start
                # of the network, before start of the reference trajectory)
                trajectory['t'] -= buffer
                trajectory.to_csv(data_path + 'trajectory.csv',
                                  index=False)
            if not os.path.isfile(data_path + 'reference.csv'):
                reference = trajectory_from_logfile(filepath=reference_filepath)
                reference.to_csv(data_path + 'reference.csv',
                                  index=False)
            if not os.path.isfile(data_path + 'track.csv'):
                if filepath.find('wave') > -1:
                    track_filepath = track_filepaths['wave']
                else:
                    track_filepath = track_filepaths['flat']

                track = track_from_logfile(filepath=track_filepath)
                # Make some adjustments
                track['pz'] += 0.35 # shift gates up in fligthmare
                track['dx'] = 0.
                track['dy'] = 3 # in the middle of inner diameter 2.5 and outer 3.0
                track['dz'] = 3 # in the middle of inner diameter 2.5 and outer 3.0
                track.to_csv(data_path + 'track.csv',
                             index=False)
            # Save gate pass and collision events to output folder
            if not os.path.isfile(data_path + 'events.csv'):
                E = get_pass_collision_events(
                    filepath_trajectory=data_path+'trajectory.csv',
                    filepath_track=data_path+'track.csv')
                E.to_csv(data_path + 'events.csv', index=False)
            # Save performance features to output folder
            if not os.path.isfile(data_path + 'features.csv'):
                P = extract_performance_features(
                    filepath_trajectory=data_path + 'trajectory.csv',
                    filepath_reference=data_path + 'reference.csv',
                    filepath_events=data_path + 'events.csv')
                P.to_csv(data_path + 'features.csv', index=False)
            # Save trajectory plot to output folder
            if to_plot_traj_3d:
                track = pd.read_csv(data_path + 'track.csv')
                trajectory = pd.read_csv(data_path + 'trajectory.csv')
                features = pd.read_csv(data_path + 'features.csv')
                for label in ['', 'valid_']:
                    for view, xlims, ylims, zlims in [
                                 [(45, 270), (-15, 19), (-17, 17), (-8, 8)],
                                 # [(0, 270), (-15, 19), (-17, 17), (-12, 12)],
                                 # [(0, 180), (-15, 19), (-17, 17), (-12, 12)],
                                 # [(90, 270), (-15, 19), (-15, 15), (-12, 12)],
                            ]:
                        outpath = (data_path + '{}trajectory_with_gates_'
                                               '{}x{}.jpg'
                                   .format(label,
                                           '%03d' % view[0],
                                           '%03d' % view[1])
                                   )
                        if not os.path.isfile(outpath):
                            if label == 'valid_':
                                ind = ((trajectory['t'].values >=
                                       features['t_start'].iloc[0]) &
                                       (trajectory['t'].values <=
                                        features['t_end'].iloc[0]))
                            else:
                                ind = np.array([True for i in range(
                                    trajectory.shape[0])])
                            ax = plot_trajectory_with_gates_3d(
                                trajectory=trajectory.iloc[ind, :],
                                track=track,
                                view=view,
                                xlims=xlims,
                                ylims=ylims,
                                zlims=zlims,
                            )

                            ax.set_title(outpath)
                            plt.savefig(outpath)
                            plt.close(plt.gcf())
                            ax=None
            # Plot the drone state
            if to_plot_state:
                if not os.path.isfile(data_path + 'state.jpg'):
                    plot_state(
                        filepath_trajectory=data_path + 'trajectory.csv',
                        filepath_reference=data_path + 'reference.csv',
                        filepath_features=data_path + 'features.csv',
                        )
                    plt.savefig(data_path + 'state.jpg')
                    plt.close(plt.gcf())


# Collect performance metrics across runs
if to_performance:
    outpath = './performance/'
    outfilepath = outpath + 'performance.csv'
    if not os.path.exists(outpath):
        make_path(outpath)
    performance = pd.DataFrame([])
    for model in models:
        filepaths = []
        for w in os.walk('./process/'+model+'/'):
            for f in w[2]:
                if f=='features.csv':
                    filepaths.append(os.path.join(w[0], f))
        for filepath in filepaths:
            print('..collecting performance: {}'.format(filepath))

            df =  pd.read_csv(filepath)

            # Get model and run information from filepath
            strings = (
                df['filepath'].iloc[0]
                    .split('/process/')[-1]
                    .split('/trajectory.csv')[0]
                    .split('/')
            )
            if len(strings) == 2:
                strings.insert(1, 's016_r05_flat_li01_buffer20')

            # Load the yaml file
            yamlpath = None
            config = None
            yamlcount = 0
            for w in os.walk('./logs/'+model+'/'):
                for f in w[2]:
                    if f.find('.yaml')>-1:
                        yamlpath = os.path.join(w[0], f)
                        yamlcount += 1
            if yamlpath is not None:
                with open(yamlpath, 'r') as stream:
                    try:
                        config = yaml.safe_load(stream)
                    except yaml.YAMLError as exc:
                        print(exc)
                        config = None

            # print(yamlcount, yamlpath)

            ddict = {}
            ddict['model_name'] = strings[0]
            ddict['has_dda'] = int(strings[0].find('dda') > -1)

            if config is not None:

                ddict['has_yaml'] = 1

                ddict['has_ref'] = 1
                if 'no_ref' in config['train']:
                    ddict['has_ref'] = int(config['train']['no_ref'] == False)


                ddict['has_state_q'] = 0
                ddict['has_state_v'] = 0
                ddict['has_state_w'] = 0
                if 'use_imu' in config['train']:
                    if config['train']['use_imu'] == True:
                        ddict['has_state_q'] = 1
                        ddict['has_state_v'] = 1
                        ddict['has_state_w'] = 1
                        if 'imu_no_rot' in config['train']:
                            if config['train']['imu_no_rot'] == True:
                                ddict['has_state_q'] = 0
                        if 'imu_no_vels' in config['train']:
                            if config['train']['imu_no_vels'] == True:
                                ddict['has_state_v'] = 0
                                ddict['has_state_w'] = 0

                ddict['has_fts'] = 0
                if 'use_fts_tracks' in config['train']:
                    if config['train']['use_fts_tracks']:
                        ddict['has_fts'] = 1



                ddict['has_decfts'] = 0
                ddict['has_gztr'] = 0
                if 'attention_fts_type' in config['train']:
                    if config['train']['attention_fts_type'] == 'decoder_fts':
                        ddict['has_decfts'] = 1
                        ddict['has_gztr'] = 0
                    elif config['train']['attention_fts_type'] == 'gaze_tracks':
                        ddict['has_decfts'] = 0
                        ddict['has_gztr'] = 1


                ddict['has_attbr'] = 0
                if 'attention_branching' in config['train']:
                    if config['train']['attention_branching'] == True:
                        ddict['has_attbr'] = 1


                ddict['buffer'] = 0
                if 'start_buffer' in config['simulation']:
                    ddict['buffer'] = config['simulation']['start_buffer']

            # If no yaml file was found
            else:
                ddict['has_yaml'] = 0

            ddict['buffer'] = float(strings[1].split('buffer')[-1]) / 10
            ddict['subject'] = int(strings[1].split('_')[0].split('s')[-1])
            ddict['run'] = int(strings[1].split('_')[1].split('r')[-1])
            ddict['track'] = strings[1].split('_')[2]

            li_string = strings[1].split('_')[3].split('li')[-1]
            if li_string.find('-')>-1:
                ddict['li'] = int(li_string.split('-')[0])
                ddict['num_laps'] = (int(li_string.split('-')[-1]) -
                                     int(li_string.split('-')[0]) + 1)
            else:
                ddict['li'] = int(li_string)
                ddict['num_laps'] = 1

            if ddict['has_dda'] == 0:
                if strings[2] == 'reference_mpc':
                    ddict['mt'] = -1
                    ddict['st'] = 0
                    ddict['repetition'] = 0
                else:
                    ddict['mt'] = -1
                    ddict['st'] = int(strings[2].split('_')[1].split('switch-')[-1])
                    ddict['repetition'] = int(strings[2].split('_')[-1])
            else:
                if strings[0].find('dda_offline')>-1:
                    ddict['mt'] = -1
                    ddict['st'] = int(strings[2].split('_')[1].split('st-')[-1])
                    ddict['repetition'] = int(strings[2].split('_')[-1])
                elif strings[2].find('mpc_eval_nw')>-1:
                    ddict['mt'] = -1
                    ddict['st'] = -1
                    ddict['repetition'] = 0
                else:
                    ddict['mt'] = int(strings[2].split('_')[1].split('mt-')[-1])
                    ddict['st'] = int(strings[2].split('_')[2].split('st-')[-1])
                    ddict['repetition'] = int(strings[2].split('_')[-1])

            for k in sorted(ddict):
                df[k] = ddict[k]

            performance = performance.append(df)
    performance.to_csv(outfilepath, index=False)


# Make output table
if to_table:

    performance = pd.read_csv('./performance/performance.csv')

    for attention_name in ['decfts', 'attbr']:
        for trajectory_name in ['reference', 'other-laps', 'other-track']:

            print('----------------')
            print(trajectory_name, attention_name)
            print('----------------')
            # Subject dictionnairy
            run_dict = None
            exclude_run_dict = None
            if trajectory_name == 'reference':
                run_dict = {
                'track': 'flat',
                'subject': 16,
                'run': 5,
                'li': 1,
                'num_laps': 1,
                }
            elif trajectory_name == 'other-laps':
                run_dict = {
                    'track': 'flat',
                    'num_laps': 1,
                }
                exclude_run_dict = {
                    'track': 'flat',
                    'subject': 16,
                    'run': 5,
                    'li': 1,
                    'num_laps': 1,
                }
            elif trajectory_name == 'other-track':
                run_dict = {
                    'track': 'wave',
                    'num_laps': 1,
                }

            # Model dictionnairy
            model_dicts = None
            if attention_name == 'decfts':
                model_dicts = [
                {
                    'name': 'Ref + QVW + Fts + Att',
                    'specs': {
                        'has_dda': 1,
                        'has_attbr': 0,
                        'has_gztr': 0,
                        'has_decfts': 1,
                        'has_fts': 1,
                        'has_state_q': 1,
                        'has_state_v': 1,
                        'has_state_w': 1,
                        'has_ref': 1,
                    },
                },{
                    'name': 'Ref + QVW + Att',
                    'specs': {
                        'has_dda': 1,
                        'has_attbr': 0,
                        'has_gztr': 0,
                        'has_decfts': 1,
                        'has_fts': 0,
                        'has_state_q': 1,
                        'has_state_v': 1,
                        'has_state_w': 1,
                        'has_ref': 1,
                    },
                },{
                    'name': 'Ref + QVW + Fts',
                    'specs': {
                        'has_dda': 1,
                        'has_attbr': 0,
                        'has_gztr': 0,
                        'has_decfts': 0,
                        'has_fts': 1,
                        'has_state_q': 1,
                        'has_state_v': 1,
                        'has_state_w': 1,
                        'has_ref': 1,
                    },
                },{
                    'name': 'Ref + QVW',
                    'specs': {
                        'has_dda': 1,
                        'has_attbr': 0,
                        'has_gztr': 0,
                        'has_decfts': 0,
                        'has_fts': 0,
                        'has_state_q': 1,
                        'has_state_v': 1,
                        'has_state_w': 1,
                        'has_ref': 1,
                    },
                },{
                    'name': 'Ref + VW',
                    'specs': {
                        'has_dda': 1,
                        'has_attbr': 0,
                        'has_gztr': 0,
                        'has_decfts': 0,
                        'has_fts': 0,
                        'has_state_q': 0,
                        'has_state_v': 1,
                        'has_state_w': 1,
                        'has_ref': 1,
                    },
                },{
                    'name': 'Ref + Q + Fts + Att',
                    'specs': {
                        'has_dda': 1,
                        'has_attbr': 0,
                        'has_gztr': 0,
                        'has_decfts': 1,
                        'has_fts': 1,
                        'has_state_q': 1,
                        'has_state_v': 0,
                        'has_state_w': 0,
                        'has_ref': 1,
                    },
                },{
                    'name': 'Ref + Q + Att',
                    'specs': {
                        'has_dda': 1,
                        'has_attbr': 0,
                        'has_gztr': 0,
                        'has_decfts': 1,
                        'has_fts': 0,
                        'has_state_q': 1,
                        'has_state_v': 0,
                        'has_state_w': 0,
                        'has_ref': 1,
                    },
                },{
                    'name': 'Ref + Q + Fts',
                    'specs': {
                        'has_dda': 1,
                        'has_attbr': 0,
                        'has_gztr': 0,
                        'has_decfts': 0,
                        'has_fts': 1,
                        'has_state_q': 1,
                        'has_state_v': 0,
                        'has_state_w': 0,
                        'has_ref': 1,
                    },
                },{
                    'name': 'Ref + Q',
                    'specs': {
                        'has_dda': 1,
                        'has_attbr': 0,
                        'has_gztr': 0,
                        'has_decfts': 0,
                        'has_fts': 0,
                        'has_state_q': 1,
                        'has_state_v': 0,
                        'has_state_w': 0,
                        'has_ref': 1,
                    },
                },{
                    'name': 'Ref + Fts + Att',
                    'specs': {
                        'has_dda': 1,
                        'has_attbr': 0,
                        'has_gztr': 0,
                        'has_decfts': 1,
                        'has_fts': 1,
                        'has_state_q': 0,
                        'has_state_v': 0,
                        'has_state_w': 0,
                        'has_ref': 1,
                    },
                },{
                    'name': 'Ref + Att',
                    'specs': {
                        'has_dda': 1,
                        'has_attbr': 0,
                        'has_gztr': 0,
                        'has_decfts': 1,
                        'has_fts': 0,
                        'has_state_q': 0,
                        'has_state_v': 0,
                        'has_state_w': 0,
                        'has_ref': 1,
                    },
                },{
                    'name': 'Ref + Fts',
                    'specs': {
                        'has_dda': 1,
                        'has_attbr': 0,
                        'has_gztr': 0,
                        'has_decfts': 0,
                        'has_fts': 1,
                        'has_state_q': 0,
                        'has_state_v': 0,
                        'has_state_w': 0,
                        'has_ref': 1,
                    },
                },{
                    'name': 'Ref',
                    'specs': {
                        'has_dda': 1,
                        'has_attbr': 0,
                        'has_gztr': 0,
                        'has_decfts': 0,
                        'has_fts': 0,
                        'has_state_q': 0,
                        'has_state_v': 0,
                        'has_state_w': 0,
                        'has_ref': 1,
                    }
                },
            ]
            elif attention_name == 'attbr':
                model_dicts = [
                {
                    'name': 'Ref + QVW + Fts + Att',
                    'specs': {
                        'has_dda': 1,
                        'has_attbr': 1,
                        'has_gztr': 0,
                        'has_decfts': 0,
                        'has_fts': 1,
                        'has_state_q': 1,
                        'has_state_v': 1,
                        'has_state_w': 1,
                        'has_ref': 1,
                    },
                },{
                    'name': 'Ref + QVW + Att',
                    'specs': {
                        'has_dda': 1,
                        'has_attbr': 1,
                        'has_gztr': 0,
                        'has_decfts': 0,
                        'has_fts': 0,
                        'has_state_q': 1,
                        'has_state_v': 1,
                        'has_state_w': 1,
                        'has_ref': 1,
                    },
                },{
                    'name': 'Ref + QVW + Fts',
                    'specs': {
                        'has_dda': 1,
                        'has_attbr': 0,
                        'has_gztr': 0,
                        'has_decfts': 0,
                        'has_fts': 1,
                        'has_state_q': 1,
                        'has_state_v': 1,
                        'has_state_w': 1,
                        'has_ref': 1,
                    },
                },{
                    'name': 'Ref + QVW',
                    'specs': {
                        'has_dda': 1,
                        'has_attbr': 0,
                        'has_gztr': 0,
                        'has_decfts': 0,
                        'has_fts': 0,
                        'has_state_q': 1,
                        'has_state_v': 1,
                        'has_state_w': 1,
                        'has_ref': 1,
                    },
                },{
                    'name': 'Ref + VW',
                    'specs': {
                        'has_dda': 1,
                        'has_attbr': 0,
                        'has_gztr': 0,
                        'has_decfts': 0,
                        'has_fts': 0,
                        'has_state_q': 0,
                        'has_state_v': 1,
                        'has_state_w': 1,
                        'has_ref': 1,
                    },
                },{
                    'name': 'Ref + Q + Fts + Att',
                    'specs': {
                        'has_dda': 1,
                        'has_attbr': 1,
                        'has_gztr': 0,
                        'has_decfts': 0,
                        'has_fts': 1,
                        'has_state_q': 1,
                        'has_state_v': 0,
                        'has_state_w': 0,
                        'has_ref': 1,
                    },
                },{
                    'name': 'Ref + Q + Att',
                    'specs': {
                        'has_dda': 1,
                        'has_attbr': 1,
                        'has_gztr': 0,
                        'has_decfts': 0,
                        'has_fts': 0,
                        'has_state_q': 1,
                        'has_state_v': 0,
                        'has_state_w': 0,
                        'has_ref': 1,
                    },
                },{
                    'name': 'Ref + Q + Fts',
                    'specs': {
                        'has_dda': 1,
                        'has_attbr': 0,
                        'has_gztr': 0,
                        'has_decfts': 0,
                        'has_fts': 1,
                        'has_state_q': 1,
                        'has_state_v': 0,
                        'has_state_w': 0,
                        'has_ref': 1,
                    },
                },{
                    'name': 'Ref + Q',
                    'specs': {
                        'has_dda': 1,
                        'has_attbr': 0,
                        'has_gztr': 0,
                        'has_decfts': 0,
                        'has_fts': 0,
                        'has_state_q': 1,
                        'has_state_v': 0,
                        'has_state_w': 0,
                        'has_ref': 1,
                    },
                },{
                    'name': 'Ref + Fts + Att',
                    'specs': {
                        'has_dda': 1,
                        'has_attbr': 1,
                        'has_gztr': 0,
                        'has_decfts': 0,
                        'has_fts': 1,
                        'has_state_q': 0,
                        'has_state_v': 0,
                        'has_state_w': 0,
                        'has_ref': 1,
                    },
                },{
                    'name': 'Ref + Att',
                    'specs': {
                        'has_dda': 1,
                        'has_attbr': 1,
                        'has_gztr': 0,
                        'has_decfts': 0,
                        'has_fts': 0,
                        'has_state_q': 0,
                        'has_state_v': 0,
                        'has_state_w': 0,
                        'has_ref': 1,
                    },
                },{
                    'name': 'Ref + Fts',
                    'specs': {
                        'has_dda': 1,
                        'has_attbr': 0,
                        'has_gztr': 0,
                        'has_decfts': 0,
                        'has_fts': 1,
                        'has_state_q': 0,
                        'has_state_v': 0,
                        'has_state_w': 0,
                        'has_ref': 1,
                    },
                },{
                    'name': 'Ref',
                    'specs': {
                        'has_dda': 1,
                        'has_attbr': 0,
                        'has_gztr': 0,
                        'has_decfts': 0,
                        'has_fts': 0,
                        'has_state_q': 0,
                        'has_state_v': 0,
                        'has_state_w': 0,
                        'has_ref': 1,
                    }
                },
            ]


            # Feature dictionnairy
            feature_dict={
                'Flight Time [s]': {
                    'varname': 'flight_time',
                    'track': '',
                    'first_line': 'mean',
                    'second_line': 'std',
                    'precision': 2
                    },
                'Travel Distance [m]': {
                    'varname': 'travel_distance',
                    'track': '',
                    'first_line': 'mean',
                    'second_line': 'std',
                    'precision': 2
                },
                'Mean Error [m]': {
                    'varname': 'median_path_deviation',
                    'track': '',
                    'first_line': 'mean',
                    'second_line': 'std',
                    'precision': 2
                },
                'Gates Passed': {
                    'varname': 'num_gates_passed',
                    'track': '',
                    'first_line': 'mean',
                    'second_line': 'std',
                    'precision': 2
                },
                '% Collision': {
                    'varname': 'num_collisions',
                    'track': '',
                    'first_line': 'percent',
                    'second_line': '',
                    'precision': 0
                },
            }

            # Make a table
            if (run_dict is not None) and (model_dicts is not None):
                table = pd.DataFrame([])
                for mdict in model_dicts:

                    #add subject dictionnairy to the model dictionnairy
                    mdict['specs'] = {**mdict['specs'], **run_dict}

                    ddict = {}
                    ddict['Model'] = [mdict['name'], '']

                    # Select performance data
                    # Runs to include
                    ind = np.array([True for i in range(performance.shape[0])])
                    for k, v in mdict['specs'].items():
                        ind = ind & (performance[k] == v)
                    # Runs to exclude
                    if exclude_run_dict is not None:
                        ind_exclude = np.array([True for i in range(
                            performance.shape[0])])
                        for k, v in exclude_run_dict.items():
                            ind_exclude = ind_exclude & (performance[k] == v)
                        # Combine run selection
                        ind = (ind == True) & (ind_exclude == False)
                    # Select current runs
                    curr_performance = performance.copy().loc[ind, :]

                    ddict['Num Runs'] = [str(curr_performance.shape[0]), '']

                    print(mdict['name'], ':', curr_performance.shape[0])
                    # print(curr_performance)

                    if curr_performance.shape[0] > 0:
                        # Compute Average performances
                        for outvar in feature_dict:
                            ddict.setdefault(outvar, [])
                            invar = feature_dict[outvar]['varname']
                            curr_vals = curr_performance[invar].values
                            #first line value
                            op1 = feature_dict[outvar]['first_line']
                            if op1 == 'mean':
                                val1 = np.nanmean(curr_vals)
                            elif op1 == 'percent':
                                val1 = 100 * np.mean((curr_vals > 0).astype(int))
                            else:
                                val1 = None
                            if val1 is None:
                                ddict[outvar].append('')
                            else:
                                ddict[outvar].append(str(np.round(val1, feature_dict[outvar][
                                    'precision'])))
                            # second line value
                            op2 = feature_dict[outvar]['second_line']
                            if op2 == 'std':
                                val1 = np.nanstd(curr_vals)
                            else:
                                val1 = None
                            if val1 is None:
                                ddict[outvar].append('')
                            else:
                                ddict[outvar].append('('+str(np.round(val1, feature_dict[outvar][
                                    'precision']))+')')

                    for k in ddict:
                        ddict[k] = [' '.join(ddict[k])]

                    # Append two lines to the output table
                    table = table.append(
                        pd.DataFrame(ddict,
                                     index=list(range(len(ddict['Model']))))
                    )
                outpath = './performance/latex_table_{}_{}.csv'.format(
                    trajectory_name, attention_name)
                table.to_latex(outpath, index=False)




if to_plot_reference:
    # Load track.
    track = pd.read_csv(track_filepath)
    ndict = {
        'pos_x': 'px',
        'pos_y': 'py',
        'pos_z': 'pz',
        'rot_x_quat': 'qx',
        'rot_y_quat': 'qy',
        'rot_z_quat': 'qz',
        'rot_w_quat': 'qw',
        'dim_x': 'dx',
        'dim_y': 'dy',
        'dim_z': 'dz',
    }
    track = track.rename(columns=ndict)
    track = track[list(ndict.values())]
    track['pz'] += 0.35
    track['dx'] = 0.
    track['dy'] = 3
    track['dz'] = 3
    # Load reference and downsample to 20 Hz
    reference = trajectory_from_logfile(
        filepath=reference_filepath)
    sr = 1 / np.nanmedian(np.diff(reference.t.values))
    reference = reference.iloc[np.arange(0, reference.shape[0], int(sr / 20)), :]
    # Plot reference, track, and format figure.
    ax = plot_trajectory(
        reference.px.values,
        reference.py.values,
        reference.pz.values,
        reference.qx.values,
        reference.qy.values,
        reference.qz.values,
        reference.qw.values,
        axis_length=2,
        c='k',
    )
    ax = plot_gates_3d(
        track=track,
        ax=ax,
        color='k',
        width=4,
        )
    ax = format_trajectory_figure(
        ax=ax,
        xlims=(-15, 19),
        ylims=(-17, 17),
        zlims=(-8, 8),
        xlabel='px [m]',
        ylabel='py [m]',
        zlabel='pz [m]',
        title='',
        )

    plt.axis('off')
    plt.grid(b=None)
    ax.view_init(elev=45,
                 azim=270)
    plt.gcf().set_size_inches(20,10)

    plot_path = './plots/'
    if not os.path.exists(plot_path):
        make_path(plot_path)

    plt.savefig(plot_path + 'reference_3d.jpg')

    # # Plot flight path overlay of individual runs
    # for model in models:
    #   data_path = './process/' + model + '/'
    #   compare_trajectories_3d(
    #       reference_filepath=reference_filepath,
    #       data_path=data_path,
    #       )

    plt.show()