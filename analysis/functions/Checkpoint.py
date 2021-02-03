import numpy as np
from shapely.geometry import LineString
from scipy.spatial.transform import Rotation


class Checkpoint(object):

    def __init__(self, df):
        #checkpoint position
        p = df[['checkpoint-center_x [m]', 'checkpoint-center_y [m]', 'checkpoint-center_z [m]']].values.flatten()
        #checkpoint rotation
        q = df[['rotation_x [quaternion]', 'rotation_y [quaternion]', 'rotation_z [quaternion]', 'rotation_w [quaternion]']].values.flatten()
        #checkpoint dimension/width
        w = df[['checkpoint-size_x [m]', 'checkpoint-size_y [m]', 'checkpoint-size_z [m]']].values.flatten()
        #checkpoint half width
        hw = w / 2.
        # assuming gates are oriented in the direction of flight: x=forward, y=left, z=up
        proto = np.array([[ hw[0],  hw[1],  hw[2]],
                          [ hw[0], -hw[1],  hw[2]],
                          [ hw[0], -hw[1], -hw[2]],
                          [ hw[0],  hw[1], -hw[2]],
                          [ hw[0],  hw[1],  hw[2]],
                          [-hw[0],  hw[1],  hw[2]],
                          [-hw[0], -hw[1],  hw[2]],
                          [-hw[0], -hw[1], -hw[2]],
                          [-hw[0],  hw[1], -hw[2]],
                          [-hw[0],  hw[1],  hw[2]]]).T

        self._corners = (Rotation.from_quat(q).apply(proto.T).T + p.reshape(3, 1)).astype(float)
        self._center = p
        self._rotation = q
        #top-view line representation of gate horizontal axis
        self._xy = LineString([(self._corners[0, 0], self._corners[1, 0]), (self._corners[0, 2], self._corners[1, 2])])
        #side-view line representation of the gate vertical axis
        self._z = np.array([np.min(self._corners[2, :]), np.max(self._corners[2, :])])

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
    def xy(self):
        return self._xy

    @property
    def z(self):
        return self._z

    def intersect(self, p0, p1):
        '''
        p0 and p1 are the start and endpoints of a line in W frame
        '''
        point_2d = None
        point_3d = None

        #only proceed if no nan values
        if (np.sum(np.isnan(p0).astype(int))==0) & (np.sum(np.isnan(p1).astype(int))==0):

            line_xy = LineString([(p0[0], p0[1]), (p1[0], p1[1])])

            if self.xy.intersects(line_xy):
                xy = [val for val in self.xy.intersection(line_xy).coords]
                if len(xy) == 2:
                    ind = np.argmin(np.array([np.linalg.norm(np.array(xy[0]) - p0[:2]),
                                              np.linalg.norm(np.array(xy[1]) - p0[:2])]))
                else:
                    ind = 0
                p_xy = xy[ind]
                b = p1-p0
                b /= np.linalg.norm(b)
                f = (p_xy[0]-p0[0])/b[0]
                _p = p0+f*b
                p_z = _p[2]
                if (p_z >= self._z[0]) & (p_z <= self._z[1]):
                    point_3d = np.array([p_xy[0], p_xy[1], p_z])
                    point_2d = self.point2d(point_3d)
        return point_2d, point_3d

    def point2d(self, p):
        '''
        For AIRR square gates placed vertically
        x=right
        y=down
        origin at top left
        '''
        p0_xy = self._corners[:2, 0] #gate horizontal axis origin
        p1_xy = self._corners[:2, 2] #gate horizontal axis endpoint
        x = np.linalg.norm(p[:2]-p0_xy) / np.linalg.norm(p1_xy-p0_xy)
        p0_z = self._corners[2, 0]  # gate vertical axis origin
        p1_z = self._corners[2, 2]  # gate vertical axis endpoint
        y = np.abs(p[2] - p0_z) / np.abs(p1_z - p0_z)
        return np.array([x, y])
