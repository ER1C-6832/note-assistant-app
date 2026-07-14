# ADR-002：PC 音频栈

状态：Accepted for Gate 0

## 决策

MVP 使用 `sounddevice RawInputStream / RawOutputStream + libopus/opuslib + PCM16 bytes`。

上行固定为 16kHz、mono、20ms、640 bytes PCM/frame、Opus VOIP 24kbps。

## 原因

协议参数与 Android 一致；Raw Stream 避免热路径 float32 转换；py-xiaozhi 只作为设备和 libopus 经验来源，不复用其 Runtime 生命周期。

## 后果

Windows 设备差异需要真机测试；输出采样率留在 Playback Adapter；AEC、NS、AGC 和 KWS 不属于 MVP。
