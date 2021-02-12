try:
    from analysis.functions.preprocessing_utils import *
    from analysis.functions.processing_utils import *
    from analysis.functions.Animation3D import *
    from analysis.functions.Gate import *
    from analysis.functions.laptracker_utils import *
except:
    from functions.preprocessing_utils import *
    from functions.processing_utils import *
    from functions.Animation3D import *
    from functions.Gate import *
    from functions.laptracker_utils import *

def getWallColliders(dims=(1, 1, 1), center=(0, 0, 0)):
    '''getting 3d volume wall collider objects
    dims: x, y, z dimensions in meters
    denter: x, y, z positions of the 3d volume center'''
    objWallCollider = []

    _q = (Rotation.from_euler('y', [np.pi/2]) * Rotation.from_quat(np.array([0, 0, 0, 1]))).as_quat().flatten()
    objWallCollider.append(Gate(pd.DataFrame({'pos_x': center[0], 'pos_y': center[1], 'pos_z' : center[2] - dims[2] / 2,
                                            'rot_x_quat': _q[0], 'rot_y_quat':_q[1], 'rot_z_quat':_q[2], 'rot_w_quat':_q[3],
                                            'dim_x':0, 'dim_y': dims[1], 'dim_z':dims[0]}, index=[0]).iloc[0],
                                dims=(dims[1], dims[0]), dtype='gazesim'))

    _q = (Rotation.from_euler('y', [-np.pi/2]) * Rotation.from_quat(np.array([0, 0, 0, 1]))).as_quat().flatten()
    objWallCollider.append(Gate(pd.DataFrame({'pos_x': center[0], 'pos_y': center[1], 'pos_z' : center[2] + dims[2] / 2,
                                            'rot_x_quat': _q[0], 'rot_y_quat':_q[1], 'rot_z_quat':_q[2], 'rot_w_quat':_q[3],
                                            'dim_x':0, 'dim_y':dims[1], 'dim_z':dims[0]}, index=[0]).iloc[0],
                                dims=(dims[1], dims[0]), dtype='gazesim'))

    _q = np.array([0, 0, 0, 1])
    objWallCollider.append(Gate(pd.DataFrame({'pos_x': center[0] + dims[0] / 2, 'pos_y': center[1], 'pos_z' : center[2],
                                            'rot_x_quat': _q[0], 'rot_y_quat':_q[1], 'rot_z_quat':_q[2], 'rot_w_quat':_q[3],
                                            'dim_x':0, 'dim_y':dims[1], 'dim_z':dims[2]}, index=[0]).iloc[0],
                                dims=(dims[1], dims[2]), dtype='gazesim'))

    _q = (Rotation.from_euler('z', [np.pi]) * Rotation.from_quat(np.array([0, 0, 0, 1]))).as_quat().flatten()
    objWallCollider.append(Gate(pd.DataFrame({'pos_x': center[0] - dims[0] / 2, 'pos_y': center[1], 'pos_z' : center[2],
                                            'rot_x_quat': _q[0], 'rot_y_quat':_q[1], 'rot_z_quat':_q[2], 'rot_w_quat':_q[3],
                                            'dim_x':0, 'dim_y':dims[1], 'dim_z':dims[2]}, index=[0]).iloc[0],
                                dims=(dims[1], dims[2]), dtype='gazesim'))

    _q = (Rotation.from_euler('z', [np.pi/2]) * Rotation.from_quat(np.array([0, 0, 0, 1]))).as_quat().flatten()
    objWallCollider.append(Gate(pd.DataFrame({'pos_x': center[0], 'pos_y': center[1] + dims[1] / 2, 'pos_z' : center[2],
                                            'rot_x_quat': _q[0], 'rot_y_quat':_q[1], 'rot_z_quat':_q[2], 'rot_w_quat':_q[3],
                                            'dim_x':0, 'dim_y':dims[1], 'dim_z':dims[2]}, index=[0]).iloc[0],
                                dims=(dims[0], dims[2]), dtype='gazesim'))

    _q = (Rotation.from_euler('z', [-np.pi/2]) * Rotation.from_quat(np.array([0, 0, 0, 1]))).as_quat().flatten()
    objWallCollider.append(Gate(pd.DataFrame({'pos_x': center[0], 'pos_y': center[1] - dims[1] / 2, 'pos_z' : center[2],
                                            'rot_x_quat': _q[0], 'rot_y_quat':_q[1], 'rot_z_quat':_q[2], 'rot_w_quat':_q[3],
                                            'dim_x':0, 'dim_y':dims[1], 'dim_z':dims[2]}, index=[0]).iloc[0],
                                dims=(dims[0], dims[2]), dtype='gazesim'))
    return objWallCollider

