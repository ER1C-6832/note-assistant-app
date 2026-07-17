# Gate 5 Test and Acceptance Plan

状态：冻结候选  
适用范围：Gate 5.0 through Gate 5.4。  
原则：每个 verifier fail-fast、传播 exit code，并继续执行此前已冻结的累计回归。

## 1. 测试层级

```text
Unit
-> service / protocol integration
-> Fake end-to-end
-> QML / UI smoke
-> Real protocol probe
-> Real CRUD + tag + confirmation acceptance
-> cumulative resource closeout
```

只有 Automated + Fake + Real 都有证据，Gate 5 才可 Accepted。

## 2. Canonical verifiers

建议新增：

```text
tools/verify_gate5_0_protocol.py
tools/verify_gate5_1_read_ui.py
tools/verify_gate5_2_mutations.py
tools/verify_gate5_3_confirmation.py
tools/verify_gate5_fake_full.py
tools/verify_gate5_real_tools_list.py
tools/verify_gate5_real_crud.py
tools/verify_gate5_4_cumulative.py
```

最终 canonical entry：

```powershell
python tools/verify_gate5_4_cumulative.py
python tools/verify_gate5_real_tools_list.py
python tools/verify_gate5_real_crud.py
```

本地 PowerShell wrapper 可继续 gitignore，但仓库内 Python verifier 必须可审查、可版本化。

## 3. 每阶段累计检查

`verify_gate5_4_cumulative.py` 至少执行：

```text
dependency/import check
compileall apps tools tests
Black --check apps tools tests
Ruff apps tools tests
all tests under tests/
Gate 4 Fake playback
Gate 4 Fake two-turn
Gate 5 protocol verifier
Gate 5 read/UI verifier
Gate 5 mutation verifier
Gate 5 confirmation verifier
Gate 5 full Fake runner
QML smoke
secret/payload persistence scan
resource/task leak scan
exit code propagation
```

Real verifier 不应被普通无音频 CI 假装通过。环境缺失必须返回 blocked=2；协议/行为失败返回 1；通过返回 0。

## 4. Registry and schema acceptance

必须精确断言：

```text
tool_count == 31
tool_names == frozen Gate 5 set
duplicates == []
unsupported_android_tools intersection == []
```

每个 descriptor 必须包含：

```text
name
description
inputSchema
risk
mutates
confirmation
```

Schema 测试：

- required fields；
- additionalProperties 策略；
- string/array/int/bool 类型；
- title 1～200；
- ids 正整数、去重、非空、数量上限；
- limit 上限；
- enum；
- mutually exclusive arguments；
- oversized payload；
- unknown fields；
- Unicode/Chinese content；
- invalid JSON/root array/null。

## 5. Protocol matrix

| 场景 | 预期 |
|---|---|
| initialize | protocolVersion/serverInfo/tools capability |
| initialized notification | no response, no error |
| tools/list | exactly 31, nextCursor empty |
| tools/list unknown cursor | invalid params |
| tools/call known | one result |
| unknown method | -32601 |
| unknown tool | -32601 / not_implemented contract |
| invalid params | -32602, zero handler execution |
| malformed JSON | parse/invalid request, receiver alive |
| string/integer id | response preserves id type/value |
| notification without id | no response |
| queue full | bounded server_busy, receiver alive |
| oversized input | rejected before handler |
| oversized result | safely truncated/failed, sender alive |
| stale generation | no response on new socket, no replay |

断言 MCP response 只经过现有 sender；底层 websocket `.send()` 调用者数量不得增加。

## 6. Idempotency matrix

至少覆盖：

```text
duplicate completed read
duplicate in-flight read
duplicate completed create
duplicate in-flight create
duplicate delete confirmation request
duplicate assistant.confirm
same request id + different arguments
same request id + different tool
cache capacity eviction
disconnect after commit before response
reconnect does not replay
shutdown while duplicate waiter awaits
```

核心断言：

```text
one logical request -> at most one mutation transaction
```

## 7. Tool behavior coverage

### 7.1 Read / resolve

每个工具覆盖：success、empty、not_found、invalid params、limit、deleted filtering。

额外：

- resolve exact id；
- resolve exact title；
- resolve unique fuzzy；
- resolve ambiguous returns candidates；
- ambiguous target followed by mutation remains zero-write；
- recent ordering ignores pin priority；
- todo maps to exact protected tag；
- snippets/results respect result budget。

### 7.2 Note mutation

- create normal/todo, title validation, source voice_pc；
- append separator and empty-content rejection；
- update title preserves content/tags；
- replace content requires confirmation and checks stale timestamp；
- convert type only adds/removes `待办`；
- pin/unpin single/batch and >5 escalation；
- delete always confirmation, soft-delete only；
- restore active/deleted/not-found and >5 escalation；
- all successful mutations refresh active UI state。

### 7.3 Tags

