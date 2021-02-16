import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from mpl_toolkits.mplot3d.art3d import Line3D
from shapely.geometry import LineString
from scipy.spatial.transform import Rotation
from shutil import copyfile
from skspatial.objects import Vector, Points, Line, Point


class Gate(object):
    """
    Racing gate object, represented as 2D surface, with some useful methods
    for detecting intersections and 3D-2D projections.
    """

    def __init__(self, df, dims=None, dtype='gazesim'):
        #set variable names according to the type of data
        if dtype=='liftoff':
            position_varnames = ['position_x [m]', 'position_y [m]', 'position_z [m]']
            rotation_varnames = [ 'rotation_x [quaternion]', 'rotation_y [quaternion]', 'rotation_z [quaternion]',
                                  'rotation_w [quaternion]']
            dimension_varnames = ['checkpoint-size_y [m]', 'checkpoint-size_z [m]']
            dimension_scaling_factor = 1.
        else: #gazesim: default
            position_varnames = ['pos_x', 'pos_y', 'pos_z']
            rotation_varnames = ['rot_x_quat', 'rot_y_quat', 'rot_z_quat', 'rot_w_quat']
            dimension_varnames = ['dim_y', 'dim_z']
            dimension_scaling_factor = 2.5
        #current gate center position
        p = df[position_varnames].values.flatten()
        #current gate rotation quaterion
        q = df[rotation_varnames].values.flatten()
        #if no width and height dimensions were specified
        if dims is None:
            dims = (df[dimension_varnames[0]] * dimension_scaling_factor, df[dimension_varnames[1]] * dimension_scaling_factor)
        #half width and height of the gate
        hw = dims[0] / 2. #half width
        hh = dims[1] / 2. #half height
        #assuming gates are oriented in the direction of flight: x=forward, y=left, z=up
        proto = np.array([[ 0.,  0.,  0.,  0.,  0.],  # assume surface, thus no thickness along x axis
                          [ hw, -hw, -hw,  hw,  hw],
                          [ hh,  hh, -hh, -hh,  hh]])
        self._corners = (Rotation.from_quat(q).apply(proto.T).T + p.reshape(3, 1)).astype(float)
        self._center = p
        self._rotation = q
        #1D minmax values
        self._x = np.array([np.min(self._corners[0, :]), np.max(self._corners[0, :])])
        self._y = np.array([np.min(self._corners[1, :]), np.max(self._corners[1, :])])
        self._z = np.array([np.min(self._corners[2, :]), np.max(self._corners[2, :])])
        #2D line representations of gate horizontal axis
        self._xy = LineString([ ((np.min(self._corners[0, :])), np.min(self._corners[1, :])),
                                ((np.max(self._corners[0, :])), np.max(self._corners[1, :]))])
        self._xz = LineString([((np.min(self._corners[0, :])), np.min(self._corners[2, :])),
                               ((np.max(self._corners[0, :])), np.max(self._corners[2, :]))])
        self._yz = LineString([((np.min(self._corners[1, :])), np.min(self._corners[2, :])),
                               ((np.max(self._corners[1, :])), np.max(self._corners[2, :]))])

    @property
    def corners(self):
        return self._corners

    @property
    def center(self):
        return self._center

    @property
    def rotation(self):
        return self._rotation

    @property
    def x(self):
        return self._x

    @property
    def y(self):
        return self._y

    @property
    def z(self):
        return self._z

    @property
    def xy(self):
        return self._xy

    @property
    def xz(self):
        return self._xz

    @property
    def yz(self):
        return self._yz

    def intersect(self, p0: np.ndarray([]), p1: np.ndarray([])) -> tuple():
        """
        Returns 2D and 3D intersection points with the gate surface and a
        line from two given points (p0, p1).
        """
        # Initialize relevant variables
        point_2d = None
        point_3d = None
        _x = None
        _y = None
        _z = None
        count = 0
        #only proceed if no nan values
        if (np.sum(np.isnan(p0).astype(int))==0) & (np.sum(np.isnan(p1).astype(int))==0):
            #line between start end end points
            line_xy = LineString([(p0[0], p0[1]),
                                  (p1[0], p1[1])])
            line_xz = LineString([(p0[0], p0[2]),
                                  (p1[0], p1[2])])
            line_yz = LineString([(p0[1], p0[2]),
                                  (p1[1], p1[2])])
            if self.xy.intersects(line_xy):
                count += 1
                _x, _y = [val for val in self.xy.intersection(line_xy).coords][0]
            if self.xz.intersects(line_xz):
                count += 1
                _x, _z = [val for val in self.xz.intersection(line_xz).coords][0]
            if self.yz.intersects(line_yz):
                count += 1
                _y, _z = [val for val in self.yz.intersection(line_yz).coords][0]
            #at least two of the three orthogonal lines need to be crossed
            if count > 1:
                point_3d = np.array([_x, _y, _z])
                point_2d = self.point2d(point_3d)
        return point_2d, point_3d

    def point2d(self, p: np.ndarray([])) -> np.ndarray([]):
        """
        Returns normalized [0-1 range] 2D coordinates of the intersection
        point within gate surface.

        The origin is the upper left corner (1st corner point)
        X-axis is to the right
        Y-axis is down
        """
        # Represent x and y axis of the gate surface by line objects.
        x_axis = Line(point=self._corners[:, 0],
                      direction=self._corners[:, 1] - self._corners[:, 0])
        y_axis = Line(point=self._corners[:, 0],
                      direction=self._corners[:, 3] - self._corners[:, 0])
        length_x_axis = x_axis.direction.norm()
        length_y_axis = y_axis.direction.norm()
        # Project the 3D intersection point onto the x and y surface axies.
        px_projected = x_axis.project_point(p)
        py_projected = y_axis.project_point(p)
        length_px_projected = x_axis.point.distance_point(px_projected)
        length_py_projected = y_axis.point.distance_point(py_projected)
        # Return the normalized 2D projection of the intersection point.
        return np.array([length_px_projected / length_x_axis,
                         length_py_projected / length_y_axis])


