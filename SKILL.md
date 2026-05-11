---
name: car-tool
description: 清洁小车任务下发助手。根据用户清扫需求，从39个可清扫区域中选择目标区域并生成清扫任务指令。当用户提到清扫、打扫、清洁小车、任务下发、区域清扫等关键词时使用此skill。支持通过地点检索指定清扫目标，生成带POI标记的地图截图，并使用视觉模型分析地图确定清扫区域。特别注意：大部分清扫地点位于五缘湾区域，系统会首先验证用户请求的地点是否在预定义的39个可清扫区域内。
compatibility:
---

# 清洁小车任务下发助手

**核心限制**：只能使用 `poi_search.js`、`map_screenshot.py`、`visualize_regions.py`、`match_region.py`、`session_manager.py` 和 `preset_scripts.py` 六个脚本，**不得创建任何额外脚本文件**。

## 工作流程概述

```
用户输入
↓
[步骤0] ⚠️ 会话初始化——区分三种情况：
  情况A — 新用户请求（全新的任务）：运行 `session_manager.py start`
  → 创建新日期目录 + session1，如 260507xxxx/session1
  情况B — 同一次请求的多个子任务（如"打扫A到B，再打扫C到D"）：
    1. 先 `start` 创建日期目录 + session1，分配给子任务1
    2. 再 `next` 创建 session2/3/... 分配给子任务2/3...
    → 所有子任务共享同一日期目录，各自有独立的 session 目录
  情况C — 用户修改当前任务（说"修改"/"重做"/"不对"/"重新来"）：
  → `session_manager.py next` 在当前日期目录下创建下一个子会话
  - SESSION_PATH = 子会话路径（保存该任务的**所有文件**：POI JSON、地图截图 PNG、**task_params.json**、**index.html**）
  - SESSION_DIR = 总会话/日期目录路径（仅用于组织子会话，**不再存放最终结果文件**）
  - ⚠️ **重要：全新的用户请求（不同时间、不同任务）必须用 `start`，不能用 `next` 追加到旧任务目录**
  - ⚠️ **每个任务独立输出**：任务1→session1(端口8001)，任务2→session2(端口8002)，依次递增
↓
[步骤1] 识别任务类型：两点路径 / 多点路径 / 厕所相关 / 单点周围 / 多点组合
↓
[步骤1.5] ⚠️ 任务连接词解析（区分路径连接与并列列举）
↓
[步骤2] ⚠️ 关键分支点——对每个地点执行向量数据库查询

  **操作流程：**
  ① 从用户输入中提取所有地点名称
  ② 对**每一个**地点运行 `preset_scripts.py query "<地名>"`，记录结果
  ③ 根据查询结果分流，共三种情况：

  | 情况 | 条件 | 后续流程 |
  |------|------|---------|
  | **A) 全部已知** | 所有地点 `found: true` | **跳转至步骤7**，跳过步骤3-6 |
  | **B) 全部未知** | 所有地点 `found: false` | 步骤3-6 对所有地点执行 |
  | **C) 部分已知** | 既有 `found: true` 也有 `found: false` | 对未知地点执行步骤3-6；已知地点**跳过搜索/打点/截图** |

  ⚠️ **CRITICAL：只要 `found: true`（在向量库中），禁止搜索、禁止打点、禁止截图、禁止任何POI文件**

  ```bash
  # 情况A — 全部已知（如"打扫64号楼到爱情湾"）
  python scripts/preset_scripts.py query "64号楼"
  # → 查询结果: 64号楼 → 区域: R2  (found: true)
  python scripts/preset_scripts.py query "爱情湾"
  # → 查询结果: 爱情湾 → 区域: R6,R7  (found: true)
  ```
  # 情况B — 全部未知（如"打扫花溪到凉亭"）
  python scripts/preset_scripts.py query "花溪"
  # → 未知地标: 花溪  (found: false)
  python scripts/preset_scripts.py query "凉亭"
  # → 未知地标: 凉亭  (found: false)
  # → 全部 found: false → 情况B，对所有地点执行步骤3-6

  # 情况C — 部分已知（如"打扫西门到凉亭"）
  python scripts/preset_scripts.py query "西门"
  # → 查询结果: 西门 → 区域: R1  (found: true)  ← 已知
  python scripts/preset_scripts.py query "凉亭"
  # → 未知地标: 凉亭  (found: false)              ← 未知
  # → 混合 → 情况C：西门已知→不动，只对凉亭执行步骤3-6
  ```

  ⚠️ **CRITICAL——向量数据库结果有效性判断（MUST DO）：**
  `found: true` **不等于**结果一定正确！向量数据库可能返回"近似但无关"的结果
  （例如：搜索"花溪"→ 返回"爱情湾"；搜索"凉亭"→ 返回"休息亭"）。
  
  **必须**将查询返回的地标名称与用户输入进行文本对比，满足以下条件才算真正命中：
  - 返回名称与用户输入**包含相同的关键字**（如"64号楼"/"64号楼"、"爱情湾"/"爱情湾"）
  - 或为已知的同义表达（如"日圆大桥旁边厕所"/"日圆大桥旁厕所"）
  
  **判定规则**：
  | 对比结果 | 处理方式 |
  |---------|---------|
  | 名称**大致相符** | 确认 found: true，跳步骤7 |
  | 名称**明显不符**（无共享关键字、语义不同） | ⚠️ 视为 found: false，必须执行步骤3搜索坐标 |
  
  **反例**：搜索"花溪"→ 返回"爱情湾"(found:true) → 名称无共享关键字 → **视为 found: false**

  ↓ 情况A → 直接跳到步骤7（规划路径+验证）
  ↓ 情况B/C → 继续步骤3（仅对未知地点操作）

↓ 分支A：全部已知 → 直接跳步骤7（规划路径+验证）
↓ 分支B：含未知地标 → 继续步骤3

[步骤3] 获取坐标（⚠️ 仅对未知地标）：调用 poi_search.js，使用预设搜索关键词
  - 已知地标绝对不要搜索——已从向量库获得区域编号，无需任何操作
