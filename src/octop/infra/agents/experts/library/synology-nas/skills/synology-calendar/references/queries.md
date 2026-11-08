# Calendar 查询结构

以下结构来自本项目配套 `my-nas` 客户端的 `lib/api/calendar_api.dart`，只作查询起点，不代表在当前 NAS 已实机验收。先核对 `nas_apis` / `nas_describe` 返回的版本；未注册或版本不匹配就停止，不试探其他方法。

Calendar 的这些接口将包括字符串在内的参数值按 JSON 序列化，因此 `request.encoding` 使用 `json`，`params` 保持自然 JSON，不提前双重编码。

| 目标 | API | method / version | params |
| --- | --- | --- | --- |
| 日历列表 | `SYNO.Cal.Cal` | `list` / 2 | `{"is_todo": false, "is_evt": true}` |
| 待办列表目录 | `SYNO.Cal.Cal` | `list` / 2 | `{"is_todo": true, "is_evt": false}` |
| 范围内日程 | `SYNO.Cal.Event` | `list` / 1 | `{"cal_id_list": [实际日历ID], "start": 起始Unix秒, "end": 结束Unix秒, "list_repeat": true}` |
| 事件详情 | `SYNO.Cal.Event` | `get` / 1 | `{"evt_id": 实际事件ID}` |
| 未完成待办 | `SYNO.Cal.Todo` | `list` / 1 | `{"cal_id_list": [实际待办日历ID], "list_repeat": false, "filter_due": 3, "filter_complete": 2}` |
| 待办详情 | `SYNO.Cal.Todo` | `get` / 1 | `{"evt_id": 实际待办ID}` |
| Calendar 用户设置 | `SYNO.Cal.Setting` | `get` / 2 | `{}` |

例如日历列表的工具参数：

```json
{
  "request": {
    "api": "SYNO.Cal.Cal",
    "method": "list",
    "version": 2,
    "encoding": "json",
    "params": {"is_todo": false, "is_evt": true}
  },
  "execute": false
}
```

返回预览后，在当前账号、版本和查询范围确认无误且连接器写开关开启时，同一请求改为 `execute=true` 才会查询。查询授权不构成新增日程的授权。列表可能按日历 ID 分组，保留分组来源；已有客户端通过 `list_repeat=true` 请求重复事件，仍应检查实际返回范围和实例标识。

此参考不定义写入格式。Calendar 新版事件的时间、重复、附件和并发校验与旧版不同，写入必须另行核实当前版本，不能从查询字段推断。
