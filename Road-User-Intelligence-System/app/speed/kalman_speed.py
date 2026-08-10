"""
Per-track Kalman filter — Week 5, v2.

Constant-velocity model: state = [x, y, vx, vy] in real-world meters.
Handles variable frame timing (recomputes transition matrix per update
using actual dt, since your video may not be perfectly constant-fps).
"""

import cv2
import numpy as np

from app.config import KALMAN_PROCESS_NOISE, KALMAN_MEASUREMENT_NOISE


class KalmanFilter2D:
    def __init__(self):
        self.kf = cv2.KalmanFilter(4, 2)
        self.kf.measurementMatrix = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], dtype=np.float32)
        self.kf.processNoiseCov = np.eye(4, dtype=np.float32) * KALMAN_PROCESS_NOISE
        self.kf.measurementNoiseCov = np.eye(2, dtype=np.float32) * KALMAN_MEASUREMENT_NOISE
        self.initialized = False
        self.last_time = None

    def _set_transition(self, dt):
        self.kf.transitionMatrix = np.array([
            [1, 0, dt, 0],
            [0, 1, 0, dt],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ], dtype=np.float32)

    def update(self, t, x, y):
        """Predict + correct with a real measurement. Returns (vx, vy) in m/s."""
        if not self.initialized:
            self.kf.statePost = np.array([[x], [y], [0], [0]], dtype=np.float32)
            self.initialized = True
            self.last_time = t
            return 0.0, 0.0

        dt = max(t - self.last_time, 1e-3)
        self.last_time = t
        self._set_transition(dt)
        self.kf.predict()
        measurement = np.array([[np.float32(x)], [np.float32(y)]])
        state = self.kf.correct(measurement)
        return float(state[2]), float(state[3])

    def predict_only(self, t):
        """Predict without correcting — used when a measurement is distrusted
        (e.g. optical flow disagreement) so one bad frame doesn't corrupt the filter."""
        if not self.initialized:
            return 0.0, 0.0
        dt = max(t - self.last_time, 1e-3)
        self.last_time = t
        self._set_transition(dt)
        state = self.kf.predict()
        return float(state[2]), float(state[3])