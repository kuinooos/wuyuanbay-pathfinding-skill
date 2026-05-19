---
name: car-toolv1.0.1
description: 清洁小车任务下发助手。根据用户清扫需求，从39个可清扫区域中选择目标区域并生成清扫任务指令。当用户提到清扫、打扫、清洁小车、任务下发、区域清扫等关键词时使用此skill。
triggers:
  - 清扫
  - 打扫
  - 清洁小车
  - 任务下发
  - 区域清扫
  - 派清扫任务
  - 打扫从哪里到哪里
---

# 清洁小车任务下发助手

## 概述

本 skill 实现清洁小车任务下发完整工作流：
1. 用户指定清扫地点（起点、终点或多点）
2. 通过 RAG（Milvus 向量数据库）查询地点经纬度
3. 在地图上标记地点并截图
4. 通过视觉模型分析截图，识别路径经过的可清扫区域（红色路段 + 编号）
5. 创建清扫任务并返回任务页面地址与任务 ID
6. 支持任务重置（修改区域、描述、名称）

## 核心概念

- **可清扫区域**: 共 39 个（编号 1-39，内部 0-based ID 为 0-38），在地图上以红色路段显示，每个路段上方有编号标注
- **区域编号**: 用户看到的编号是 **1-based**（1~39），传给脚本时也使用 1-based，脚本内部转换为 0-based
- **Milvus 数据库**: 运行在 `36.212.131.89:19530`，存储地标的名称、经纬度、描述等向量化数据，用于语义搜索
- **高德地图**: 地图截图基于高德地图 API，使用 GCJ-02 坐标系

## 关键路径

| 路径 | 说明 |
|------|------|
| SKILL.md | 本文件 |
| scripts/rag_poi.py | RAG POI 查询脚本（Milvus 向量搜索） |
| scripts/map_screenshot.py | 地图标记与截图脚本（需要 map_draw_template.html） |
| scripts/create_task.py | 创建清扫任务脚本 |
| scripts/reset_task.py | 重置清扫任务脚本 |
| scripts/rectangles.json | 39 个可清扫区域的边界坐标数据 |
| scripts/preset_data.json | 预设地标数据（用于播种 Milvus） |
| scripts/templates/visualize_template.html | 区域可视化 HTML 模板 |
| scripts/config.json | 地图范围配置（可选，不存在则用默认范围） |

## 工作流

### 步骤 1: 解析用户意图

分析用户输入，提取清扫任务的关键信息：
- **清扫起点** 和 **终点**（如"从公园西门扫到休闲平台"）
- **单一地点**（如"打扫海水浴场"）
- **多个地点列表**（如"打扫公园西门、停车场、海水浴场"）

如果是路径清扫（从 A 到 B），需要确定起点和终点的名称。如果用户表述模糊，反问澄清。

### 步骤 2: RAG 查询地点经纬度

对每个用户提到的地点名称，调用 rag_poi.py 查询：

```bash
cd /home/jfcf/.hermes/skills/car-toolv1.0.1
python scripts/rag_poi.py query <地点名称>
```

**重要**: rag_poi.py 连接远程 Milvus 数据库（36.212.131.89:19530），可能返回多个匹配结果。你需要：
1. 分析返回结果中每个候选的 `name`、`score`（相似度分数，越高越匹配）
2. 结合用户提示词的上下文，判断最匹配的结果
3. 如果多个结果相近且无法确定，使用 `clarify` 工具反问用户选择哪个

**查询失败处理（Milvus 不可达时的降级链）**:
如果 `rag_poi.py query` 因连接超时/拒绝而失败（常见于网络问题时）：
1. 尝试使用 `location-finder` skill 查询地点经纬度
2. location-finder 使用高德 Web Service API，可作为可靠降级方案
3. 将 location-finder 返回的经纬度组装为 poi.json

**示例输出解读**:
```
查询「公园西门」匹配度最高的 3 个结果:
  #1  五缘湾湿地公园(西门) → 坐标: [118.173443, 24.520315]  (score: 0.9234)
  #2  五缘湾感恩广场（入口） → 坐标: [118.164415, 24.514132]  (score: 0.7120)
```
这里应选择 #1，因为 score 最高且名称最匹配。

### 步骤 3: 创建 poi.json

