// SPDX-License-Identifier: MIT
#pragma once
#include <lvgl.h>
#include <string>
#include <string_view>

namespace stackchan::avatar {

// A code-drawn interpretation of the Grok Bot orb. No downloaded brand assets.
// The view owns its timer and LVGL tree; destroy it before its parent.
class GrokStatusView {
public:
    GrokStatusView(lv_obj_t* parent, const lv_font_t* font);
    ~GrokStatusView();
    GrokStatusView(const GrokStatusView&) = delete;
    GrokStatusView& operator=(const GrokStatusView&) = delete;
    void show(std::string_view state, std::string_view text);
    void hide();

private:
    void render();
    lv_obj_t* _root = nullptr;
    lv_obj_t* _body = nullptr;
    lv_obj_t* _eyes[2] = {};
    lv_obj_t* _symbol = nullptr;
    lv_obj_t* _status = nullptr;
    lv_obj_t* _dot = nullptr;
    lv_timer_t* _timer = nullptr;
    std::string _state;
    std::string _text;
    uint32_t _started = 0;
    uint32_t _last_update = 0;
};

}  // namespace stackchan::avatar
