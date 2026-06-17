cmake_minimum_required(VERSION 3.10)
project(Calculations CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)

find_package(Eigen3 REQUIRED)
find_package(ur_rtde REQUIRED)
find_package(zenohc CONFIG REQUIRED)
find_package(zenohcxx CONFIG REQUIRED)

include_directories(include)

add_executable(main src/main.cpp src/calculations.cpp)

target_link_libraries(main
    Eigen3::Eigen
    ur_rtde::rtde
)

add_executable(zenoh_pub src/zenoh_pub.cpp)
target_link_libraries(zenoh_pub PRIVATE zenohcxx::zenohc)

add_executable(zenoh_sub src/zenoh_sub.cpp)
target_link_libraries(zenoh_sub PRIVATE zenohcxx::zenohc)