# todo: update this function for px py pz inputs
#  make this a function of the liftoff module
def detect_gate_passing(
        t: np.ndarray([]), px: np.ndarray([]), py: np.ndarray([]),
        pz: np.ndarray([]), gate_object: Gate, max_step_size: int=20,
        distance_threshold: int=None) -> np.ndarray([]):

        # time: np.ndarray([]), position: np.ndarray([]), gate_object: Gate,
        # max_step_size: int = 20,
        # distance_threshold: int = None) -> np.ndarray([]):

        
    """Detect gate passing events
        Function update on 12.02.2021
        Checks if position data is within a distance threshold from the gate
        And for those data checks if the gate was passed"""
    # determine the distance threshold from the gate size
    if distance_threshold is None:
        v = gate_object.corners - gate_object.center.reshape(3, 1)
        distance_threshold = 1.5 * np.max(np.array([np.linalg.norm(v[:, i])
                                                    for i in
                                                    range(v.shape[1])]))
    dt = np.nanmedian(np.diff(time))
    # print('delta time is {} sec'.format(dt))
    p_gate = gate_object.center.reshape((1, 3)).astype(float)
    dist = np.linalg.norm(position - p_gate, axis=1)
    ts1 = time[dist < distance_threshold]
    ts2 = []

    for t_ in ts1:
        ind = time >= t_
        p_ = position[ind, :]
        selection = []
        for ss in np.arange(max_step_size):
            if p_.shape[0] > ss:
                # check for gate passing considering a certain sample-to-sample
                # step size
                _, p3d = gate_object.intersect(p_[0, :], p_[ss, :])
                if p3d is not None:
                    selection.append((t_, np.linalg.norm(p_[0, :] - p3d)))

        if len(selection) > 0:
            minDist = np.min(np.array([val for _, val in selection]))
            minTime = [__t for __t, __v in selection if __v == minDist][0]
            ts2.append(minTime)

        # if p_.shape[0] > step_size:
        #     #check for gate passing considering a certain sample-to-sample
        #     step size
        #     _, p3d = gate_object.intersect(p_[0, :], p_[step_size, :])
        #     if p3d is not None:
        #         ts2.append(t_)
    # remove duplicated timestamps, i.e. when within the stepsize window
    if len(ts2) > 0:
        ts2 = np.sort(np.array(ts2))
        ind = np.hstack((np.diff(ts2) >= (2 * dt), True))
        ts2 = ts2[ind]
    ts2 = np.array(ts2)
    return ts2


