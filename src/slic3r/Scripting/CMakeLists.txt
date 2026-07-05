# libbambu_api — the embedded pyslic3r Python runtime host.
#
# Kept as its own static target (additive-and-isolated invariant): the only
# core edits are the one init/shutdown hook pair in GUI_App.cpp and the
# wiring in the parent CMakeLists. Mutually dependent with libslic3r_gui
# (the bindings call Plater; GUI_App calls host_init) — a static-library
# cycle CMake resolves by repeating archives on the link line.

add_library(libbambu_api STATIC
    PyHost.hpp
    PyHost.cpp
    M0SelfTest.cpp
)

# Same include roots as libslic3r_gui: src/ is the include root
# ("slic3r/GUI/GUI_App.hpp", "libslic3r/Model.hpp").
target_include_directories(libbambu_api PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/../..)
target_include_directories(libbambu_api PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/..)

target_compile_definitions(libbambu_api PRIVATE BBS_PY_RUNTIME=1)

# Plain (non-keyword) signature to stay compatible with the parent scope's
# usage on libslic3r_gui; wxWidgets flags/includes arrive via the directory-
# scope include(${wxWidgets_USE_FILE}) in src/CMakeLists.txt.
target_link_libraries(libbambu_api libslic3r cereal imgui pybind11::embed ${wxWidgets_LIBRARIES})

encoding_check(libbambu_api)
