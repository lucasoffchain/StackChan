# Grok status font

`grok_status_24.c` contains ASCII and a small set of Chinese status glyphs at 24 px,
4 bits per pixel. It is a subset of **Noto Sans SC**, weight 500, distributed under
the SIL Open Font License in `OFL-NotoSansSC.txt`. It is not a full Chinese font.

Source: https://github.com/google/fonts/tree/main/ofl/notosanssc

Generated using fonttools 4.68.0 (instantiate the variable font at `wght=500`),
then lv_font_conv 1.5.3:

```text
lv_font_conv --font NotoSansSC-Medium.ttf --size 24 --bpp 4 --format lvgl \
  --range 0x20-0x7e \
  --symbols '状态未知准备就绪正在思考执行等待处理任务完成运行出错已离线连接断开重新' \
  --no-compress --lv-font-name grok_status_24 -o grok_status_24.c
```

Keep the license with generated fonts. When adding Chinese messages, regenerate
the subset with all required characters and check the LVGL preview.
