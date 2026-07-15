# Gate 2.2 身份迁移与 Gate 1.7 回归修复报告

## 基线

- 仓库：`ER1C-6832/note-assistant-app`
- 基线提交：`1dd6964941fe25f126bc2eb8dc6a37308de6eaa0`
- 问题来源：Windows 本机全量验收与真实 OTA 检查

## 已确认问题

### 1. Gate 1.7 误报

Gate 1.7 通过全文查找 `py-xiaozhi` 判断是否仍依赖旧 Runtime。Gate 2.2 新增的身份兼容模块只读取旧配置文件，没有导入旧 Runtime、启动进程或建立控制链路，但仍被这个纯文本规则误判。

修复后检查真实危险行为：

- 外部 Runtime Python 导入；
- `subprocess` / `multiprocessing` / `QProcess`；
- localhost 控制路径；
- Sidecar 进程模式。

并为身份兼容模块增加独立只读边界检查。

### 2. Windows 旧身份目录少了一层

旧 PC 客户端通过 `platformdirs.user_data_dir("py-xiaozhi")` 解析用户数据目录。Windows 下 `platformdirs` 默认同时使用 app author 和 app name，因此实际常见目录是：

```text
%LOCALAPPDATA%\py-xiaozhi\py-xiaozhi\config
```

上一版只检查：

```text
%LOCALAPPDATA%\py-xiaozhi\config
```

所以没有找到原来的 `efuse.json` 与 `config.json`，继而生成随机本地 MAC，服务器自然把它识别为新设备并返回验证码。

### 3. 已生成的错误身份会阻止后续迁移

第一次错误运行已把随机身份写入 `assistant_runtime.json`。原实现只要看到本地身份存在，就不会再次尝试迁移。

本次为身份记录增加向后兼容的 `source` 字段。旧文件没有该字段时读取为 `unknown`。当发现更可信的旧配置身份或本机指纹身份时，会：

1. 替换 `unknown/generated_random` 身份；
2. identity generation 加一；
3. 清除错误身份产生的 WebSocket token、验证码和 challenge；
4. 保留 OTA 与授权地址；
5. 重新执行真实 OTA 检查。

## 身份搜索顺序

只读扫描以下候选目录，不执行旧客户端代码：

```text
%LOCALAPPDATA%\py-xiaozhi\py-xiaozhi\config
%LOCALAPPDATA%\py-xiaozhi\config
%APPDATA%\py-xiaozhi\py-xiaozhi\config
%APPDATA%\py-xiaozhi\config
用户目录下的 Linux/macOS 兼容目录
当前工作区及上三级目录的 py-xiaozhi / py-xiaozhi-tao-analysis 兄弟目录
NOTE_ASSISTANT_LEGACY_CONFIG_DIR（可选覆盖）
```

也兼容 `py_xiaozhi` 和 `xiaozhi` 目录名。

## 回退策略

- 找到完整 `efuse.json + config.json`：复用原 MAC、Client ID、serial、HMAC，`identity_source=legacy_config`。
- 找到部分旧配置：组合可恢复字段，并用本机真实 MAC/机器指纹补全。
- 未找到旧配置但能读取真实 MAC：使用本机指纹身份，绝不使用随机伪 MAC。
- 无法取得可靠 MAC：最后才使用随机身份。

服务器仍是激活状态的最终真相。若旧 Client ID 文件已经丢失或服务器撤销授权，真实检查仍可能合法返回验证码，此时不能伪装为已激活。

## 真实检查输出新增字段

```text
identity_source
identity_repaired
previous_identity_source
compatibility_config_path
legacy_local_activation_marked
```

预期已迁移设备常见输出：

```text
identity_source = legacy_config
identity_repaired = true
status = activated
```

## 验证

在 Gate 2.1 + Gate 2.2 重建基线上完成：

```text
55 passed
Black check：补丁文件全部 unchanged
Ruff：通过
Python compileall：通过
```

测试覆盖：

- Windows platformdirs 双层目录；
- 旧 schema 中没有 source 的身份；
- 已持久化随机身份自动替换；
- 替换时清除错误验证码、challenge、token；
- 分散的旧配置字段与机器指纹组合；
- Gate 1.7 不再误报只读迁移模块；
- 外部 Runtime、第二进程和 localhost 控制路径仍被禁止。