# todo: update this pipeline, remove the animation part, just save features
def performance_feature_extraction(PATH, toShowAnimation=False,
                                   toSaveAnimation=False):
    """Pipeline for computing and saving performance features for flight
    trajectories"""

    print('------------------------')
    print(PATH)
    print('')
    # find switchtime
    filename = PATH.split('/')[-1]
    tSwitch = None
    for s in ['_st-', '_switch-']:
        if filename.find(s) != -1:
            tSwitch = int(filename.split(s)[-1].split('_')[0]) / 10
    # read drone state logs
    d = pd.read_csv(PATH)
    d = d.sort_values(by=['time-since-start [s]'])
    # read gate poses for the current track
    t = pd.read_csv('./tracks/flat.csv')
    # add zoffset to gate positions in flightmare
    zOffset = 0.35
    t['pos_z'] += zOffset
    # make gate passing surfaces
    objGatePass = [Gate(t.iloc[i], dtype='gazesim', dims=(2.5, 2.5)) for i
                   in range(t.shape[0])]
    # make gate collision surfaces
    objGateCollider = [Gate(t.iloc[i], dtype='gazesim', dims=(3.5, 3.5)) for
                       i in range(t.shape[0])]
    # make wall collision surfaces
    objWallCollider = wall_colliders(dims=(66, 36, 9),
                                       center=(0, 0, 4.5 + zOffset))
    # get drone state variables for event detection
    _t = d.loc[:, 'time-since-start [s]'].values
    _p = d.loc[:,
         ('position_x [m]', 'position_y [m]', 'position_z [m]')].values
    # gate passing event
    evGatePass = [(i, detect_gate_passing(_t, _p, objGatePass[i])) for i in
                  range(len(objGatePass))]
    evGatePass = [(i, v) for i, v in evGatePass if v.shape[0] > 0]
    print('gate passes:')
    print(evGatePass)
    print('')
    # gate collision event (discard the ones that are valid gate passes
    evGateCollision = []
    _tmp = [(i, detect_gate_passing(_t, _p, objGateCollider[i])) for i in
            range(len(objGateCollider))]
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
    # wall collision events
    evWallCollision = [(i, detect_gate_passing(_t, _p, objWallCollider[i]))
                       for i in range(len(objWallCollider))]
    evWallCollision = [(i, v) for i, v in evWallCollision if v.shape[0] > 0]
    print('wall collisions:')
    print(evWallCollision)
    print('')
    # save timestamps
    e = pd.DataFrame([])
    for i, v in evGatePass:
        for _v in v:
            e = e.append(pd.DataFrame(
                {'time-since-start [s]': _v, 'object-id': i,
                 'object-name': 'gate', 'is-collision': 0, 'is-pass': 1},
                index=[0]))
    for i, v in evGateCollision:
        for _v in v:
            e = e.append(pd.DataFrame(
                {'time-since-start [s]': _v, 'object-id': i,
                 'object-name': 'gate', 'is-collision': 1, 'is-pass': 0},
                index=[0]))
    for i, v in evWallCollision:
        for _v in v:
            e = e.append(pd.DataFrame(
                {'time-since-start [s]': _v, 'object-id': i,
                 'object-name': 'wall', 'is-collision': 1, 'is-pass': 0},
                index=[0]))
    e = e.sort_values(by=['time-since-start [s]'])
    # make output folder
    outpath = '/process/'.join(
        (PATH.split('.csv')[0] + '/').split('/logs/'))
    if os.path.exists(outpath) == False:
        make_path(outpath)
    # copy trajectory data
    copyfile(PATH, outpath + 'trajectory.csv')
    # save the events
    e.to_csv(outpath + 'events.csv', index=False)
    # compute performance metrics
    # ----------------------------
    # start time: start of the flight
    tStart = e['time-since-start [s]'].iloc[0]
    # find collision events
    ec = e.loc[(e['is-collision'].values == 1), :]
    # if collisions detected
    if ec.shape[0] > 0:
        tFirstCollision = ec['time-since-start [s]'].iloc[0]
        hasCollision = 1
        ind = e['time-since-start [s]'].values < tFirstCollision
        en = e.copy().iloc[ind, :]
    # if no collisions detected
    else:
        hasCollision = 0
        tFirstCollision = np.nan
        en = e.copy()
    # end time: time of first collision or end of logging
    if np.isnan(tFirstCollision):
        tEnd = np.nanmax(d['time-since-start [s]'].values)
    else:
        tEnd = tFirstCollision
    # compute the flight times
    flightTimeTotal = tEnd - tStart
    flightTimeMPC = flightTimeTotal
    flightTimeNetwork = 0.
    if tSwitch is not None:
        flightTimeMPC = tSwitch - tStart
        flightTimeNetwork = tEnd - tSwitch
    # how many gates were passed in total
    ind = en['is-pass'].values == 1
    numGatePassesTotal = np.sum(ind)
    idGatePassesTotal = [en.loc[ind, 'object-id'].values]
    tsGatePassesTotal = [en.loc[ind, 'time-since-start [s]'].values]
    if tSwitch is not None:
        # how many gates were passed by MPC
        ind = (en['time-since-start [s]'].values <= tSwitch) & (
                    en['is-pass'].values == 1)
        numGatePassesMPC = np.sum(ind)
        idGatePassesMPC = [en.loc[ind, 'object-id'].values]
        tsGatePassesMPC = [en.loc[ind, 'time-since-start [s]'].values]
        # how many gates were passed by the network
        ind = (en['time-since-start [s]'].values > tSwitch) & (
                    en['time-since-start [s]'].values <= tEnd) & (
                          en['is-pass'].values == 1)
        numGatePassesNetwork = np.sum(ind)
        idGatePassesNetwork = [en.loc[ind, 'object-id'].values]
        tsGatePassesNetwork = [en.loc[ind, 'time-since-start [s]'].values]
    else:
        # how many gates were passed by MPC
        numGatePassesMPC = numGatePassesTotal
        idGatePassesMPC = idGatePassesTotal
        tsGatePassesMPC = tsGatePassesTotal
        # how many gates were passed by the network
        numGatePassesNetwork = 0
        idGatePassesNetwork = None
        tsGatePassesNetwork = None
    # flight distance
    ind = (_t >= tStart) & (_t <= tEnd)
    flightDistanceTotal = np.nansum(
        np.linalg.norm(np.diff(_p[ind, :], axis=0), axis=1))
    if tSwitch is not None:
        ind = (_t >= tStart) & (_t <= tSwitch)
        flightDistanceMPC = np.nansum(
            np.linalg.norm(np.diff(_p[ind, :], axis=0), axis=1))
        ind = (_t > tSwitch) & (_t <= tEnd)
        flightDistanceNetwork = np.nansum(
            np.linalg.norm(np.diff(_p[ind, :], axis=0), axis=1))
    else:
        flightDistanceMPC = flightDistanceTotal
        flightDistanceNetwork = 0
    # collect performance metrics in pandas dataframe
    p = pd.DataFrame({'time-start [s]': tStart, 'time-switch [s]': tSwitch,
                      'time-end [s]': tEnd,
                      'flight-time-total [s]': flightTimeTotal,
                      'flight-time-mpc [s]': flightTimeMPC,
                      'flight-time-network [s]': flightTimeNetwork,
                      'flight-distance-total [m]': flightDistanceTotal,
                      'flight-distance-mpc [m]': flightDistanceMPC,
                      'flight-distance-network [m]': flightDistanceNetwork,
                      'num-gate-passes-total': numGatePassesTotal,
                      'num-gate-passes-mpc': numGatePassesMPC,
                      'num-gate-passes-network': numGatePassesNetwork,
                      'gate-id-total': idGatePassesTotal,
                      'gate-id-mpc': idGatePassesMPC,
                      'gate-id-network': idGatePassesNetwork,
                      'gate-ts-total': tsGatePassesTotal,
                      'gate-ts-mpc': tsGatePassesMPC,
                      'gate-ts-network': tsGatePassesNetwork,
                      'has-collision': hasCollision, 'filepath': outpath},
                     index=[0])
    # save performance metrics
    p.to_csv(outpath + 'performance.csv', index=False)
    # save the animation
    # if toSaveAnimation or toShowAnimation:
    #     print('..saving animation')
    #     gate_objects = objGatePass + objGateCollider + objWallCollider
    #     d['simulation-time-since-start [s]'] = d[
    #         'time-since-start [s]'].values
    #     anim = Animation3D(d, Gate_objects=gate_objects,
    #                        equal_lims=(-30, 30))
    #     if toSaveAnimation:
    #         if os.path.isfile(outpath + 'anim.mp4') == False:
    #             anim.save(outpath + 'anim.mp4', writer='ffmpeg', fps=25)
    #     if toShowAnimation:
    #         anim.show()

