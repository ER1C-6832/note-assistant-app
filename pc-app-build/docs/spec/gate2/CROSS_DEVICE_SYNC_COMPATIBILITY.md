# Android / PC 双端数据同步兼容设计

## 1. 与 Gate 2 的关系

Gate 2 是 Assistant Runtime，不直接实现便签云同步。但 Runtime、MCP 和双端同步会在以下位置相交：

- MCP 创建的便签需要稳定跨设备标识；
- `source_conversation_id` 需要跨端可追踪；
- assistant/user settings 必须区分设备本地和用户同步；
- 未来从 Android 搜索/删除 PC 创建的便签不能依赖本地整数 ID。

因此现在冻结兼容边界，真正同步可在后续独立 Gate 实现。

## 2. 当前 schema 差异

### Android NoteEntity 当前字段

```text
id local Long
title
content
type
content_format
is_done
done_at
pinned
archived
deleted
archived_at
deleted_at
color
tag_text
reminder_at
sort_order
created_at
updated_at
last_edited_source
source_conversation_id
```

### PC Gate 1 当前字段

```text
id local Integer
title
content
tags
is_pinned
is_deleted
created_at
updated_at
source
```

结论：

- 两端本地自增 ID 都不能用于同步；
- PC 目前缺少 Android 的多项产品字段；
- `tags` 与 `tag_text` 的存储格式不同；
- Android 有 deleted_at，PC 只有布尔删除；
- Android 已有 source_conversation_id，PC 尚未对齐。

## 3. 统一跨端 Note Contract

建议新增一个平台中立的同步模型：

```text
sync_id UUID
schema_version
revision
server_version optional
title
content
note_type
content_format
is_done
done_at
is_pinned
is_archived
archived_at
is_deleted
deleted_at
color
tags[]
reminder_at
sort_order
created_at
updated_at
last_edited_source
source_conversation_id
origin_device_id
last_modified_device_id
```

本地数据库仍可保留整数主键用于 join 和性能：

```text
local id: database internal
sync_id: external and cross-device identity
```

## 4. 时间和冲突

- 网络协议统一 UTC；
- 精度至少毫秒，推荐 ISO-8601 UTC 或 epoch ms；
- 性能指标继续使用 monotonic ns，不参与同步；
- `updated_at` 不能单独承担版本控制；
- 使用 revision/server_version 做乐观并发；
- 删除使用 tombstone，不立即丢记录；
- hard delete 需要服务端确认和保留期。

第一版冲突策略可采用：

```text
字段级策略未实现前：last-write-wins + revision precondition
冲突时：保留 server/current 与 local candidate，生成 conflict record
```

不可静默覆盖用户正文。

## 5. MCP 外部标识

Gate 5 工具返回：

```text
note_id = sync_id
```

不返回本地整数主键。

工具参数也优先接受 `sync_id`。本地整数 ID 仅允许 UI/Repository 内部使用。

## 6. 设置同步分类

### 永不跨设备同步

- device_id；
- client_id；
- serial_number；
- hmac key；
- websocket token；
- 本机 audio device id；
- microphone lease；
- session_id；
- phase/reconnect/VAD/generation；
- 本地路径；
- debug trace。

### 默认设备本地

- assistant enabled；
- KWS enabled；
- 开机启动；
- 音频输入输出设备；
- 本机 endpoint override；
- developer mode。

### 可考虑用户级同步

- preferred voice interaction mode；
- streaming idle timeout；
- barge-in preference；
- UI theme；
- 用户自定义标签；
- 非敏感助手偏好。

同步前必须给每个设置定义 scope：`device`、`account` 或 `workspace`。

## 7. 推荐新增里程碑

### Cross-device Readiness Gate（Gate 5 前置）

- Android/PC 都增加 sync_id；
- additive migration；
- UUID 唯一索引；
- source_conversation_id 对齐；
- deleted_at/tombstone 对齐；
- tag canonical format；
- external DTO 不暴露 local id；
- 双端 fixture round-trip 测试。

它不必阻塞 Gate 2 文本 Runtime，但必须阻塞 Gate 5 的稳定 MCP note identifier 和后续真正同步。

## 8. 双端契约测试

建立共享 JSON fixtures：

```text
note-normal.json
note-todo-done.json
note-archived.json
note-deleted-tombstone.json
note-created-by-voice.json
note-with-tags-reminder.json
```

Android 和 PC 都必须：

- decode；
- encode；
- 保持 sync_id；
- 保持 UTC 时间；
- 保持 unknown optional fields 或通过 schema migration 明确处理；
- 不把 local id 写入网络 DTO。
