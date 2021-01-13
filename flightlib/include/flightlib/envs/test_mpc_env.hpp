#pragma once

// std lib
#include <stdlib.h>
#include <cmath>
#include <iostream>
#include <string>

// yaml cpp
#include <yaml-cpp/yaml.h>

// Eigen
#include <eigen3/Eigen/Dense>

// opencv
#include <opencv2/core/mat.hpp>
#include <opencv2/core/eigen.hpp>

// flightlib
#include "flightlib/bridges/unity_bridge.hpp"
#include "flightlib/common/quad_state.hpp"
#include "flightlib/common/types.hpp"
#include "flightlib/objects/quadrotor.hpp"
#include "flightlib/sensors/rgb_camera.hpp"
#include "flightlib/objects/static_gate.hpp"

namespace flightlib {

namespace mpcenv {
    enum Ctl : int {
      // observations
      kObs = 0,
      //
      kPos = 0,
      kNPos = 3,
      kOri = 3,
      kNOri = 3,
      kLinVel = 6,
      kNLinVel = 3,
      kAngVel = 9,
      kNAngVel = 3,
      kNObs = 12,
      // control actions
      kAct = 0,
      kNAct = 4,
      // image dimensions
      // image_height = 600,
      // image_width = 800,
      // fov = 90,
      // for testing
      image_height = 600,
      image_width = 800,
      fov = 90,
      // track info (should probably be loaded)
      num_gates = 10,
    };
};

class MPCTest {
 public:
  MPCTest();
  MPCTest(const std::string &cfg_path, const bool wave_track = false);
  ~MPCTest();

  // method to set the quadrotor state and get a rendered image
  bool step(const Ref<Vector<>> new_state, Ref<ImageFlat<>> image);

  // Unity methods
  void addObjectsToUnity(std::shared_ptr<UnityBridge> bridge);
  bool setUnity(bool render);
  bool connectUnity();
  void disconnectUnity();

  // getter methods
  int getImageHeight() const;
  int getImageWidth() const;

  bool loadParam(const YAML::Node &cfg);

 private:
  // quadrotor
  std::shared_ptr<Quadrotor> quadrotor_ptr_;
  std::shared_ptr<Quadrotor> camera_dummy_;
  QuadState quad_state_;
  QuadState camera_dummy_state_;
  Matrix<3, 2> world_box_;

  // camera
  int cam_height_, cam_width_, cam_fov_;
  std::shared_ptr<RGBCamera> rgb_camera_;

  // image observations
  int image_counter_;
  ImageChannel<mpcenv::image_height, mpcenv::image_width> channels_[3];
  cv::Mat cv_image_;
  cv::Mat cv_channels_[3];

  // gates
  std::shared_ptr<StaticGate> gates_[mpcenv::num_gates];

  // unity
  std::shared_ptr<UnityBridge> unity_bridge_ptr_;
  SceneID scene_id_{UnityScene::ALPHAPILOT};
  bool unity_ready_{false};
  bool unity_render_{false};

  std::vector<std::vector<Scalar>> test_yaml_;
};

}  // namespace flightlib