# todo: update documentation of this function, make this a function of the
#  liftoff module
def make_path(PATH):
    if PATH[0] == '/':
        outpath = '/'
    else:
        outpath = ''
    folders = PATH.split('/')
    for fold in folders:
        if len(fold)>0:
            outpath += fold +'/'
            if os.path.isdir(outpath) == False:
                os.mkdir(outpath)


def trajectory_from_flightmare(filepath: str) -> pd.DataFrame():
    """Returns a trajectory dataframe with standard headers from a flightmare
    log filepath."""
    ndict = {
        'time-since-start [s]': 't',
        'position_x [m]': 'px',
        'position_y [m]': 'py',
        'position_z [m]': 'pz',
        'rotation_x [quaternion]': 'qx',
        'rotation_y [quaternion]': 'qy',
        'rotation_z [quaternion]': 'qz',
        'rotation_w [quaternion]': 'qw',
        'velocity_x': 'vx',
        'velocity_y': 'vy',
        'velocity_z': 'vz',
        'acceleration_x': 'ax',
        'acceleration_y': 'ay',
        'acceleration_z': 'az',
        'omega_x': 'wx',
        'omega_y': 'wy',
        'omega_z': 'wz'
        }
    if os.path.exists(filepath) is False:
        return pd.DataFrame([])
    else:
        df = pd.read_csv(filepath)
        # Rename columns according to the name dictionairy.
        for search_name, replacement_name in ndict.items():
            for column_name in df.columns:
                if column_name.find(search_name) != -1:
                    df = df.rename(columns={column_name: replacement_name})
        # Sort columns using found dictionairy entries first and unknown last.
        known_names = [name for name in ndict.values() if name in df.columns]
        unknown_names = [name for name in df.columns if name not in known_names]
        sorted_names = known_names.copy()
        sorted_names.extend(unknown_names)
        df = df.loc[:, sorted_names]
        # Sort values by timestamp
        df = df.loc[:, sorted_names]
        df = df.sort_values(by=['t'])
        return df