↓
[步骤3.5] ⚠️ POI搜索失败处理——地标完全未找到
  如果向量数据库未命中 **且** POI搜索也未找到该地标（无结果或结果明显不相关）：
  - **有其他任务** → 跳过当前无法处理的任务，继续处理下一个任务，并在最终输出中说明"未找到地标'XXX'，已跳过"
  - **无其他任务** → 直接反馈用户"未找到地标'XXX'，无法生成清扫任务。请确认地点名称是否正确或提供更多信息"
  - ⚠️ **禁止**：强行使用不相关的结果凑合生成任务
↓
[步骤4] 只对POI搜索获得坐标的未知地标执行 match_region.py（⚠️ 必须先算后看）
↓
[步骤5] 生成截图（⚠️ 仅当存在未知地标时）：调用 map_screenshot.py
  - POI数组中**只包含未知地标的坐标**，不含已知地标
  - 已知地标不需要POI标记——已有区域编号，不要创建它们的POI文件
↓
[步骤6] 视觉分析确认未知poi的区域（Rxx）——⚠️ 必须预填已知地标：告知视觉模型已知区域，仅确认未知POI
↓
[步骤7] （规划路径 + 验证相邻性）->（调用视觉模型）：
  - 如果是两点路径 → 规划起点到终点的最短连续路径
  - 如果是多点路径 → 规划每对前后必经点之间的路径，逐段验证相邻性
  - 如果地标是已知，那么使用预设的区域编号，不要让视觉模型重新识别，直接将这些区域编号纳入路径规划，让视觉模型规划路径
  - 如果地标是未知，那么先用视觉模型确认它的区域编号，再纳入路径规划
  - 如果地标有的已知有的未知，那么已知的直接用区域编号，未知的先视觉确认区域编号，再一起规划路径
↓
[步骤8] 保存 task_params.json 到 **SESSION_PATH**（每个任务独立的 session 目录）

  ⚠️ **重要：每个任务独立保存各自的 task_params.json**
  - 任务1 → `SESSION_DIR/session1/task_params.json`
  - 任务2 → `SESSION_DIR/session2/task_params.json`
  - **不再**将所有任务合并到一个 task_params.json 中

↓
[步骤9] 生成交互式可视地图（visualize_regions.py）→ 保存到 **SESSION_PATH**（每个任务独立）

  ⚠️ **每个任务独立调用 visualize_regions.py，使用不同端口**
  - 任务1（session1）→ `--port 8001 --output-dir SESSION_PATH`
  - 任务2（session2）→ `--port 8002 --output-dir SESSION_PATH`
  - 后续任务依次递增端口号
  - 每个任务处理完后**立即调用** visualize_regions.py，无需等待所有任务完成
  - **端口复用**：如果端口已被占用，脚本会自动回退到可用端口，以实际输出为准

↓
[步骤10] 输出中文说明 + 各任务的HTTP链接
  - 每个任务单独输出一条，格式：`任务N：从{起点}到{终点}，清扫区域为{区域列表}号路线。点击 {HTTP地址} 可查看地图详情。`
  - 如有任务被跳过（地标未找到），在末尾说明
```

---

## ⚠️ 一、任务连接词解析（CRITICAL——必须正确区分）

用户使用不同的中文连接词表达不同意图，**错误解析会导致完全不同的输出**。

### 路径连接词（表示连续清扫路径）
- "到"、"至"、"→"、"从A到B"
- 示例："打扫凉亭到cafe" → R37→R36→R35 连续路径

### 并列连接词（表示各自独立清扫，**禁止规划连接路径**）
- **"以及"、"和"、"跟"、"与"、"还有"、"连同"**
- ⚠️ **"A以及B" ≠ "A到B"！** 前者是两个独立清扫目标，后者是一条路径
- 示例："打扫日圆大桥以及他旁边的厕所" → R38独立清扫 + R15独立清扫

### 顺序连接词（表示多个独立任务，按顺序执行）
- "再去"、"然后"、"接着"、"最后"、"再打扫"
- 每个任务独立规划路径，**不包含任务之间的转场过渡区域**
- 示例："打扫凉亭到cafe，再打扫花溪到休息平台" → 任务1 + 任务2，各自独立

---

## ⚠️ 二、已知地标查询（通过 preset_scripts.py 查向量数据库）

**使用原则**：所有已知地标的区域编号已存入向量数据库。用户提及地标时，**一律通过 `preset_scripts.py query` 查询，无需POI搜索、无需视觉定位**。

```bash
cd C:/Users/18325/.claude/skills/car_tool
python scripts/preset_scripts.py query "地标名称"
```

- 返回 `found: true` + 区域编号 → 直接使用，标记为"已知地标"
- 返回 `found: false` → 该地标不在向量库中，需要POI搜索+视觉确认

### 厕所预设映射说明

以下厕所位置已通过历史验证存入向量库。用户提及厕所时，**先通过 `preset_scripts.py query` 查询**，禁止直接搜索坐标/截图/视觉识别灰色图标：

| 用户提及的参考地标 | 厕所区域 | 建议查询关键词 |
|------------------|---------|--------------|
| 27号楼厕所、8号楼厕所 | **R18、R19** | "27号楼厕所"、"8号楼厕所" |
| 禾美社区居委会/日圆大桥旁厕所 | **R15** | "日圆大桥旁厕所"、"禾美社区居委会" |
| 地圆桥/休息亭旁厕所 | **R33** | "地圆桥旁厕所"、"休息亭旁厕所" |

仅当查询返回 `found: false` 时，才回退到POI搜索+视觉识别灰色厕所图标的流程。

### 需POI搜索的常见地标及预设关键词

以下地标**不在向量库中**，必须通过POI搜索获取坐标。**必须使用预设关键词，不要直接使用用户输入**。

| 用户表述 | 预设搜索关键词 | 说明 |
|---------|---------------|------|
| "感恩广场入口" | **"五缘湾感恩广场(入口)"** | 必须含括号，不能简化为"感恩广场" |
| "步道广场入口" | **"五缘步道广场1号入口"** | 必须含"1号" |
| "感恩广场"（不带入口） | **"五缘湾感恩广场"** | |
| "步道广场"（不带入口） | **"五缘步道广场"** | |
| "工会驿站"（参考图上已显示，但搜索用全称） | **"福建工会驿站(厦门工会爱心驿站)"** | |
| "健身驿站" | **"健身驿站"** | |
| "休闲平台"/"休息厅" | **"休闲平台"** | 用户易混淆 |
| "休息亭" | **"五缘湾湿地公园-休息亭"** | 与休闲平台不同 |
| "停车场"/"停车出入口" | **"停车场(出入口)"** | |
| "花溪" | **"五缘湾湿地公园-花溪"** | |
| "天鹅湖"/"咖啡" | **"SWAN LAKE CAFE"** | |
| "凉亭" | **"五缘湾湿地公园-凉亭"** | |
| "爱情湾" | **"中国第一爱情湾"** | |
| "游泳馆" | **"五缘湾 游泳馆"** | |

---

## ⚠️ 三、核心操作规则（MUST——贯穿所有场景）

### 规则1：已知地标免视觉定位（CRITICAL）

**向视觉模型发送提示词时，必须先将已知地标的区域编号写入提示词**，明确告知"这些地标的区域已确定，无需在地图上定位"，仅让视觉模型确认POI蓝色标记所在区域。

**正例提示词**：
```
以下地标的区域编号已根据预设数据确定（无需在地图上定位）：
- 22号楼 → R12, 23号楼 → R11, 爱情湾 → R6/R7, 工会驿站 → R23

