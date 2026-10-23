# 布布一二角色表情与动作系统

这一层把论文对话字段转换成可复用的角色姿势。角色固定映射为：

- `female` → `yier`：白色方圆脸、棕色耳朵、粉色脸颊、黑色领结，活泼主讲。
- `male` → `bubu`：焦糖棕色、深棕耳朵、黄色脸颊，温和追问。

这里的动作、短台词和图像都是科研讲解场景的二创设计，不是官方动作、官方台词、官方配音或官方授权声明。动作气泡只承担视觉节奏，不能替代论文证据与字幕；默认不把 `caption_zh` 自动加入配音，避免打断正文断句。

## 文件与运行规则

- 元数据：`assets/characters/manifest.json`
- 图像：`assets/characters/<pose_id>.png`
- 选择器：`scripts/character_library.py`
- 每个角色必须恰好 20 套，共 40 套；`id` 和图像文件名全局唯一。
- `female` 只能使用 `yier_*`，`male` 只能使用 `bubu_*`。显式跨角色 ID 会报错，而不是悄悄换角色。
- 一个 turn 提供 `character_pose` 时显式选择优先；未提供时，按 `dialogue_act`、`emotion` 与 `interaction_tags` 自动选择。
- 自动映射优先处理 `self_correction`、`reverse_question`、`unresolved` 等具体事件，再处理一般情绪。无匹配时使用该角色的中性姿势。
- 目标 PNG 缺失时回落到中性姿势。若中性 PNG 也缺失，选择器仍返回中性元数据并标记 `asset_available: false`，渲染器应跳过角色图层而不是中止论文视频。

## 一二：20 套主讲动作

| # | Pose ID / PNG | 情绪 | 动作 | 默认气泡 | 典型自动触发 |
|---:|---|---|---|---|---|
| 1 | `yier_neutral_intro` | 自然开心 | 面向观众站立，微笑挥手 | 开讲啦！ | `neutral` 或无匹配回落 |
| 2 | `yier_catchphrase_dash` | 元气入场 | 小跑入场，双手左右摆动 | 啊哒哒～ | `claim + excited` |
| 3 | `yier_happy_solution` | 开心 | 双手举起，身体轻轻跃起 | 解出来了！ | `evidence_answer + excited` |
| 4 | `yier_calm_explain` | 从容 | 一手指向图表，一手摊开讲解 | 我们一步一步看。 | `claim/evidence_answer + neutral/reflective` |
| 5 | `yier_curious_tilt` | 好奇 | 歪头前倾，头顶浮现问号 | 咦，为什么呢？ | `challenge/followup + curious + question` |
| 6 | `yier_eyes_sparkle` | 两眼放光 | 星星眼前倾，双手贴近脸颊 | 这个结果太亮眼了！ | `evidence_answer + surprised/excited + surprise` |
| 7 | `yier_serious_focus` | 认真 | 凝神指向关键条件 | 注意这个条件。 | `claim + serious` |
| 8 | `yier_evidence_point` | 笃定 | 用教鞭指向论文红框证据 | 证据在这里。 | `evidence_answer + serious/neutral` |
| 9 | `yier_self_correct` | 谨慎修正 | 挠头冒汗并改正笔记 | 等等，我修正一下。 | `concession + reflective + self_correction` |
| 10 | `yier_surprised_reveal` | 恍然大悟 | 双手张开，头顶出现感叹号 | 原来如此！ | `synthesis + surprised + surprise` |
| 11 | `yier_skeptical_narrow` | 审慎怀疑 | 抱臂半眯眼，审视结论边界 | 这个结论要收窄。 | `challenge/synthesis + skeptical + disagreement` |
| 12 | `yier_thinking` | 思考 | 托腮看向公式，身边浮现省略号 | 让我想一想。 | `followup + reflective` |
| 13 | `yier_excited_discovery` | 兴奋发现 | 跃起并指向关键关系 | 发现关键了！ | `synthesis + excited + surprise` |
| 14 | `yier_confident_summary` | 自信总结 | 叉腰点头，旁边出现勾号 | 结论很清楚。 | `synthesis + neutral/serious` |
| 15 | `yier_gentle_reassure` | 温柔安慰 | 双手合在胸前，微笑安抚 | 别急，慢慢来。 | `evidence_answer + reflective` |
| 16 | `yier_number_check` | 严谨核数 | 拿计算纸与计算器复核数字 | 数字再核一遍。 | `claim/evidence_answer + serious + self_correction` |
| 17 | `yier_term_define` | 清晰定义 | 举起术语卡片并指向定义 | 先定义这个术语。 | `claim + reflective` |
| 18 | `yier_limitation_warn` | 提醒限制 | 举起警示牌并圈出适用边界 | 这里有个限制。 | `challenge/synthesis + serious + unresolved` |
| 19 | `yier_reverse_question` | 反向追问 | 转身向布布伸手发问 | 布布，你怎么看？ | `followup + curious + reverse_question` |
| 20 | `yier_closing_celebrate` | 圆满收尾 | 双手比心后向观众挥手 | 今天就讲到这里！ | `synthesis + excited + concession` |