#todo: fix 2d point extraction for Gate class
#todo: update laptracker and Gate scripts in Liftoff plugin
#todo: fix gate passing event detection for gates

def extractFeaturesSaveAnimation(PATH, toShowAnimation=False, toSaveAnimation=False):
    print(PATH)
    print('')
    step_size = 4
    #read drone state logs
    d = pd.read_csv(PATH)
    #read gate poses for the current track
    t = pd.read_csv('./tracks/flat.csv')
    #make gate passing surfaces
    objGatePass = [Gate(t.iloc[i], dtype='gazesim') for i in range(t.shape[0])]
    #make gate collision surfaces
    objGateCollider = [Gate(t.iloc[i], dtype='gazesim', dims=(3.5, 3.5)) for i in range(t.shape[0])]
    #make wall collision surfaces
    objWallCollider = getWallColliders(dims=(66, 36, 9), center=(0, 0, 4.5))
    #get drone state variables for event detection
    _t = d.loc[:, 'time-since-start [s]'].values
    _p = d.loc[:,('position_x [m]', 'position_y [m]', 'position_z [m]')].values
    #gate passing event
    evGatePass = [(i, detect_gate_passing(_t, _p, objGatePass[i], step_size=step_size)) for i in range(len(objGatePass))]
    evGatePass = [(i, v) for i, v in evGatePass if v.shape[0] > 0]
    print('gate passes:')
    print(evGatePass)
    print('')
    #gate collision event (discard the ones that are valid gate passes
    evGateCollision = []
    _tmp = [(i, detect_gate_passing(_t, _p, objGateCollider[i], step_size=step_size)) for i in range(len(objGateCollider))]
    _tmp = [(i, v) for i, v in _tmp if v.shape[0] > 0]
    for key, values in _tmp:
        new_vals = []
        for _k, _v in evGatePass:
            if _k == key:
                for value in values:
                    if value not in _v:
                        new_vals.append(_v)
        if len(new_vals) > 0:
            evGateCollision.append((key, np.array(new_vals)))
    print('gate collisions:')
    print(evGateCollision)
    print('')
    #wall collision events
    evWallCollision = [(i, detect_gate_passing(_t, _p, objWallCollider[i], step_size=step_size)) for i in range(len(objWallCollider))]
    evWallCollision = [(i, v) for i, v in evWallCollision if v.shape[0] > 0]
    print('wall collisions:')
    print(evWallCollision)
    print('')
    #save timestamps
    e = pd.DataFrame([])
    for i, v in evGatePass:
        for _v in v:
            e = e.append(pd.DataFrame({'time-since-start [s]' : _v, 'object-id' : i, 'object-name' : 'gate', 'is-collision' : 0, 'is-pass' : 1}, index = [0]))
    for i, v in evGateCollision:
        for _v in v:
            e = e.append(pd.DataFrame({'time-since-start [s]' : _v, 'object-id' : i, 'object-name' : 'gate', 'is-collision' : 1, 'is-pass' : 0}, index = [0]))
    for i, v in evWallCollision:
        for _v in v:
            e = e.append(pd.DataFrame({'time-since-start [s]' : _v, 'object-id' : i, 'object-name' : 'wall', 'is-collision' : 1, 'is-pass' : 0}, index = [0]))
    e = e.sort_values(by=['time-since-start [s]'])
    #make output folder
    outpath = '/process/'.join((PATH.split('.csv')[0] + '/').split('/logs/'))
    if os.path.exists(outpath) == False:
        make_path(outpath)
    #copy trajectory data
    copyfile(PATH, outpath + 'trajectory.csv')
    #save the events
    e.to_csv(outpath + 'events.csv', index=False)
    #compute performance metrics
    tStart = e['time-since-start [s]'].iloc[0]
    ec = e.loc[(e['is-collision'].values == 1), :]
    if ec.shape[0] > 0:
        tFirstCollision = ec['time-since-start [s]'].iloc[0]
        hasCollision = 1
        ind = e['time-since-start [s]'].values < tFirstCollision
        en = e.copy().iloc[ind, :]
    else:
        hasCollision = 0
        tFirstCollision = np.nan
        en = e.copy()
    if np.isnan(tFirstCollision):
        tEnd = np.nanmax(d['time-since-start [s]'].values)
    else:
        tEnd = tFirstCollision
    flightTime = tEnd - tStart
    numGatePasses = np.sum(en['is-pass'])
    ind = en['is-pass'].values == 1
    idGatePasses = [en.loc[ind, 'object-id'].values]
    tsGatePasses = [en.loc[ind, 'time-since-start [s]'].values]
    ind = (_t >= tStart) & (_t <= tEnd)
    flightDistance = np.nansum(np.linalg.norm(np.diff(_p[ind, :], axis=0), axis=1))
    #collect performance metrics in pandas dataframe
    p = pd.DataFrame({'time-start [s]': tStart, 'time-end [s]': tEnd, 'flight-time [s]' : flightTime, 'flight-distance [m]' : flightDistance,
                      'num-gate-passes' : numGatePasses, 'gate-id': idGatePasses, 'gate-ts': tsGatePasses, 'has-collision' : hasCollision, 'filepath' : outpath}, index=[0])
    #save performance metrics
    p.to_csv(outpath + 'performance.csv', index=False)
    #save the animation
    if toSaveAnimation or toShowAnimation:
        print('..saving animation')
        gate_objects = objGatePass + objGateCollider + objWallCollider
        d['simulation-time-since-start [s]'] = d['time-since-start [s]'].values
        anim = Animation3D(d, Gate_objects=gate_objects, equal_lims=(-30, 30))
        if toSaveAnimation:
            if os.path.isfile(outpath + 'anim.mp4') == False:
                anim.save(outpath + 'anim.mp4', writer='ffmpeg', fps=25)
        if toShowAnimation:
            anim.show()

