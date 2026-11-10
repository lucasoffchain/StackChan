# Native LVGL screen preview

This compiles and renders the **production** `GrokStatusView` with LVGL 9.5.0,
without ESP-IDF, Bluetooth, a browser simulation or a connected robot.

Install CMake, Ninja and a C/C++17 compiler; fetch LVGL tag `v9.5.0` separately.
From the repository root:

```text
cmake -S tools/bot-monitor/preview -B tools/bot-monitor/.cache/render-build -G Ninja \
  -DLVGL_SOURCE_DIR=<absolute path to lvgl> -DCMAKE_BUILD_TYPE=Release
cmake --build tools/bot-monitor/.cache/render-build
tools/bot-monitor/.cache/render-build/grok_screen_preview tools/bot-monitor/.cache/screen-preview
```

On Windows use the `.exe` executable. The harness saves PPM images for every
status, heartbeat timeout, reconnection and hiding the view. It also destroys
the view and runs the timer loop afterwards to check timer lifetime handling.
PPM images can be converted to PNG/GIF with Pillow. This checks the view's native
rendering and API compatibility; it does not replace the full firmware build
or a physical-screen test.

Visual reference: the Grok Bot orb and diagonal eyes shown on the
[official application listing](https://play.google.com/store/apps/details?id=ai.x.grok.bot),
checked on 2026-11-11. The firmware draws its own interpretation with LVGL shapes;
it does not include downloaded mascot artwork or claim to contain xAI's original
animation source. The monitored program is **Grok Build**, so the screen title is
`GROK BUILD`.