## 布布：20 套追问动作

| # | Pose ID / PNG | 情绪 | 动作 | 默认气泡 | 典型自动触发 |
|---:|---|---|---|---|---|
| 1 | `bubu_neutral_listen` | 温和聆听 | 双手合起，面向主讲轻轻点头 | 我在听。 | `neutral` 或无匹配回落 |
| 2 | `bubu_warm_greeting` | 温暖问候 | 朝观众微笑挥手 | 大家好。 | `claim + excited` |
| 3 | `bubu_gentle_question` | 礼貌好奇 | 轻轻举手，头顶浮现问号 | 我有个问题。 | `challenge/followup + curious + question` |
| 4 | `bubu_skeptical_probe` | 审慎追问 | 抱臂微抬眉，检查假设 | 这个假设成立吗？ | `challenge + skeptical + question/disagreement` |
| 5 | `bubu_deep_think` | 深入思考 | 托腮凝视公式，身旁浮现思考泡泡 | 让我想想。 | `followup + reflective` |
| 6 | `bubu_calm_answer` | 从容解答 | 一手摊开说明，另一手指向简图 | 可以这样理解。 | `evidence_answer + neutral/reflective` |
| 7 | `bubu_eyes_sparkle` | 两眼放光 | 星星眼举起关键结果页 | 这个思路很妙！ | `evidence_answer/synthesis + excited + surprise` |
| 8 | `bubu_surprised` | 惊讶 | 身体微微后仰，头顶出现感叹号 | 原来是这样！ | `concession + surprised + surprise` |
| 9 | `bubu_concede` | 认可证据 | 认真点头，双手合起 | 这个证据我接受。 | `concession + neutral/reflective + concession` |
| 10 | `bubu_followup` | 继续追问 | 身体前倾，竖起一根手指 | 那再追问一步。 | `followup + curious/serious + question` |
| 11 | `bubu_baseline_check` | 检查基线 | 拿起两列表格对照基线设置 | 基线公平吗？ | `challenge + serious + question` |
| 12 | `bubu_sample_check` | 检查样本 | 用放大镜查看样本数字 | 样本量够吗？ | `challenge + skeptical + question/unresolved` |
| 13 | `bubu_method_challenge` | 追问方法 | 指向方法流程图中的关键箭头 | 关键机制在哪？ | `challenge + serious + disagreement` |
| 14 | `bubu_data_doubt` | 质疑数据 | 拿着波动曲线图，皱眉看异常点 | 波动怎么解释？ | `challenge/followup + skeptical + unresolved` |
| 15 | `bubu_limitation_warn` | 提醒局限 | 举起警示牌并指向限制条目 | 别忽略这个限制。 | `challenge/synthesis + serious + unresolved` |
| 16 | `bubu_generalization` | 思考推广 | 从论文图指向外部场景与小地球 | 还能推广吗？ | `followup + reflective + unresolved` |
| 17 | `bubu_replication_check` | 检查复现 | 对照两份实验记录并打上问号 | 能复现吗？ | `challenge + reflective + unresolved` |
| 18 | `bubu_amused` | 会心一笑 | 捂嘴轻笑并点头 | 这下说通了。 | `concession + excited + concession` |
| 19 | `bubu_encouragement` | 鼓励 | 握拳加油，身体微微前倾 | 继续，我们快到了。 | `evidence_answer + excited` |
| 20 | `bubu_conclusion` | 稳妥收束 | 竖起拇指，另一手压住结论卡片 | 结论收稳了。 | `synthesis + neutral/serious` |

## Dialogue JSON 示例

显式指定姿势，适合需要精确分镜的关键句：

```json
{
  "speaker": "female",
  "dialogue_act": "evidence_answer",
  "emotion": "excited",
  "interaction_tags": ["surprise"],
  "character_pose": "yier_eyes_sparkle",
  "zh_text": "看 Figure 3，提升集中在低资源设置。"
}
```

不写 `character_pose` 时自动选择，适合批量生成：

```json
{
  "speaker": "male",
  "dialogue_act": "challenge",
  "emotion": "skeptical",
  "interaction_tags": ["question", "unresolved"],
  "question_target": "测试集是否与训练集共享数据来源",
  "zh_text": "这个划分真的排除了数据泄漏吗？"
}
```

最小 Python 接入：

```python
from scripts.character_library import CharacterLibrary

characters = CharacterLibrary.from_file()
pose = characters.select_pose(turn["speaker"], turn)
if pose["asset_available"]:
    overlay_png(pose["asset_path"])
draw_action_caption(pose["caption_zh"])
```

调试或只检查语义映射时，可以传 `require_asset=False`；正式渲染应保留默认值，让缺图回落机制生效。渲染报告建议保存 `id`、`requested_pose_id`、`selected_by`、`used_fallback` 与 `asset_available`，便于定位错配和缺失素材。