PATH = './logs/'
MODELS = ['dda_offline_0', 'resnet_test'] #['dda_offline_0', 'resnet_test']

toExtractFeatures = True
toSaveAnimation = False
toShowAnimation = False
toPlotFeatures = False

if toExtractFeatures:
    for m in MODELS:
        for w in os.walk(PATH):
            if w[0].find(m) != -1:
                for f in w[2]:
                    if f.find('.csv') != -1:
                        extractFeaturesSaveAnimation(PATH=os.path.join(w[0], f), toShowAnimation=toShowAnimation, toSaveAnimation=toSaveAnimation)

if toPlotFeatures:
    for m in MODELS:
        if m == 'dda_offline_0':
            switchTimes = [5, 10, 15, 20, 25, 30, 35, 40, 45]
        else:
            switchTimes = [6, 8, 10, 12, 14]
        for s in switchTimes:
            if m == 'dda_offline_0':
                stem = '{}/trajectory_mpc2nw_st-{}_if-60_cf-20_'.format(m, '%02d' % s)
            else:
                stem = '{}/trajectory_mpc2nw_switch-{}_'.format(m, '%02d' % s)
            #get file paths for different model-switchtime combinations
            filepaths = []
            for w in os.walk('./process/'):
                # print(w[0])
                if w[0].find(stem) != -1:
                    filepaths.append(w[0] + '/')
            #load and plot trajectories
            fig, axs = plt.subplots(1,1)
            axs = [axs]
            iax = 0
            for f in filepaths:
                d = pd.read_csv(f + 'trajectory.csv')
                p = pd.read_csv(f + 'performance.csv')
                t0 = p['time-start [s]'].iloc[0]
                ts = s/10
                t1 = p['time-end [s]'].iloc[0]
                print(t0, ts, t1, f)
                for _t0, _t1, _c in [(t0, ts, 'b'), (ts, t1, 'r')]:
                    ind = (d['time-since-start [s]'].values >= _t0) & (d['time-since-start [s]'].values <= _t1)
                    px = d.loc[ind, 'position_x [m]'].values
                    py = d.loc[ind, 'position_y [m]'].values
                    axs[iax].plot(px, py, _c)
            axs[iax].set_title('model {}, switchtime {} sec\n gate passes {}, has collision {}'.format(m, ts,
                                                                                                        p['num-gate-passes'].iloc[0], p['has-collision'].iloc[0]))
            axs[iax].set_xlim((-35, 35))
            axs[iax].set_ylim((-35, 35))
            plt.show()