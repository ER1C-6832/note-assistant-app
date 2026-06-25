# Phase 9.0 Demo 启动说明

## 一键启动

```bat
cd /d C:\yuyinzhushou\note-assistant-app\pc-app-build
scripts\start_all_integrated.bat
```

该脚本会依次启动：

1. Notes API
2. 本地语音桥接服务
3. 桌面应用

## 环境检查

```bat
scripts\check_demo_environment.bat
```

## 语音助手路径检查

```bat
scripts\bootstrap_py_xiaozhi_runtime.bat
```

## 登录预热

默认关闭。可在应用设置页开启：

```text
设置 -> 开机后后台准备 -> 登录 Windows 后自动准备语音助手
```

开启后会在 Windows 登录时后台准备语音助手；关闭后不会常驻后台 Python 进程。
