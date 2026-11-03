# 内容包格式

A主要维护 `assets/content/nodes.json`，UTF-8编码。数组顺序就是学习顺序，增加或减少节点不用改界面代码。运行 `scripts/validate_data.py` 检查格式。

新增可选旁文件 `lessons.json`，用于每站答题前的学习过场；它不改变原nodes.json格式。图片与文字配置详见 [学习过场配置](LESSONS.md)。

## 顶层

| 字段 | 约定 |
|---|---|
| `schema_version` | 当前为1 |
| `id` | 内容包稳定ID，影响存档名称，使用英文、数字与连字符；不要使用路径字符 |
| `version` | 内容版本，例如0.1.0 |
| `title` | 标题 |
| `scope` | 历史范围与示意限制说明 |
| `review_status` | 当前draft；正式核验后可改为reviewed |
| `nodes` | 至少一个节点 |

## 节点

`id` 全包唯一且保持稳定；`name` 完整名称，`short_name` 用于地图标签；`time`、`place` 为展示文本；`event`、`spirit`、`modern` 分别为史事、精神解读、现实联系；`sources` 为非空来源列表；`questions` 至少一道。

`position: [x, y]` 为0—1范围的相对绘图位置，不是经纬度。请避开边缘与其他标签。合并史事与历史延伸应在正文说明，路线不是完整或精确行军路线。

## 题目

```json
{
  "id": "unique-question-id",
  "type": "single_choice",
  "prompt": "题目内容",
  "options": [
    {"id": "a", "text": "选项一"},
    {"id": "b", "text": "选项二"}
  ],
  "answer": ["a"],
  "explanation": "为什么正确，以及常见混淆。"
}
```

题目 `id` 全包唯一；选项ID在该题中唯一。答案引用选项ID，不引用显示顺序。单选答案只有一个；多选使用 `multiple_choice`，答案数组包含所有正确选项。

`sources` 应填写实际核对过的资料，推荐书名、版次、页码或官方页面标题和完整链接。当前“待A核验”是任务占位，不是已经验证的出处。

## 对存档的影响

修改题目ID、题目文字、类型、选项、正确答案或节点/题目顺序，会保留旧档并重新开始。修改故事、解析、来源、图上位置不影响当前进度。变更节点范围或学习规则前先与B确认。