需要在地图上确认的POI标记：
- SWAN LAKE CAFE（蓝色标记点）

请确认SWAN LAKE CAFE所在的区域编号，然后规划连接所有区域的最优清扫路径。
```

**反例（禁止）**：让视觉模型去识别22号楼、爱情湾、工会驿站等的区域——这些在向量库中已有确定编号。

### 规则2：先算后看（CRITICAL——坐标匹配优先于视觉估算）

**只要有POI坐标，就必须先用 match_region.py 计算与39个区域中心的距离**，确定候选区域后再用视觉验证。**禁止跳过坐标计算直接进行视觉估算**。

```bash
cd C:/Users/18325/.claude/skills/car_tool
python scripts/match_region.py 118.17256 24.516191 "休息亭"
# 或批量：python scripts/match_region.py --poi-file SESSION_PATH/poi.json --top 3
```

距离阈值参考：
- < 50m → 高度确信，可直接确定
- 50-150m → 可能在附近区域，需视觉确认
- > 150m → 不太可能匹配，应选更近候选

### 规则3：颜色识别

在地图截图上，**必须正确区分**：
- **红色编号区域** = 可清扫路段（1-39号路），这是**清扫目标**
- **黑色文字** = 建筑物/地标标签（如"64号楼"），只是**参考点**，不是清扫区域
- **蓝色圆点** = POI搜索标记
- **灰色小图标** = 厕所位置

⚠️ **楼号≠区域号**："64号楼"的清扫目标是它旁边红色的**2号路**，不是区域64。

### 规则4：路径规划（⚠️ 视觉分析）

- **最少区域原则**：两点间默认选最短路径。如果用户要求"经过爱情湾"，则必须规划经过爱情湾的路径，即使它不是最短的。
- **逐对验证相邻性**：每对前后区域必须地理相邻，不能跳跃
- **路径顺序**：regions数组必须从起点到终点排列
- **多点路径分段**：3个及以上必经点时，拆分为子段逐段规划

### 规则5：文件保存

- **所有文件**（POI JSON、截图PNG、task_params.json、index.html）→ **SESSION_PATH**（任务各自的 session 目录）
- SESSION_DIR 仅作为日期目录，用于组织多个 session 子目录
- **所有生成文件永久保留，禁止删除**

### 规则6：visualize_regions.py 调用（CRITICAL——每个任务独立调用，不同端口）

**每个任务处理完成后立即调用 visualize_regions.py，不再等待所有任务收集完再统一调用。**

正确方式：
```bash
# 任务1（session1）→ 端口 8001
python scripts/visualize_regions.py --no-open --port 8001 --output-dir SESSION_DIR/session1 --tasks '[{"name":"任务1名称","regions":[1,2,3,4,5]}]'

# 任务2（session2）→ 端口 8002
python scripts/visualize_regions.py --no-open --port 8002 --output-dir SESSION_DIR/session2 --tasks '[{"name":"任务2名称","regions":[10,11,12]}]'
```

端口规则：
- 任务1 → 8001，任务2 → 8002，任务3 → 8003，依次递增
- 如果指定端口被占用，脚本会自动回退到可用端口，以脚本实际打印的 HTTP 地址为准

---

## 工具说明

### 1. POI搜索 (poi_search.js)

```bash
cd C:/Users/18325/.claude/skills/car_tool
node scripts/poi_search.js "关键词"
```

返回搜索结果，提取坐标信息。**必须使用"需POI搜索的常见地标"表中的预设关键词**，不要直接使用用户输入。

### 2. 坐标匹配 (match_region.py)

```bash
cd C:/Users/18325/.claude/skills/car_tool
python scripts/match_region.py 118.17256 24.516191 "POI名称"
python scripts/match_region.py --poi-file SESSION_PATH/poi.json --top 3  # 批量
```

根据POI坐标计算最近的清扫区域编号，输出Top N候选区域。

### 3. 地图截图 (map_screenshot.py)

```bash
cd C:/Users/18325/.claude/skills/car_tool
python scripts/map_screenshot.py --poi-file SESSION_PATH/poi.json --screenshot-path SESSION_PATH/map.png --html-output-dir SESSION_PATH
```

生成包含POI标记和39个可清扫区域的地图截图。

⚠️ **POI JSON 字段要求**：
```json
[
  {"name": "花溪", "position": [118.172453, 24.515147]},
  {"name": "凉亭", "position": [118.175938, 24.519453]}
]
```
- 必须是**直接数组格式**（不是 `{"pois": [...]}` 嵌套对象）
- **必须使用 `"position": [经度, 纬度]` 格式**，禁止使用 `"lng"/"lat"` 或 `"lon"/"lat"` 等独立字段名——脚本只识别 `position` 或 `center` 字段，否则 POI 会回退到 `[0,0]` 导致标记不显示

地图范围固定使用 `scripts/config.json` 中的bounds配置，不受POI位置影响。

### 4. 交互式可视化 (visualize_regions.py)

```bash
cd C:/Users/18325/.claude/skills/car_tool
# 单任务（默认端口8001）：
python scripts/visualize_regions.py 1 2 3 --no-open --output-dir SESSION_PATH