在 `/home/jfcf/.hermes/skills/car-toolv1.0.1/scripts/tmp/` 目录下创建 `poi.json`：

```bash
mkdir -p /home/jfcf/.hermes/skills/car-toolv1.0.1/scripts/tmp
```

poi.json 格式（数组，每个元素包含 name 和 position）：
```json
[
    {
        "name": "公园入口",
        "position": [118.173501, 24.520202]
    },
    {
        "name": "公园出口",
        "position": [118.176368, 24.519747]
    }
]
```

- `position` 格式为 `[longitude, latitude]`（经度在前，纬度在后）
- 坐标从 rag_poi.py 查询结果中的 `poi` 字段获取，格式也是 `[lng, lat]`

### 步骤 4: 地图截图

调用 map_screenshot.py 在地图上标记所有 POI 点并截图：

```bash
cd /home/jfcf/.hermes/skills/car-toolv1.0.1
python scripts/map_screenshot.py \
  --poi-file scripts/tmp/poi.json \
  --screenshot-path scripts/tmp/map_screenshot.png \
  --html-output-dir scripts/tmp
```

**参数说明**:
- `--poi-file`: 步骤 3 创建的 poi.json 路径
- `--screenshot-path`: 截图输出路径
- `--port`: HTTP 服务器端口（默认 8765）
- `--html-output-dir`: HTML 持久保存目录

**依赖**: map_screenshot.py 需要 `scripts/map_draw_template.html` 模板文件和 Playwright Chromium 浏览器。如果缺少模板文件，脚本会报错。

截图成功后输出类似：
```
[成功] 地图截图已保存: /home/jfcf/.hermes/skills/car-toolv1.0.1/scripts/tmp/map_screenshot.png (xxxxx bytes)
```

### 步骤 5: 视觉分析确定可清扫区域

使用 `vision_analyze` 工具分析截图，识别清扫路径经过哪些可清扫区域。

对 vision_analyze 的提问要点：
- 询问从起点到终点的路径上经过哪些红色路段
- 要求读出每个红色路段上的**编号**（1-39）
- 如果是单点清扫，询问该点附近有哪些红色路段
- 如果是多点清扫，询问各个点之间的路径经过哪些红色路段

**视觉分析不可用时的降级方案**（Vision API 余额不足等）:
- 单点任务：跳过视觉分析，使用 `match_region.py` 距离计算（< 50m 阈值）确定最近区域
- 路径任务：使用 rectangles.json 中各区域的 center 坐标推断邻接关系，找出起点到终点之间的区域

**区域编号注意**: 
- 地图上标注的编号是 1-based（1~39）
- 从视觉分析得出的编号直接就是传给脚本的 --area 参数值
- 注意：根据记忆修正，**公园西门对应清扫区域 R2（编号 2，不是 R1）**
- 从地圆桥旁厕所到休闲平台的路径应包含区域 34, 35, 32（1-based 编号），即内部 ID 33, 34, 31

### 步骤 6: 创建清扫任务

使用 create_task.py 创建任务：

```bash
cd /home/jfcf/.hermes/skills/car-toolv1.0.1
python scripts/create_task.py \
  --area 3,4,5,6 \
  --desc "从公园入口打扫到停车场，经过步道和水景区" \
  --name "公园入口到停车场"
```

**参数说明**:
- `--area`: 待清扫区域编号，**1-based**，逗号分隔（如 `3,4,5,6`）
- `--desc`: 任务说明，描述本次清扫任务的内容
- `--name`: 任务名称
- `--port`: HTTP 服务端口（默认 8001，会复用已有服务）

**脚本行为**:
1. 生成 `task_id`（格式：`task-YYYYMMDDHHmmss`）
2. 创建任务文件夹 `task/<task_id>/`
3. 写入 `task_params.json`（包含任务配置）
4. 生成可视化 `index.html`
5. 启动/复用后台 HTTP 服务
6. 输出任务 ID 和访问地址

**成功输出示例**:
```
  任务ID:     task-20260519092001
  访问地址:   http://192.168.1.100:8001/task/task-20260519092001/index.html
```

### 步骤 7: 告知用户

将任务信息告知用户，格式为：
- 任务 ID: `task-xxxxxxxxxxxx`
- 访问地址: `http://<IP>:<port>/task/<task_id>/index.html`
- 提示用户可以在页面中手动修改清扫区域，或者告诉 AI 来帮忙修改

