# 短片：从素材到 20–60 秒成片

## 一、滤镜链骨架

一条 ffmpeg 命令完成：拉长/截齐片段 → 交叉淡化 → 烧字幕 → 混音 → 响度归一。

```bash
ffmpeg -i a.mp4 -i b.mp4 -i narration.wav -i pad.wav -/filter_complex film.filter \
  -map "[vout]" -map "[aout]" \
  -c:v libx264 -preset medium -crf 19 -pix_fmt yuv420p \
  -c:a aac -b:a 160k -movflags +faststart out.mp4
```

filter 文件里每段：

```
[0:v]setpts=1.29*PTS,trim=duration=6.5,setpts=PTS-STARTPTS,fps=30,scale=1280:720,setsar=1[v0]
[v0][v1]xfade=transition=fade:duration=0.5:offset=6.0[x1]
[x1][v2]xfade=transition=fade:duration=0.5:offset=12.0[x2]
[x2]subtitles=filename=D\:/work/subs.srt:force_style='FontName=Microsoft YaHei,FontSize=20'[vout]
[3:a]adelay=800|800[na]
[4:a]volume=0.2[mu]
[na][mu]amix=inputs=2:duration=longest:normalize=0,loudnorm=I=-18:TP=-2:LRA=9,atrim=duration=18.5[aout]
```

要点：

- 每段先 `setpts` 拉长再 `trim`，总长长出一截，`xfade` 的 offset 按"累计时长 − 0.5"算；
- 字幕路径里的冒号要转义成 `D\:/...`；
- `normalize=0` 别省，否则 `amix` 会偷偷把两边都压低；
- 最后 `loudnorm` 再 `atrim`，成片响度稳定。

## 二、TTS 的坑

- 官方 TTS 返回的 wav，头里 data 长度可能是 `0xFFFFFFFF`；ffmpeg 只警告一句，Windows 的播放器直接判"不是有效 wav"。**播放或剪辑前先重写头**（`scripts/fix_tts_wav.py`）。
- 计算时长别信头部字段：`(文件大小 - 44) / (采样率 × 2)`，24 kHz 单声道时这个估算够用。
- 字幕时间轴可以按字数比例排，但**必须人工校对**。ASR 常见的错："他/它"、"琴剑/琴键"、整句漏字。

## 三、自算配乐

不需要采样音源也能有铺底：正弦波叠四个和弦，固定 BPM，一晚就能合出来（`scripts/make_pad.py`）。

- 好处：无版权问题、可精确对齐时长、参数全在手里；
- 坏处：没有节拍冲击力，做不了鼓点卡点；
- 用法：**当环境底噪**，音量压到旁白的 20%，别让它抢戏。

## 四、素材分层

- AI 生成：负责画面与转场，**不负责叙事**；
- 真实素材：负责"这是真的"，优先当主角；
- 自算音频：负责氛围，不负责情绪高潮。

## 五、请人看片时问什么

不问"好不好"，问三个：

1. **哪一段你走神了？**（走神的位置比夸奖有用）
2. 看完记得住哪一句、哪一个画面？
3. 你信不信片子里那句自述？（哪里让你信、哪里让你不信）

**"没感觉"是有效回答**——它说明该改的是片子，不是观众的耳朵。

## 六、作业纪律

- 生成超时（比如 600 秒）**不要盲目重试**，用已有素材补位；
- 交付前必做：抽帧看字幕、听一遍混音、确认时长；
- 删素材前确认成片已归档；**失败素材不删**，它是下一篇的原料。