def plot_trajectory(
        px: np.ndarray([]), py: np.ndarray([]), pz: np.ndarray([])=np.array([]),
        qx: np.ndarray([])=np.array([]), qy: np.ndarray([])=np.array([]),
        qz: np.ndarray([])=np.array([]), qw: np.ndarray([])=np.array([]),
        c: str=None, ax: plt.axis()=None, axis_length: float=1.,
        ) -> plt.axis():
    """Returns an axis handle for a 2D or 3D trajectory based on position and
    rotation data."""
    # Check if the plot is 2D or 3D.
    if pz.shape[0] == 0:
        is_two_d = True
    else:
        is_two_d = False
    # Make a new figure if no axis was provided.
    if ax is None:
        fig = plt.figure()
        if is_two_d:
            ax = fig.add_subplot(1, 1, 1)
        else:
            ax = fig.add_subplot(1, 1, 1, projection='3d')
    # Plot the flightpath
    if is_two_d:
        if c is None:
            ax.plot(px, py)
        else:
            ax.plot(px, py, color=c)
    else:
        if c is None:
            ax.plot(px, py, pz)
        else:
            ax.plot(px, py, pz, color=c)
    # Plot 3D quadrotor rotation
    if not is_two_d:
        if ((qx.shape[0] > 0) and (qy.shape[0] > 0) and (qz.shape[0] > 0)
                and (qw.shape[0] > 0)):
            for primitive, color in [((1, 0, 0), 'r'),
                                     ((0, 1, 0), 'g'),
                                     ((0, 0, 1), 'b')]:
                p0 = np.hstack((px.reshape(-1, 1), np.hstack((py.reshape(-1, 1),
                                                              pz.reshape(-1, 1)))))
                q = np.hstack((qx.reshape(-1, 1),
                               np.hstack((qy.reshape(-1, 1),
                                          np.hstack((qz.reshape(-1, 1),
                                                     qw.reshape(-1, 1)))))))
                p1 = p0 + Rotation.from_quat(q).apply(np.array(primitive)
                                                      * axis_length)
                for i in (range(p0.shape[0])):
                    ax.plot([p0[i, 0], p1[i, 0]], [p0[i, 1], p1[i, 1]],
                            [p0[i, 2], p1[i, 2]], color=color)
    return ax