### 步骤 8 （可选）: 重置/修改任务

如果用户说"哪里要改"、"修改区域"、"重新设置"等，调用 reset_task.py：

```bash
cd /home/jfcf/.hermes/skills/car-toolv1.0.1
python scripts/reset_task.py \
  --task_id task-20260519092001 \
  --area 3,4,5,7,8 \
  --desc "修改后的任务描述" \
  --name "新的任务名称"
```

**参数说明**:
- `--task_id`: 要重置的任务 ID（必填）
- `--area`: 新的清扫区域编号，1-based，逗号分隔（必填）
- `--desc`: 新的任务描述
- `--name`: 新的任务名称
- `--port`: HTTP 服务端口（默认 8001）

**重要行为**:
1. 检查任务文件夹下的 `task_params.json` 中的 `execution_confirmed` 字段
2. 如果 `execution_confirmed == true`，**任务已确认执行，无法重置**，脚本返回错误并 exit(1)
3. 如果任务未确认，清空任务文件夹并重新生成 `task_params.json` 和 `index.html`
4. 输出新的访问地址和任务 ID

**如果任务已在进行中（execution_confirmed == true）**:
必须明确告知用户："任务 <task_id> 已确认执行，无法重置。如需修改，请先手动在页面中取消确认状态。"

重置成功后，同样告知用户新的任务 ID 和访问地址。

## 完整示例

**用户**: "帮我打扫从公园西门到休闲平台的路"

**AI 执行流程**:
1. 解析意图：起点="公园西门"，终点="休闲平台"，路径清扫
2. 查询"公园西门"：`python scripts/rag_poi.py query 公园西门` → 匹配"五缘湾湿地公园(西门)" [118.173443, 24.520315]
3. 查询"休闲平台"：`python scripts/rag_poi.py query 休闲平台` → 匹配"休闲平台" [118.171179, 24.513790]
4. 创建 poi.json（scripts/tmp/poi.json）
5. 截图：`python scripts/map_screenshot.py --poi-file scripts/tmp/poi.json --screenshot-path scripts/tmp/map_screenshot.png --html-output-dir scripts/tmp`
6. 视觉分析截图 → 识别经过区域编号（如：2,7,12,18,25,32）
7. 创建任务：`python scripts/create_task.py --area 2,7,12,18,25,32 --desc "从公园西门清扫到休闲平台" --name "公园西门到休闲平台"`
8. 输出任务 ID 和访问地址给用户

**用户**: "把区域改成 2,7,8,12,18,25,32"

**AI 执行流程**:
1. 重新视觉分析（因为区域变了，需要确认）
2. 调用 reset_task.py（使用之前的 task_id，新的 area 参数）
3. 输出新的访问地址

## 注意事项与容易出错的地方

### 关键规则

1. **区域编号始终 1-based**: 用户看到的编号、视觉分析读出的编号、传给 `--area` 参数的编号都是 1-based（1~39）。脚本内部会自动转换为 0-based。

2. **坐标顺序是 [lng, lat]**: poi.json 中 position 字段以及 rag_poi.py 返回的 poi 都是 `[longitude, latitude]`（经度在前）。

3. **路径清扫的区域顺序**: 从视觉分析读出的区域编号应按照路径方向排列，确保清扫顺序合理。

4. **task_id 唯一性**: 每次 create_task 生成新的 task_id，reset_task 保留原 task_id 不变。

5. **Milvus 连接**: rag_poi.py 连接远程服务器 `36.212.131.89:19530`。如果网络不通，脚本会超时或报错。使用 location-finder skill 作为降级方案。

6. **HTTP 服务复用**: create_task 和 reset_task 会尝试复用已有 HTTP 服务（检查 `http_server_state.json`）。如果不指定 `--port`，默认使用 8001。

7. **reset_task 的安全检查**: `execution_confirmed == true` 时无法重置。这是为了防止修改正在执行的任务。

8. **多结果消歧**: rag_poi.py 可能返回多个匹配结果。优先选 score 最高的，如果多个候选 score 相近且名称不同，用 clarify 反问用户。

9. **任务页面功能**: 生成的 HTML 页面支持用户在浏览器中切换/增减清扫区域，点击确认按钮后将 `execution_confirmed` 设为 true。一旦确认，后台脚本无法 reset。