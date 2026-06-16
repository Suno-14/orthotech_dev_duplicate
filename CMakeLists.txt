cmake_minimum_required(VERSION 3.16)
project(OrthoTech CXX)

set(CMAKE_EXPORT_COMPILE_COMMANDS TRUE)

if(CMAKE_INSTALL_PREFIX_INITIALIZED_TO_DEFAULT)
    # PROJECT_SOURCE_DIR is the root folder where your main CMakeLists.txt lives
    set(CMAKE_INSTALL_PREFIX "${PROJECT_SOURCE_DIR}/install" CACHE PATH "Local install directory" FORCE)
endif()

set(CMAKE_PREFIX_PATH "/opt/orthotech_dev")

# == 
# 2. RUNTIME / LINKER SEARCH PATHS (Linux vs Windows)
# == 
if (UNIX AND NOT APPLE)
    # Linux-specific settings
    set(CMAKE_INSTALL_RPATH_USE_LINK_PATH TRUE)
    set(CMAKE_BUILD_WITH_INSTALL_RPATH FALSE)
    set(CMAKE_INSTALL_RPATH
        "$ORIGIN"
        "$ORIGIN/../lib"
        "$ORIGIN/../../lib"
        "/opt/orthotech_dev/lib"
    )
elseif (WIN32)
    # Windows-specific settings
    set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
    set(CMAKE_LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
    set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib")
endif()

set(as_subproject;
    supervisor;
    )

macro(find_package)
    if(NOT "${ARGV0}" IN_LIST as_subproject)
        _find_package(${ARGV})
    endif()
endmacro()

add_subdirectory(src/supervisor)