def format_trajectory_figure(
        ax: plt.axis(), xlims: tuple=(), ylims: tuple=(), zlims: tuple=(),
        xlabel: str='', ylabel: str='', zlabel: str='', title: str='',
        ) -> plt.axis():
    """Apply limits, labels, and title formatting for a supplied figure axis."""
    if len(xlims) > 0:
        ax.set_xlim(xlims)
    if len(ylims) > 0:
        ax.set_ylim(ylims)
    if len(zlims) > 0:
        ax.set_zlim(zlims)
    if len(xlabel) > 0:
        ax.set_xlabel(xlabel)
    if len(ylabel) > 0:
        ax.set_ylabel(ylabel)
    if len(zlabel) > 0:
        ax.set_zlabel(zlabel)
    if len(title) > 0:
        ax.set_title(title)
    return ax


def wall_colliders(dims=(1, 1, 1), center=(0, 0, 0)):
    """Returns a list of 'Gate' objects representing the walls of a race
    track in 3D.
        dims: x, y, z dimensions in meters
        denter: x, y, z positions of the 3d volume center"""
    objWallCollider = []

    _q = (Rotation.from_euler('y', [np.pi/2]) * Rotation.from_quat(np.array([0, 0, 0, 1]))).as_quat().flatten()

    objWallCollider.append(Gate(pd.DataFrame({'pos_x': [center[0]],
                                              'pos_y': [center[1]],
                                              'pos_z': [center[2] - dims[2]/2],
                                              'rot_x_quat': [_q[0]],
                                              'rot_y_quat': [_q[1]],
                                              'rot_z_quat': [_q[2]],
                                              'rot_w_quat': [_q[3]],
                                              'dim_x': [0],
                                              'dim_y': [dims[1]],
                                              'dim_z': [dims[0]]},
                                             index=[0]).iloc[0],
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

