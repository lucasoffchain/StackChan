cmake_minimum_required(VERSION 3.20)
project(grok_screen_preview LANGUAGES C CXX)
set(CONFIG_LV_BUILD_DEMOS OFF CACHE BOOL "" FORCE)
set(CONFIG_LV_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(CONFIG_LV_USE_THORVG_INTERNAL OFF CACHE BOOL "" FORCE)
set(LV_BUILD_CONF_PATH "${CMAKE_CURRENT_SOURCE_DIR}/lv_conf.h" CACHE PATH "" FORCE)
if(NOT LVGL_SOURCE_DIR)
    message(FATAL_ERROR "Set LVGL_SOURCE_DIR to LVGL 9.5.0")
endif()
add_subdirectory("${LVGL_SOURCE_DIR}" lvgl)
add_executable(grok_screen_preview render.cpp
    ../../../firmware/main/assets/fonts/grok_status_24.c
    ../../../firmware/main/stackchan/avatar/skins/grok/grok_status_view.cpp)
target_compile_features(grok_screen_preview PRIVATE cxx_std_17)
target_link_libraries(grok_screen_preview PRIVATE lvgl::lvgl)
target_include_directories(grok_screen_preview PRIVATE
    ../../../firmware/main/stackchan/avatar/skins/grok)