# 多任务各自独立调用（不同端口）：
# 任务1 → 端口8001
python scripts/visualize_regions.py --no-open --port 8001 --output-dir SESSION_DIR/session1 --tasks '[{"name":"任务1","regions":[23,24,25,26,27]}]'
# 任务2 → 端口8002
python scripts/visualize_regions.py --no-open --port 8002 --output-dir SESSION_DIR/session2 --tasks '[{"name":"任务2","regions":[15,14,13,12,11,10,7]}]'
```

**重要**：
- 区域编号直接使用1-based（1-39），脚本自动转换
- `--tasks` 中 regions 数组的**顺序必须从起点到终点排列**
- 记录脚本**实际打印的HTTP地址**（端口可能回退），不要硬编码
- 使用 `--output-dir SESSION_PATH` 保存到任务各自的 session 目录
- `--port` 从 8001 开始，每个任务递增（8001, 8002, 8003...）

#### 交互式面板布局（2026-05-09 新增）

生成的交互页面右侧面板采用**按任务分组 + 其他区域**布局：

```
● 海水浴场到cafe  3/3个区域
  [✓] Region32 (32)  [✓] Region33 (33)  [✓] Region36 (36)

● 其他区域  0/36个区域
  ▶ 未选中 (36)
    [ ] Region1 (1)  [ ] Region2 (2)  ...  [ ] Region39 (39)
```

- **每个任务独立卡片**，头部分组名 + 选中数目（如 `3/3个区域`）
- **"其他区域"卡片**（在所有任务卡片下方）包含全部不在任何任务路径中的区域（如：初始只有任务路径上的3个区域，其余36个在"其他区域"中）
- 已选中区域始终展开显示，每个区域显示为 **方块复选框 + 色点 + 名称(编号)** 的紧凑标签
- **未选中区域**折叠在 `▶ 未选中 (N)` 后，点击展开（▶变▼），再点击收起
- ☑ **任务默认区域**（深蓝色 #00008B）→ 地图上该区域多边形显示为深蓝色、标号高亮（深蓝底），**颜色与所属任务统一**
- ☑ **用户额外选中区域**（浅蓝色 #ADD8E6）→ 从"其他区域"手动勾选的区域显示为浅蓝色，与默认任务区域区分
- ☐ **未选中**（灰色）→ 地图多边形变灰、标号变灰（色圆变灰但仍可见）
- 点击复选框或点击地图上的多边形，均可切换选中状态
- 切换后未选中的**自动移至折叠区**，选中的自动展开到上方
- 点击 **▶ 确认执行** 后：所有已选区域（包括默认深蓝和浅蓝）**统一变为深蓝色**（#00008B）
- **同一任务内所有选中区域颜色统一**（`getTaskColor()` 确保单任务场景全部使用任务色，多任务场景按所属任务分配）

#### 实时同步 task_params.json

每次切换复选框自动 `POST /api/toggle_region` 同步到 `task_params.json`：
- **请求体格式**：`{"region_id": 0, "selected": true, "task_index": 0}`
- **同步范围**：同时更新顶层 `selected_regions` AND 对应任务 `tasks[task_index].selected_regions` AND `tasks[task_index].regions[]` 中该区域的 status（选中→status=1，取消→从regions中移除）
- **任务归属逻辑**：`findTaskIndexForRegion()` 判断区域属于哪个任务
  - 在任务路径内的区域 → 归该任务
  - 不在任何任务中的区域（即"其他区域"的） → 归第一个任务（index 0）
- **勾选** → `selected_regions` 中添加该区域ID并排序，`regions` 中添加 `{"id": N, "status": 1}`
- **取消勾选** → 从 `selected_regions` 中移除，从 `regions` 中移除
- `selected_count` 自动更新
- 文件不存在时自动创建基础结构

#### 确认执行按钮（可重按）

点击 **▶ 确认执行** 按钮后：
1. 收集当前所有任务的选中区域状态（调用 `collectSelectedData()`）
2. `POST /api/confirm` 发送完整 payload：`{"tasks": [{"id":"...", "name":"...", "regions":[{"id":N,"status":1},...], "selected_regions":[...]}], "selected_regions": [...], "selected_count": N}`
3. 服务器写入 `task_params.json`（覆盖 `tasks`、`selected_regions`、`selected_count`，设置 `execution_confirmed: true` + 时间戳；所有区域的 status 保持为 1）
4. 按钮变为 **✓ 已确认执行**，状态栏显示 **✔ 已同步于 HH:MM:SS** + **↻ 重做** 链接
5. 点击 **↻ 重做** → 按钮恢复为 **▶ 确认执行**，可重新调整区域选择后再次确认

#### 服务器API端点

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/confirm` | 确认执行（接受完整 tasks/selected_regions payload），写入 `execution_confirmed: true` |
| GET  | `/api/confirm` | 查询是否已确认执行 |
| POST | `/api/toggle_region` | 切换区域选中状态（body: `{"region_id": N, "selected": true, "task_index": 0}`），同步更新 `selected_regions` + `tasks[task_index].selected_regions` + `tasks[task_index].regions[]`（添加/移除 `{"id":N, "status":1}`） |

### 5. 已知地标查询 (preset_scripts.py)

```bash
cd C:/Users/18325/.claude/skills/car_tool
python scripts/preset_scripts.py query "64号楼"
# 输出：
# 查询结果: 64号楼 → 区域: R2
# JSON: {"name": "64号楼", "regions": ["R2"], "found": true}
```

