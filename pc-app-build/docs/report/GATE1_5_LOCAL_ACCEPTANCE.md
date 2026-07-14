# Gate 1.5 本地验收指南

## 1. 覆盖位置

将覆盖包解压到仓库根目录：

```text
C:\yuyinzhushou\note-assistant-app-runtime-v2\
```

必须允许覆盖同名文件。

## 2. 推荐一键验证

在仓库根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\VERIFY_GATE1_5.ps1
```

全部命令退出码应为 0。

## 3. 分步验证

```powershell
cd C:\yuyinzhushou\note-assistant-app-runtime-v2\pc-app-build

python -m compileall -q apps\notes-pyside\app\ui tests\gate1_5
python -m black --check apps\notes-pyside\app\ui tests\gate1_5
python -m ruff check apps\notes-pyside\app\ui tests\gate1_5
python -m pytest tests\gate1_5 -q
python -m pytest tests\gate1_1 tests\gate1_2 tests\gate1_3 tests\gate1_4 tests\gate1_5 -q
```

Gate 1.5 定向测试应显示：

```text
8 passed
```

累计测试要求：

```text
0 failed
0 errors
无 collection error
```

## 4. main.py Smoke

```powershell
cd C:\yuyinzhushou\note-assistant-app-runtime-v2\pc-app-build\apps\notes-pyside
python main.py
```

通过条件：

- 窗口启动；
- 无 Python traceback；
- 无 MigrationConflictError；
- 无 QML load error；
- 关闭窗口后进程退出；
- 无 Sidecar 或第二 Python 进程。

Gate 1.5 尚未接入 Bootstrap/QML，所以 UI 仍是 Empty ViewModel 是预期结果。

## 5. 最终验收

```text
[ ] compileall 通过
[ ] Black 通过
[ ] Ruff 通过
[ ] Gate 1.5: 8 passed
[ ] Gate 1.1～1.5 累计测试全绿
[ ] main.py 可启动并正常退出
[ ] app/ui 中不存在 SQLAlchemy/Session/HTTP 依赖
[ ] 不修改 QML 和 Bootstrap
```
