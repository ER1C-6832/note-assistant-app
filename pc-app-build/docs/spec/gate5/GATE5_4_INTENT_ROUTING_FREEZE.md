# Gate 5.4 Intent Routing Freeze

状态：冻结候选

## 1. 边界

自然语言到工具的最终选择仍由 Xiaozhi 服务端完成。PC 客户端不新增第二个 LLM、关键词命令总线或绕过 MCP 的本地自然语言执行器。

Gate 5.4 只增强两层：

1. `tools/list` 中 31 个 descriptor 的中文路由说明；
2. 已经进入 `notes.search` / `notes.resolve` 的 query 参数做确定性、无副作用的口语冗余清理。

## 2. 参考来源

旧 main 的 MCP 工具说明已经证明以下提示对选工具有帮助：

- 明确写出“便签 / 小智便签 / 记到便签”等触发表达；
- 明确排除文件工具和 Windows 记事本；
- 目标含糊时先 search，再 update/delete；
- description 中说明参数含义和安全边界。

旧阶段和 Android 工具面中的 UI action / read-before-write / confirmation 语义被保留，但实现仍是当前 PC 单进程链路：

```text
Xiaozhi MCP -> ToolRegistry -> Gate53ToolExecutor
-> NoteCommandService / NoteQueryService / TagCatalogService / UiCommandBus
```

不引回 Sidecar、HTTP NotesApiClient、PC-only alias、全局 `_CONTEXT` 或 Android 不存在于 PC schema 的 archive/done/revision 工具。

## 3. 全局路由规则

- 查找目标：`notes.resolve` 或 `notes.search`；不得直接猜 note id。
- 读取明确目标：`notes.get`。
- 列表型问题：recent/tag/deleted/todo/pinned 使用对应 list 工具。
- 追加、标题修改、正文替换和待办转换必须使用独立工具。
- UI 导航使用 `ui.*`；读取数据不能假装完成 UI 切换。
- 高风险 mutation 先产生 pending，再用 confirmation 工具消费。
- 用户只说“确认/取消”时先列 pending；多个 pending 时必须追问。
- 小智便签请求不得路由到文件写入或系统记事本。

## 4. 口语 query 归一化

允许安全处理：

```text
“麻烦帮我找一下那个关于王总报价的便签” -> “王总报价”
“请在小智便签里查查我之前记的包装问题” -> “包装问题”
“编号为 12 的便签” -> note_id 12
```

规则：

- 优先提取引号内容；
- 去除有界的礼貌语、查找动词和“便签应用里”等对象词；
- 精确清理后的完整主题优先于较短 fallback token；
- 最多保留 8 个候选 term；
- 不把 query 或正文写入日志/审计；
- 纯指代“刚才那条”只有 scope 中唯一候选时才能 resolved，否则 ambiguous。

## 5. 冻结值

```text
工具数量                 31
工具名集合 SHA-256       58840e01b41f8f3cf08a406428bab9261d07a664be7212d3d650e5016da22693
Android unsupported       8 个，继续不广告
工具列表序列化预算         < 64 KiB
```