根据用户输入的地名，查询向量数据库是否包含该地标的区域编号。**这是步骤2的关键查询工具**，用于区分已知/未知地标。

```bash
python scripts/preset_scripts.py seed [--reload]  # 重新播种数据到向量库（首次使用前需执行一次）
```

### 6. 会话管理 (session_manager.py)

```bash
cd C:/Users/18325/.claude/skills/car-tool
python scripts/session_manager.py start   # 新用户请求 → 新建日期目录 + session1
python scripts/session_manager.py next    # 同一请求内下一个子任务，或用户要求修改当前任务
python scripts/session_manager.py current # 查看当前会话路径
```

**⚠️ 使用规则（CRITICAL——必须区分三种场景）：**

| 场景 | 命令 | 示例 |
|------|------|------|
| **A: 全新的用户请求**（不同时间、不同任务的用户消息） | `start` | 用户说"打扫凉亭到cafe" → 创建 `260507xxxx/session1` |
| **B: 同一次请求的多个子任务**（"以及"/"再"/"然后"连接的多个清扫段） | 先 `start` 给子任务1，再 `next` 给子任务2/3... | "打扫A到B，再打扫C到D" → 子任务1=`session1`，子任务2=`session2`，共用一个日期目录 |
| **C: 用户要求修改当前任务**（说"修改"/"重做"/"不对"/"重新来"） | `next` | 用户说"不对，换一个路线" → `session1`→`session2` |

**场景B 执行示例**（"打扫西门到凉亭，再打扫工会到8号楼"）：
```bash
# 第1步：start 创建日期目录 + session1 给子任务1
python scripts/session_manager.py start
# → 2605070955_09/session1（用于西门到凉亭的所有文件）
# → SESSION_PATH = .../session1, SESSION_DIR = .../2605070955_09

# ... 处理子任务1（西门到凉亭）→ 保存到 session1/ → visualize port 8001 ...

# 第2步：next 创建 session2 给子任务2
python scripts/session_manager.py next
# → 2605070955_09/session2（用于工会到8号楼的所有文件）
# → SESSION_PATH = .../session2, SESSION_DIR 不变

# ... 处理子任务2 → 保存到 session2/ → visualize port 8002 ...
# 最终每个 session 各自包含 task_params.json + index.html
```

---

## 详细场景执行

### 场景A：两点路径清扫

**示例**："打扫花溪到凉亭路段"

1. **地点分类**（运行 preset_scripts.py query）：花溪→`found: false`；凉亭→`found: false` → 均需POI搜索
2. **POI搜索**：搜索"五缘湾湿地公园-花溪"和"五缘湾湿地公园-凉亭"，获取坐标
3. **坐标匹配**：用match_region.py计算候选区域
4. **生成截图**：创建POI数组JSON，调用map_screenshot.py
5. **视觉分析**（⚠️ 应用规则1）：此场景无已知地标，让视觉模型确认两个POI蓝色标记所在区域，然后规划最短连续路径
6. **保存结果**：task_params.json保存到SESSION_PATH
7. **生成可视化**：调用visualize_regions.py，使用视觉分析确定的区域编号
8. **输出**：中文说明 + HTTP链接

### 场景B：多点路径清扫（含途经点）

**示例**："打扫日圆大桥旁边厕所到地圆桥旁边厕所，要求经过爱情湾"

1. **地点分类**（使用 preset_scripts.py query 查询）：
   - `query "日圆大桥旁边厕所"` → **R15**（已知地标）
   - `query "爱情湾"` → **R6、R7**（已知地标）
   - `query "地圆桥旁边厕所"` → **R33**（已知地标）
2. **所有地点均为已知** → 无需POI搜索、无需截图
3. **视觉分析**（⚠️ 仅用于规划路径）：预填所有已知区域，让视觉模型规划 R15→R7→R33 的连续路径
4. **逐段验证**：R15→...→R7→...→R33 必须逐对相邻
5. 保存结果 + 生成可视化 + 输出

### 场景C：连续任务（多段独立清扫）

**示例**："打扫凉亭到cafe，再打扫花溪到休闲平台"

1. **识别为连续任务**（"再"分隔）→ 2个独立子任务，各自分配session
2. **子任务1（session1）**：凉亭（需POI）→ SWAN LAKE CAFE（需POI）→ 含未知地标，走分支B（搜索→截图→视觉确认），规划 R37→R36→R35
3. **子任务2（session2）**：花溪（需POI）→ 休闲平台（query返回R30）→ 含未知地标，走分支B
4. **不包含任务间转场区域**
5. **各自独立输出**：任务1 → session1/task_params.json + 端口8001；任务2 → session2/task_params.json + 端口8002

**输出示例**：
```
任务1：从凉亭(37号路)到cafe(35号路)，经过36号路。清扫区域为35,36,37号路线，点击 http://127.0.0.1:8001/index.html 可查看地图详情。
任务2：从花溪(32号路)到休闲平台(30号路)，经过31号路。清扫区域为30,31,32号路线，点击 http://127.0.0.1:8002/index.html 可查看地图详情。
```

**示例2**："打扫西门到凉亭，再打扫工会到8号楼"

1. **识别为连续任务**（"再"分隔）→ 2个独立子任务
2. **子任务1（session1，端口8001）**：西门（query返回R1）→ 凉亭（需POI搜索）→ **含未知地标**，走分支B
   - 搜索→截图→视觉确认→规划路径→保存 session1/task_params.json → visualize port 8001
3. **子任务2（session2，端口8002）**：工会（query返回R23）→ 8号楼（query返回R18/R19）→ ⚠️ **全部已知地标！走分支A，跳过POI搜索和截图**

   | 子任务2流程 |
   |-----------|
   | 查询向量库：R23（工会）+ R18/R19（8号楼），已确定全部区域编号 |
   | **无需POI搜索、无需创建POI文件、无需match_region、无需截图** |
   | 直接进入步骤7-10：规划最优路径 R23→R24→R25→R26→R27→R28→R29→R18→R19 |
   | 保存 session2/task_params.json → visualize port 8002 → 输出 |

