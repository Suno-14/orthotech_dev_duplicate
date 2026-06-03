cmake_minimum_required(VERSION 3.10)

project(Calculations CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(main
    src/main.cpp
    src/calculations.cpp
)

target_include_directories(main PRIVATE
    include
    external/eigen
)
