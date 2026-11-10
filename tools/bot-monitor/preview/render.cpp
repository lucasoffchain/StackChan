// Render the production LVGL view, exercising updates, timeouts and destruction.
#include "grok_status_view.h"
#include <array>
#include <cstdio>
#include <filesystem>
#include <stdexcept>
#include <string>

static std::array<uint8_t, 320 * 240 * 4> pixels;
LV_FONT_DECLARE(grok_status_24);
static void flush(lv_display_t* display, const lv_area_t*, uint8_t*)
{
    lv_display_flush_ready(display);
}

static void save(const std::filesystem::path& path)
{
    lv_refr_now(nullptr);
    auto* image = lv_snapshot_take(lv_screen_active(), LV_COLOR_FORMAT_RGB888);
    if (!image) throw std::runtime_error("LVGL snapshot failed");
    FILE* out = std::fopen(path.string().c_str(), "wb");
    if (!out) throw std::runtime_error("Cannot save snapshot");
    std::fprintf(out, "P6\n320 240\n255\n");
    for (int y = 0; y < 240; ++y) {
        const auto* row = image->data + y * image->header.stride;
        for (int x = 0; x < 320; ++x) {
            const uint8_t rgb[] = {row[x * 3 + 2], row[x * 3 + 1], row[x * 3]};
            std::fwrite(rgb, 1, 3, out);
        }
    }
    std::fclose(out);
    lv_draw_buf_destroy(image);
}

int main(int argc, char** argv)
{
    if (argc != 2) return 2;
    std::filesystem::path output(argv[1]);
    std::filesystem::create_directories(output);
    lv_init();
    auto* display = lv_display_create(320, 240);
    lv_display_set_buffers(display, pixels.data(), nullptr, pixels.size(), LV_DISPLAY_RENDER_MODE_FULL);
    lv_display_set_flush_cb(display, flush);
    {
        stackchan::avatar::GrokStatusView view(lv_screen_active(), &grok_status_24);
        const char* states[] = {"idle", "thinking", "working", "waiting", "done", "error", "offline", "unknown"};
        const char* texts[] = {"准备就绪", "正在思考", "正在执行", "等待处理", "任务完成", "运行出错", "已离线", "状态未知"};
        for (int i = 0; i < 8; ++i) {
            view.show(states[i], texts[i]);
            for (int frame = 0; frame < 12; ++frame) {
                lv_tick_inc(100);
                lv_timer_handler();
                save(output / (std::string(states[i]) + "-" + std::to_string(frame) + ".ppm"));
            }
        }
        view.show("working", "正在执行");
        lv_tick_inc(16000);
        lv_timer_handler();
        save(output / "timeout.ppm");
        view.show("thinking", "重新连接");
        save(output / "reconnected.ppm");
        view.hide();
        save(output / "hidden.ppm");
    }
    lv_tick_inc(1000);
    lv_timer_handler();
    lv_display_delete(display);
    lv_deinit();
    return 0;
}