### 场景D：多点组合清扫（并列连接）

**示例**："打扫日圆大桥以及他旁边的厕所，最后打扫下工会驿站"

1. **识别并列连接**（"以及"）→ 日圆大桥和厕所各自独立
2. 日圆大桥 → query返回 **R38**
3. 厕所 → query返回 **R15**
4. 工会驿站 → query返回 **R23**
5. **禁止规划R38→R15或R15→R23的连接路径**，每个区域独立清扫
6. 输出：task_type = "combo_cleaning"，selected_regions: [38, 15, 23]

### 场景E：厕所相关清扫

**示例**："清扫日圆大桥旁边厕所附近的区域"

1. 使用 preset_scripts.py query 查询向量库 → 日圆大桥旁边厕所 = **R15**（直接使用）
2. 直接输出R15及相邻区域，**无需搜索、无需截图、无需视觉识别**
3. 仅当查询返回 `found: false` 时，才搜索附近地标→截图→视觉识别灰色厕所图标

---

## 输出格式

### 两点路径
```json
{
  "status": "success",
  "task_id": "task_YYYYMMDD_NNN",
  "user_prompt": "用户原始输入",
  "start_point": {"name": "起点", "nearest_region": 1},
  "end_point": {"name": "终点", "nearest_region": 10},
  "tasks": [
    {
      "id": "2605111430_session1",
      "name": "起点到终点",
      "regions": [
        {"id": 1, "status": 1},
        {"id": 2, "status": 1},
        {"id": 3, "status": 1},
        {"id": 4, "status": 1},
        {"id": 5, "status": 1}
      ],
      "color": "#00008B",
      "selected_regions": [1, 2, 3, 4, 5]
    }
  ],
  "selected_regions": [1, 2, 3, 4, 5],
  "total_regions": 39, "selected_count": 5
}
```

### 连续任务（"再去"/"然后"连接）
⚠️ **每个子任务独立保存各自的 task_params.json**，不使用合并格式。子任务1保存在 session1/task_params.json，子任务2保存在 session2/task_params.json，各子任务使用上述"两点路径"或"多点路径"格式。selected_regions 仅包含该任务的清扫区域，**不包含任务间转场过渡区域**。

### 多点组合清扫（"以及"/"和"连接）
```json
{
  "status": "success",
  "task_type": "combo_cleaning",
  "tasks": [
    {
      "id": "2605111430_session1",
      "name": "多点组合清扫",
      "regions": [
        {"id": 38, "status": 1},
        {"id": 15, "status": 1}
      ],
      "color": "#00008B",
      "selected_regions": [38, 15]
    }
  ],
  "cleaning_targets": [
    {"name": "日圆大桥", "region": 38, "source": "向量数据库查询"},
    {"name": "日圆大桥旁边厕所", "region": 15, "source": "向量数据库查询"}
  ],
  "selected_regions": [38, 15],
  "total_regions": 39, "selected_count": 2
}
```

### 多点路径（一次性描述完整路径）
```json
{
  "status": "success",
  "start_point": {"name": "起点", "nearest_region": 38},
  "waypoints": [{"name": "途经点", "nearest_region": 7}],
  "end_points": [{"name": "终点", "nearest_region": 37}],
  "tasks": [
    {
      "id": "2605111430_session1",
      "name": "多点路径",
      "regions": [
        {"id": 38, "status": 1},
        {"id": 10, "status": 1},
        {"id": 7, "status": 1},
        {"id": 39, "status": 1},
        {"id": 32, "status": 1},
        {"id": 34, "status": 1},
        {"id": 35, "status": 1},
        {"id": 37, "status": 1}
      ],
      "color": "#00008B",
      "selected_regions": [38, 10, 7, 39, 32, 34, 35, 37]
    }
  ],
  "route_segments": [
    {"from": 38, "to": 7, "regions": [38, 10, 7]},
    {"from": 7, "to": 37, "regions": [7, 39, 32, 34, 35, 37]}
  ],
  "selected_regions": [38, 10, 7, 39, 32, 34, 35, 37],
  "total_regions": 39, "selected_count": 8
}
```

### task_params.json（保存到 SESSION_PATH，每个任务独立）

```json
{
  "task_id": "task_YYYYMMDD_NNN",
  "user_prompt": "打扫海水浴场到cafe",
  "task_type": "path_cleaning",
  "tasks": [
    {
      "id": "2605111430_session1",
      "name": "海水浴场到cafe",
      "regions": [
        {"id": 32, "status": 1},
        {"id": 33, "status": 1},
        {"id": 36, "status": 1}
      ],
      "color": "#00008B",
      "selected_regions": [32, 33, 36]
    }
  ],
  "selected_regions": [32, 33, 36],
  "total_regions": 39,
  "selected_count": 3,
  "execution_confirmed": false,
  "confirmed_at": ""
}
```

**字段说明**：
- `tasks[].id`：任务唯一标识，格式 `{时间戳}_{sessionXX}`，如 `2605111430_session1`（YYMMDDHHMM+session编号）
- `tasks[].regions`：不再是简单数字数组，每个区域为对象 `{"id": 区域编号, "status": 状态码}`
- **区域状态码（status）**：
  | 状态码 | 含义 | 地图显示颜色 |
  |-------|------|------------|
  | `1` | 未打扫 | 深蓝色（#00008B） |
  | `2` | 已打扫 | 深绿色（#006400） |
  | `3` | 打扫中 | 深红色（#8B0000） |
- 初始生成时所有区域 status 默认为 `1`（未打扫）
- `tasks[].color`：任务主色调，默认为深蓝色 `#00008B`
- `tasks[].selected_regions` 是该任务实际清扫的区域（包含路径区域 + 用户从"其他区域"额外勾选的区域）
- 每个 task_params.json 仅包含单个任务，保存在对应的 session 目录中

### 交互页面颜色规则

