// SPDX-License-Identifier: MIT
#include "grok_status_view.h"
#include <cmath>

namespace stackchan::avatar {
namespace {
lv_obj_t* box(lv_obj_t* parent, int w, int h, uint32_t color)
{
    auto* obj = lv_obj_create(parent);
    lv_obj_remove_style_all(obj);
    lv_obj_set_size(obj, w, h);
    lv_obj_set_style_bg_color(obj, lv_color_hex(color), 0);
    lv_obj_set_style_bg_opa(obj, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(obj, LV_RADIUS_CIRCLE, 0);
    lv_obj_remove_flag(obj, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_remove_flag(obj, LV_OBJ_FLAG_CLICKABLE);
    return obj;
}

lv_obj_t* label(lv_obj_t* parent, const lv_font_t* font, uint32_t color)
{
    auto* obj = lv_label_create(parent);
    lv_obj_set_style_text_font(obj, font, 0);
    lv_obj_set_style_text_color(obj, lv_color_hex(color), 0);
    lv_obj_set_style_text_align(obj, LV_TEXT_ALIGN_CENTER, 0);
    return obj;
}

bool valid_state(std::string_view state)
{
    return state == "unknown" || state == "idle" || state == "thinking" || state == "working" ||
           state == "waiting" || state == "done" || state == "error" || state == "offline";
}
}  // namespace

GrokStatusView::GrokStatusView(lv_obj_t* parent, const lv_font_t* font)
{
    _root = box(parent, 320, 240, 0x08090B);
    lv_obj_set_style_radius(_root, 0, 0);
    lv_obj_center(_root);
    auto* title = label(_root, &lv_font_montserrat_16, 0xA8ADB7);
    lv_label_set_text(title, "GROK BUILD");
    lv_obj_align(title, LV_ALIGN_TOP_MID, 0, 28);

    _body = box(_root, 112, 112, 0xECEDEF);
    lv_obj_set_style_bg_grad_color(_body, lv_color_hex(0xB8BDC7), 0);
    lv_obj_set_style_bg_grad_dir(_body, LV_GRAD_DIR_VER, 0);
    for (int i = 0; i < 2; ++i) {
        _eyes[i] = box(_body, 13, 29, 0x111214);
        lv_obj_set_style_transform_pivot_x(_eyes[i], 6, 0);
        lv_obj_set_style_transform_pivot_y(_eyes[i], 14, 0);
    }
    _symbol = label(_root, &lv_font_montserrat_24, 0xFFCA64);
    lv_obj_set_pos(_symbol, 237, 78);
    _status = label(_root, font, 0xECEDEF);
    lv_obj_set_width(_status, 292);
    lv_label_set_long_mode(_status, LV_LABEL_LONG_MODE_SCROLL_CIRCULAR);
    lv_obj_align(_status, LV_ALIGN_TOP_MID, 0, 187);
    _dot = box(_root, 6, 6, 0x7B8493);
    lv_obj_set_pos(_dot, 157, 220);
    _timer = lv_timer_create([](lv_timer_t* timer) {
        static_cast<GrokStatusView*>(lv_timer_get_user_data(timer))->render();
    }, 50, this);
    hide();
}

GrokStatusView::~GrokStatusView()
{
    if (_timer) lv_timer_delete(_timer);
    if (_root) lv_obj_delete(_root);
}

void GrokStatusView::show(std::string_view state, std::string_view text)
{
    _last_update = lv_tick_get();
    const auto next = valid_state(state) ? state : std::string_view("unknown");
    if (_state != next) {
        _state = next;
        _started = lv_tick_get();
    }
    // Heartbeats must not restart a long label's scrolling animation.
    if (_text != text) {
        _text = text;
        lv_label_set_text(_status, _text.c_str());
    }
    lv_obj_remove_flag(_root, LV_OBJ_FLAG_HIDDEN);
    lv_timer_resume(_timer);
    render();
}

void GrokStatusView::hide()
{
    lv_obj_add_flag(_root, LV_OBJ_FLAG_HIDDEN);
    lv_timer_pause(_timer);
}

void GrokStatusView::render()
{
    if (lv_tick_elaps(_last_update) > 15000 && _state != "offline") {
        _state = "offline";
        _text = !_text.empty() && static_cast<unsigned char>(_text.front()) >= 128 ? "连接已断开" : "Disconnected";
        _started = lv_tick_get();
        lv_label_set_text(_status, _text.c_str());
    }
    const uint32_t elapsed = lv_tick_elaps(_started);
    const float t = static_cast<float>(elapsed % 12000) / 1000.0f;
    const float wave = std::sin(t * 4.0f);
    int width = 112, height = 112, x = 0, y = 0, look = 0, eye_height = 29, angle = -260;
    uint32_t color = 0x8793A5;
    const char* symbol = "";
    if (_state == "thinking") {
        look = static_cast<int>(std::sin(t * 2.0f) * 12);
        y = static_cast<int>(wave * 3);
        color = 0xFFCC66;
        symbol = "...";
    } else if (_state == "working") {
        width += static_cast<int>(wave * 9);
        height -= static_cast<int>(wave * 9);
        y = -static_cast<int>(std::fabs(wave) * 9);
        color = 0x77B5FF;
        symbol = ">_";
    } else if (_state == "waiting") {
        look = static_cast<int>(std::sin(t * 2.5f) * 14);
        color = 0xC9A0FF;
        symbol = "?";
    } else if (_state == "done") {
        // Celebration settles after two seconds; keep the completed status legible.
        y = elapsed < 2000 ? -static_cast<int>(std::fabs(wave) * 13) : 0;
        eye_height = 8;
        angle = 0;
        color = 0x8BE0AE;
        symbol = LV_SYMBOL_OK;
    } else if (_state == "error") {
        x = elapsed < 2000 ? static_cast<int>(std::sin(t * 24) * 8) : 0;
        eye_height = 17;
        angle = 260;
        color = 0xFF818B;
        symbol = "!";
    } else if (_state == "offline") {
        height = 85;
        y = 13;
        eye_height = 4;
        angle = 0;
        color = 0x767D88;
        symbol = "z";
    } else if (_state == "idle") {
        y = static_cast<int>(std::sin(t * 2) * 3);
        color = 0x8BCED4;
    } else {
        symbol = "?";
    }
    // A short blink every four seconds, except for smile/sleep poses.
    if (_state != "done" && _state != "offline" && elapsed % 4000 > 3850) eye_height = 3;
    lv_obj_set_size(_body, width, height);
    lv_obj_set_pos(_body, 160 - width / 2 + x, 116 - height / 2 + y);
    for (int i = 0; i < 2; ++i) {
        lv_obj_set_size(_eyes[i], 13, eye_height);
        lv_obj_set_pos(_eyes[i], width / 2 + (i == 0 ? 1 : 26) + look - 6,
                       height / 2 - 17 - eye_height / 2);
        lv_obj_set_style_transform_rotation(_eyes[i], angle, 0);
    }
    lv_label_set_text(_symbol, symbol);
    lv_obj_set_style_text_color(_symbol, lv_color_hex(color), 0);
    lv_obj_set_style_text_color(_status, lv_color_hex(color), 0);
    lv_obj_set_style_bg_color(_dot, lv_color_hex(color), 0);
}
}  // namespace stackchan::avatar