- list includes custom/default/protected/used/deletable；
- search normalization；
- duplicate create idempotent；
- system/protected names rejected；
- delete protected/system/in-use rejected even after confirm；
- bind add/remove/replace；
- bind retains tag order/dedup；
- bind all-or-nothing rollback；
- concurrent UI add + MCP add does not lose catalog entries；
- create/update/bind observes unknown tags into catalog。

### 7.4 UI

- each command produces one typed UI event；
- no direct QML/Repository access；
- stale UI generation drops event；
- UI unavailable returns blocked；
- open missing/deleted note fails safely；
- mutation commit causes current view refresh；
- selection preserved when note remains visible；
- tag sidebar refreshes。

## 8. Confirmation race matrix

至少覆盖：

```text
create pending
list current pending
confirm once
confirm twice
reject once
reject then confirm
confirm then reject
expiry then confirm
disconnect then confirm
disable then confirm
shutdown then confirm
wrong session confirm
wrong generation confirm
tampered arguments/fingerprint
target modified before confirm
target deleted before confirm
confirm and expiry simultaneously
confirm and reject simultaneously
capacity overflow
```

所有 race 必须 exactly-once finalize；确认前数据库和 TagCatalog 零变化。

## 9. Failure and lifecycle matrix

至少覆盖：

```text
DB validation error
DB busy/transaction rollback
TagCatalog read/write error
UI command adapter error
audit write error
tool handler unexpected exception
result serialization failure
sender closes before response
disconnect during queued request
disconnect during active read
disconnect during active mutation
reconnect while old worker settles
mode switch during tool call
disable during tool call
shutdown during tool call
request queue overflow
dedupe cache pressure
pending confirmation pressure
```

高风险错误不得降级为执行；已提交事务不得谎称回滚。

## 10. Privacy acceptance

自动扫描与行为测试必须证明以下内容不出现在 log/report/AssistantState：

```text
raw MCP payload
full title/content/query
confirmation preview full content
authorization/token/HMAC
full session/device/client identity
PCM/Opus bytes
```

允许记录：tool name、risk、status、duration、masked/hash request id、affected ids、error code。

异常消息通过 allowlist mapping 生成，不直接 `str(exc)` 返回给服务端或 UI。

## 11. Fake full scenario

Fake runner 必须执行全部 31 个 descriptor 的可调用性检查，并至少完成：

```text
initialize/list
create normal
create todo
search/list/get/resolve
append/update_title/convert_type
tags create/search/list/bind
pin
UI navigation
replace -> reject
delete -> reject
delete -> confirm
list_deleted/show_trash
restore
pending list/expiry
duplicate request
clean shutdown
```

Fake 不得绕过真实 registry、risk、confirmation、services 或 UiCommandBus。

## 12. Real acceptance

### 12.1 Real tools/list

记录：

```text
endpoint public URL
connection generation
session id masked
initialize request/response verified
tools/list request/response verified
tool count 31
name set hash
unknown tool fail-closed
pending assistant tasks
```

不得记录 raw descriptors 中可能含有的敏感动态值。

### 12.2 Real CRUD/tag/UI scenario

使用独立测试前缀，例如 `Gate5Real-<short-id>`，避免误操作既有便签。

真实步骤：

1. 创建 normal note；
2. 创建 todo note；
3. list_recent/search/get/resolve；
4. append；
5. update_title；
6. convert type；
7. create/search/list/bind tag；
8. pin；
9. open/search/tag/pinned UI；
10. delete 后 reject，验证 note 仍 active；
11. 再次 delete 后 confirm，验证进入 trash；
12. list_deleted/show_trash；
13. restore；
14. 清理测试便签时仍只允许软删除并显式确认。

人工确认：

- 语音模型选择了正确工具；
- 回复与数据库结果一致；
- UI 自动刷新；
- 确认/拒绝语义清楚；
- 无错误删除非测试便签。

## 13. Final resource assertions

Real/Fake runner 退出后必须全部成立：

```text
request_queue_size == 0
mcp_worker_alive == false
tool_task_count == 0
inflight_request_count == 0
dedupe_waiter_count == 0
pending_confirmation_count == 0
ui_command_task_count == 0
mcp_response_future_count == 0
reconnect_timer_running == false
streaming_response_timer_running == false
audio_uplink_task == none
capture_stream_active == false
playback_output_active == false
transport_sender_alive == false
transport_receiver_alive == false
assistant_pending_tasks == []
python_process_count == 1 during app / 0 after exit
```

## 14. Final report evidence

`GATE5_FINAL_ACCEPTANCE_REPORT.md` 必须记录：

- acceptance commit SHA；
- exact test commands；
- total passed/failed/skipped；
- Real tools/list sanitized JSON；
- Real CRUD/tag/UI scenario sanitized JSON；
- duplicate/confirmation/resource evidence；
- artificial/manual confirmation result；
- blocked environment 与 product failure 的区分；
- 已知非目标和下一 Gate 边界。

只写“请运行以下命令”不能签署 Accepted。