| 场景 | 颜色 | 说明 |
|------|------|------|
| 任务默认清扫区域 | **深蓝色**（#00008B） | tasks[].regions 中的区域，初始 status=1 |
| 用户从"其他区域"额外选中 | **浅蓝色**（#ADD8E6） | 区分于默认任务区域，表示用户手动追加 |
| 点击"确认执行"后全部区域 | **深蓝色**（#00008B） | 所有已选区域统一显示为深蓝色 |

### 最终用户消息模板
- 两点路径：`从{起点}({区域}号路)到{终点}({区域}号路)，经过{中间区域}号路。清扫区域为{全部区域}号路线，点击 {HTTP地址} 可查看地图详情。`
- 连续任务：逐任务输出，每个任务一行：
  ```
  本次有{N}个清扫任务：
  任务1：从{起点}到{终点}，清扫区域为{区域列表}号路线。点击 {HTTP地址1} 可查看地图详情。
  任务2：从{起点}到{终点}，清扫区域为{区域列表}号路线。点击 {HTTP地址2} 可查看地图详情。
  ```
- 厕所：`清扫{地标}旁边厕所附近区域，活动区域为{X、Y、Z}号路线。点击 {HTTP地址} 可查看地图详情。`

---

## 视觉分析指南（⚠️ 仅用于确认未知POI + 规划路径）

### 核心原则（CRITICAL）

**永远不要向视觉模型询问已知信息！** 所有通过 `preset_scripts.py query` 查询到的地标，其区域编号已确定。视觉模型的任务仅为：
1. 确认非已知地标的POI蓝色标记所在区域
2. 规划所有区域（已知+视觉确认）之间的最优清扫路径

### 提示词构建方法

1. 对每个地点运行 `preset_scripts.py query "<地名>"` 检查是否在向量库中
2. 已知地标（`found: true`）→ 直接记录区域编号，整理为"预设列表"写入提示词
3. 未知地标 → 列为"需要视觉确认"项
4. 提示词格式：
```
以下地标的区域编号已根据预设数据确定（无需在地图上定位）：
- 地标A → 区域X
- 地标B → 区域Y

需要在地图上确认的POI标记：
- POI名称C（蓝色标记点）

请确认POI所在的区域编号，然后规划连接所有区域的最优清扫路径。
```

### 视觉分析步骤

1. **区分已知/未知**：对每个地点运行 `preset_scripts.py query "<地名>"` 查询向量库
2. **颜色识别**：红色区域=清扫目标，黑色文字=地标，蓝色圆点=POI，灰色=厕所
3. **坐标验证**（规则2）：对POI坐标执行match_region.py确定候选区域
4. **定位未知POI**：在地图截图上找到蓝色标记，确定所在区域编号
5. **定位厕所（仅非预设）**：在地标POI周围找灰色厕所图标，确定其所在区域
6. **规划路径**：已知区域 + 视觉确认区域 → 最短连续路径
7. **验证**：逐对相邻、数量3-7个、顺序正确

### 区域分布参考
- 北部（高纬度）：1-10号
- 中部：11-25号
- 南部（低纬度）：26-39号
- 东部（高经度 >118.17）vs 西部（低经度 <118.17）

---

## 常见错误分析与解决方案

### 错误0：颜色识别——混淆黑色标签与红色清扫区域
**正确做法**：找到黑色文字标签 → 观察旁边红色编号区域 → 红色编号才是清扫目标。楼号≠区域号。

### 错误1：区域编号方向判断错误
**原因**：没有观察POI在地图上的实际位置。**解决**：先看POI位置，再确定最近红色区域。

### 错误2：选择过多无关区域
**原因**：没有遵循最短路径原则。**解决**：先定位起点终点所在区域，选择3-7个连续区域。

### 错误3：搜索关键词不精确
**原因**：直接使用用户输入。**解决**：必须查阅"需POI搜索的常见地标"表中的预设关键词。

### 错误4：跳跃性选区——遗漏中间区域（重要！）
**原因**：只确认端点区域，未逐对验证相邻性。**解决**：逐对检查是否地理相邻，补全所有中间区域。

### 错误5：纯视觉估算——跳过坐标匹配（重要！）
**原因**：直接视觉判断POI所在区域。**解决**：**必须先运行match_region.py**，用坐标距离确定候选区域后再视觉验证。距离<50m可直接确定。

### 错误6：路径选择策略——绕湖长路径
**原因**：惯性选择沿湖。**解决**：优先走中部主干道捷径（如R38日圆大桥作为交通枢纽）。只有用户明确要求"沿湖"时才用沿湖路径。

### 错误7：并列连接词误判为路径连接（重要！）
**原因**："以及"/"和"被当作"到"处理。**解决**：遇到"以及"/"和"→ 各地独立清扫，禁止规划连接路径。

### 错误8：文件保存路径错误
**解决**：过程文件→SESSION_PATH，最终结果→SESSION_DIR。所有文件永久保留。

### 错误9：路径区域顺序排列错误
**解决**：列出的区域必须按从起点到终点的实际经过顺序排列，逐对验证。

### 错误10：视觉提示词未预填已知地标（重要！）
**原因**：让视觉模型识别已存入向量库的地标。**解决**：在提示词中明确列出已知地标区域编号，告知"无需定位"，仅让视觉模型确认未知POI和规划路径。

### 错误11：visualize_regions.py 调用时未使用正确的 --port 和 --output-dir（CRITICAL！）
**原因**：所有任务使用同一个端口和输出目录，导致后续任务覆盖前面任务的结果。**解决**：每个任务使用独立端口（8001, 8002...）和独立的 `--output-dir SESSION_PATH`。

### 错误13：visualize_regions.py 右侧面板缺少"其他区域"section

**原因**：旧版 `fillInfoPanel()` 只遍历 `taskGroupsData` 中的区域，不在任何任务路径中的 36 个区域完全不出现在面板上，用户无法勾选额外区域。**解决**：2026-05-09 新增了"其他区域"分组，包含所有不在任务路径中的区域，可折叠展开。确保 `visualize_regions.py` 中 `fillInfoPanel()` 的 taskGroups 分支末尾有此代码。

### 错误14：toggle_region 请求未同步到 per-task selected_regions

