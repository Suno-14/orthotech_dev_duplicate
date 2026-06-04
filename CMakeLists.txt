cmake_minimum_required(VERSION 3.10)
project(Calculations CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)

find_package(Eigen3 REQUIRED)
add_subdirectory(third_party/ur_rtde)


include_directories(include)

add_executable(main src/main.cpp
src/calculations.cpp)

target_include_direcotories(main
    PRIVATE
    inlcude
    )

target_link_libraries(main
    PRIVATE
    Eigen3::Eigen
    rtde
)