
// pybind11
#include <pybind11/eigen.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

// flightlib
#include "flightlib/envs/env_base.hpp"
#include "flightlib/envs/env_base_camera.hpp"
#include "flightlib/envs/quadrotor_env/quadrotor_env.hpp"
#include "flightlib/envs/test_env.hpp"
#include "flightlib/envs/vec_env.hpp"
#include "flightlib/envs/racing_env/racing_test_env.hpp"
#include "flightlib/envs/racing_env/racing_env.hpp"
#include "flightlib/envs/test_mpc_env.hpp"

namespace py = pybind11;
using namespace flightlib;

PYBIND11_MODULE(flightgym, m) {
  py::class_<VecEnv<QuadrotorEnv>>(m, "QuadrotorEnv_v1")
    .def(py::init<>())
    .def(py::init<const std::string&>())
    .def(py::init<const std::string&, const bool>())
    .def("reset", &VecEnv<QuadrotorEnv>::reset)
    .def("step", &VecEnv<QuadrotorEnv>::step)
    .def("testStep", &VecEnv<QuadrotorEnv>::testStep)
    .def("setSeed", &VecEnv<QuadrotorEnv>::setSeed)
    .def("close", &VecEnv<QuadrotorEnv>::close)
    .def("isTerminalState", &VecEnv<QuadrotorEnv>::isTerminalState)
    .def("curriculumUpdate", &VecEnv<QuadrotorEnv>::curriculumUpdate)
    .def("connectUnity", &VecEnv<QuadrotorEnv>::connectUnity)
    .def("disconnectUnity", &VecEnv<QuadrotorEnv>::disconnectUnity)
    .def("getNumOfEnvs", &VecEnv<QuadrotorEnv>::getNumOfEnvs)
    .def("getObsDim", &VecEnv<QuadrotorEnv>::getObsDim)
    .def("getActDim", &VecEnv<QuadrotorEnv>::getActDim)
    .def("getExtraInfoNames", &VecEnv<QuadrotorEnv>::getExtraInfoNames)
    .def("__repr__", [](const VecEnv<QuadrotorEnv>& a) {
      return "RPG Drone Racing Environment";
    });

  py::class_<TestEnv<QuadrotorEnv>>(m, "TestEnv_v0")
    .def(py::init<>())
    .def("reset", &TestEnv<QuadrotorEnv>::reset)
    .def("__repr__", [](const TestEnv<QuadrotorEnv>& a) { return "Test Env"; });

  py::class_<RacingTestEnv>(m, "RacingTestEnv_v0")
    .def(py::init<>())
    .def(py::init<const std::string&>())
    .def("reset", &RacingTestEnv::reset)
    .def("step", &RacingTestEnv::step)
    .def("setSeed", &RacingTestEnv::setSeed)
    .def("close", &RacingTestEnv::close)
    .def("getImageHeight", &RacingTestEnv::getImageHeight)
    .def("getImageWidth", &RacingTestEnv::getImageWidth)
    .def("connectUnity", &RacingTestEnv::connectUnity)
    .def("disconnectUnity", &RacingTestEnv::disconnectUnity)
    .def("getObsDim", &RacingTestEnv::getObsDim)
    .def("getActDim", &RacingTestEnv::getActDim)
    .def("__repr__", [](const RacingTestEnv& a) {
      return "Drone Racing Test Environment";
    });

    py::class_<MPCTest>(m, "MPCTest_v0")
    .def(py::init<>())
    .def(py::init<const std::string&, const bool>())
    .def("step", &MPCTest::step)
    .def("getImageHeight", &MPCTest::getImageHeight)
    .def("getImageWidth", &MPCTest::getImageWidth)
    .def("connectUnity", &MPCTest::connectUnity)
    .def("disconnectUnity", &MPCTest::disconnectUnity)
    .def("setWaveTrack", &MPCTest::setWaveTrack)
    .def("__repr__", [](const MPCTest& a) {
      return "MPC Test Environment";
    });

    py::class_<RacingEnv>(m, "RacingEnv")
    .def(py::init<>())
    .def(py::init<const std::string&>())
    .def("getObs", &RacingEnv::getObs)
    .def("step", &RacingEnv::step)
    .def("reset", &RacingEnv::reset)
    .def("setReducedState", &RacingEnv::setReducedState)
    .def("getImageHeight", &RacingEnv::getImageHeight)
    .def("getImageWidth", &RacingEnv::getImageWidth)
    .def("getObsDim", &RacingEnv::getObsDim)
    .def("getActDim", &RacingEnv::getActDim)
    .def("getSimTimeStep", &RacingEnv::getSimTimeStep)
    .def("connectUnity", &RacingEnv::connectUnity)
    .def("disconnectUnity", &RacingEnv::disconnectUnity)
    .def("__repr__", [](const RacingEnv& a) {
      return "Drone Racing Environment";
    });
}