**原因**：前端 `toggleRegion` 只发 `region_id` 和 `selected`，后端只更新顶层 `selected_regions`，未更新 `tasks[task_index].selected_regions`，导致 `confirm` 时数据不一致。**解决**：前端请求必须包含 `task_index`（由 `findTaskIndexForRegion()` 计算），后端同步更新 `data["tasks"][task_index]["selected_regions"]`。

### 错误15："其他区域"选中项未归入任务 selected_regions

**原因**：`collectSelectedData()` 只筛选 `task.regins` 内的选中项，"其他区域"勾选的额外区域不包含在任何任务的 `selected_regions` 中。**解决**：`collectSelectedData()` 需要将不在任何 task.regions 中的选中区域归入第一个任务（`tasks[0].selected_regions`）。

### 错误16：盲目信任向量数据库结果——未验证名称相似性（CRITICAL！）
**原因**：向量数据库总会返回一个最相似结果（即使完全不相关），`found: true` 不代表结果正确。例如搜索"花溪"可能返回"爱情湾"。**解决**：必须对比返回的地标名称与用户输入是否包含相同关键字，名称明显不符的视为 found: false，继续POI搜索。

### 错误17：地标完全找不到时未妥善处理
**原因**：向量数据库和POI搜索均未找到地标时，仍强行使用不相关结果生成任务。**解决**：有其他任务则跳过当前任务继续处理；无其他任务则直接反馈用户地标未找到。

### 错误12：visualize_regions.py 调用时未加 --tasks 导致无任务名称（CRITICAL！）

**原因**：使用裸参数方式 `visualize_regions.py 1 2 3 4 5 6 --no-open` 调用，地图右侧信息面板不显示任务名称图例，用户看不到任务描述。**解决**：**所有场景都必须使用 `--tasks` 参数传入任务名称**，即使是单任务路径。裸参数方式只显示区域列表但无任务图例，禁止使用。正确写法：
```bash
python scripts/visualize_regions.py --no-open --output-dir SESSION_PATH --port 8001 --tasks '[{"name":"任务名称","regions":[1,2,3,4,5,6]}]'
```
---

## 检查清单（Checklist）

### 全部已知 vs 含未知检查（分支决策）
- [ ] 每个地点是否先运行了 `preset_scripts.py query "<地名>"` 查询向量库？
- [ ] **全部 found: true** → 是否验证了返回名称与用户输入文本相似（不盲目信任）？
- [ ] 返回名称与用户输入**明显不符**（无共享关键字）→ 是否视为 found: false 继续POI搜索？
- [ ] **存在 found: false** → 仅对 unknown 地标做POI搜索+截图+match_region
- [ ] 已知地标是否**没有**出现在POI文件中（已知地标不需要POI标记）？
- [ ] POI搜索也未找到的地标 → 是否跳过了该任务或反馈了用户（而非强行生成）？

### 视觉提示词检查
- [ ] 是否将 query 返回的已知地标区域编号整理为"预设列表"写入了提示词？
- [ ] 是否明确告知视觉模型"以下地标区域已确定，无需定位"？
- [ ] 是否仅让视觉模型确认未知POI蓝色标记和规划路径？

### 坐标匹配检查
- [ ] 对有POI坐标的地点，是否执行了match_region.py计算候选区域？
- [ ] 是否遵循了"先算后看"——坐标计算在视觉分析之前？

### 连接词检查
- [ ] 用户是否使用了"以及"/"和"/"跟"？→ 各自独立清扫，**不规划连接路径**
- [ ] 用户是否使用了"再去"/"然后"？→ 独立任务，**不包含转场过渡区域**
- [ ] 用户是否使用了"到"/"至"？→ 连续清扫路径

### 路径检查
- [ ] 区域数量是否在3-7个（两点）或10-15个（多点）？
- [ ] 每对前后区域是否地理相邻（无跳跃）？
- [ ] regions数组顺序是否从起点到终点排列？
- [ ] 是否优先走了中部主干道捷径（非沿湖）？

### 颜色检查
- [ ] 是否区分了红色编号区域（清扫目标）和黑色文字（地标标签）？
- [ ] 楼号是否对应到了旁边红色编号区域（非楼号本身）？

### visualize 调用检查
- [ ] 每个任务是否独立调用了 visualize_regions.py，使用各自的 `--port` 和 `--output-dir SESSION_PATH`？
- [ ] 端口是否从 8001 开始依次递增（任务1→8001, 任务2→8002...）？
- [ ] 是否记录了脚本实际打印的 HTTP 地址（而非硬编码）？

### 输出检查
- [ ] 所有文件（过程+最终）是否都保存到了 SESSION_PATH（任务各自的 session 目录）？
- [ ] 每个任务处理完成后是否立即调用了 visualize_regions.py？
- [ ] 是否逐任务输出了中文说明 + HTTP链接？

---

## 重要约束

1. **只能使用**：poi_search.js、map_screenshot.py、visualize_regions.py、match_region.py、session_manager.py、preset_scripts.py
2. **不得创建额外脚本**
3. **必须视觉分析**：生成地图后使用视觉能力分析截图，在分析中说明选择理由
4. **文件永久保留**：禁止删除任何生成文件
5. **区域编号1-based**：与地图显示一致

## 文件结构

```
car_tool/
├── SKILL.md
├── scripts/
│   ├── poi_search.js
│   ├── map_screenshot.py
│   ├── visualize_regions.py
│   ├── match_region.py
│   ├── session_manager.py
│   ├── preset_scripts.py
│   ├── map_draw_template.html
│   ├── rectangles.json
│   └── config.json
├── 参考图.png
└── task/
    └── YYMMDDHHMM_SS/          ← SESSION_DIR（日期目录）
        ├── session1/            ← 任务1（端口8001）
        │   ├── poi.json
        │   ├── map.png
        │   ├── task_params.json
        │   └── index.html
        ├── session2/            ← 任务2（端口8002）
        │   ├── ...
        │   ├── task_params.json
        │   └── index.html
        └── ...                  ← sessionN（端口800N）
```
