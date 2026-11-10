/*
 * SPDX-FileCopyrightText: 2026 M5Stack Technology CO LTD
 *
 * SPDX-License-Identifier: MIT
 */
#include "default.h"

using namespace uitk::lvgl_cpp;
using namespace stackchan::avatar;
LV_FONT_DECLARE(grok_status_24);

void DefaultAvatar::init(lv_obj_t* parent, const lv_font_t* font)
{
    _pannel = std::make_unique<Container>(parent);
    _pannel->align(LV_ALIGN_CENTER, 0, 0);
    _pannel->setSize(320, 240);
    _pannel->setRadius(0);
    _pannel->setBorderWidth(0);
    _pannel->setBgColor(secondaryColor);
    _pannel->removeFlag(LV_OBJ_FLAG_SCROLLABLE);

    _key_elements.leftEye  = std::make_unique<DefaultEyes>(_pannel->get(), primaryColor, secondaryColor, true);
    _key_elements.rightEye = std::make_unique<DefaultEyes>(_pannel->get(), primaryColor, secondaryColor, false);
    _key_elements.mouth    = std::make_unique<DefaultMouth>(_pannel->get(), primaryColor, secondaryColor);
    _key_elements.speechBubble =
        std::make_unique<DefaultSpeechBubble>(_pannel->get(), primaryColor, secondaryColor, font);

    _title = std::make_unique<Label>(_pannel->get());
    _title->setTextFont(&lv_font_montserrat_24);
    _title->setTextColor(primaryColor);
    _title->setTextAlign(LV_TEXT_ALIGN_CENTER);
    _title->setAlign(LV_ALIGN_CENTER);
    _title->setPos(0, -76);
    _title->setWidth(280);
    _title->setLongMode(LV_LABEL_LONG_MODE_DOTS);
    _title->setHidden(true);

    // Created only when requested by a BLE monitor, so other apps keep their skin.
}

void DefaultAvatar::setStatusView(std::string_view skin, std::string_view state, std::string_view text)
{
    if (skin == "grok") {
        if (!_status_view) {
            _status_view = std::make_unique<GrokStatusView>(_pannel->get(), &grok_status_24);
        }
        _status_view->show(state, text);
    } else if (skin == "default" && _status_view) {
        _status_view->hide();
    }
}

void DefaultAvatar::setTitle(std::string_view text)
{
    if (_title) {
        _title->setText(text);
        _title->setHidden(text.empty());
    }
}

Container* DefaultAvatar::getPanel() const
{
    if (_pannel) {
        return _pannel.get();
    }
    return NULL;
}
