# 清洁小车任务下发助手 - 使用说明

## 功能概述

本工具根据用户的清扫需求，从39个可清扫区域中选择目标区域，并生成标准化的清扫任务指令（JSON格式）。

## 工作流程

```
用户输入需求
    ↓
需求解析（自然语言处理）
    ↓
[可选] POI地点检索 → 生成地图截图
    ↓
区域选择算法
    ↓
生成JSON任务指令
```

## 使用方式

### 方式一：命令行使用

```bash
python task_generator.py --prompt "清扫厕所附近的5个区域" --output task.json
```

### 方式二：Python代码调用

```python
from task_generator import CleaningTaskGenerator

generator = CleaningTaskGenerator()
result = generator.generate_task(
    prompt="清扫厕所附近的5个区域",
    output_path="task.json"
)

print(result.selected_regions)  # 输出: [5, 6, 7, 12, 13]
```

## 需求输入格式

### 1. 直接指定区域编号

```
清扫5号区域                    → 选择 [5]
打扫1、3、5号区域              → 选择 [1, 3, 5]
清理1-10号区域                 → 选择 [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
清扫1-5号区域和10、15号区域    → 选择 [1, 2, 3, 4, 5, 10, 15]
```

### 2. 指定地点类型

```
清扫厕所附近                   → 搜索厕所POI，选择最近区域
打扫餐厅周围3个区域           → 搜索餐厅POI，选择最近3个区域
清理停车场周边                → 搜索停车场POI，选择最近区域
```

支持的地点类型：
- 厕所/卫生间/洗手间/公厕
- 餐厅/食堂/饭店/餐饮
- 停车场/车位/停车
- 入口/门口/大门
- 出口/离场
- 展厅/展馆/展览
- 办公室/办公区/写字楼
- 休息区/休息室/休闲区
- 商店/商铺/便利店/超市

### 3. 指定位置描述

```
清扫北部区域      → 选择北部区域（1-10号）
打扫南部          → 选择南部区域（26-39号）
清理中部          → 选择中部区域（11-25号）
清扫东部区域      → 选择东部区域
打扫西部          → 选择西部区域
```

### 4. 组合需求

```
清扫展厅周围和人流量大的地方  → 搜索展厅POI + 结合位置特征
打扫北部5个区域               → 北部区域中选择5个
```

## 输出说明

### 成功输出示例

```json
{
  "status": "success",
  "task_id": "task_20250124_143052",
  "timestamp": "2025-01-24T14:30:52",
  "user_prompt": "清扫厕所附近区域",
  "selected_regions": [5, 6, 7, 12, 13],
  "poi_info": [
    {
      "name": "公共厕所",
      "address": "XX路XX号",
      "center": {"lng": 118.173, "lat": 24.520}
    }
  ],
  "map_screenshot": "map.png",
  "total_regions": 39,
  "selected_count": 5,
  "reasoning": "根据'厕所'位置选择了最近的5个区域"
}
```

### 字段说明

| 字段 | 说明 | 示例值 |
|------|------|--------|
| `status` | 任务状态 | "success" / "error" |
| `task_id` | 任务唯一ID | "task_20250124_143052" |
| `timestamp` | 生成时间 | "2025-01-24T14:30:52" |
| `user_prompt` | 用户原始输入 | "清扫厕所附近区域" |
| `selected_regions` | 选中的区域编号列表 | [5, 6, 7, 12, 13] |
| `poi_info` | 相关POI信息列表 | [...] |
| `map_screenshot` | 地图截图文件路径 | "map.png" |
| `total_regions` | 可清扫区域总数 | 39 |
| `selected_count` | 选中区域数量 | 5 |
| `reasoning` | 选择理由说明 | "根据'厕所'位置选择了最近的5个区域" |

## 39个可清扫区域分布

```
    北部 (1-10号)
    ┌─────────────────┐
    │  1  2  3  4  5  │
    │  6  7  8  9 10  │
    ├─────────────────┤
    │ 11 12 13 14 15 │  中部 (11-25号)
    │ 16 17 18 19 20 │
    │ 21 22 23 24 25 │
    ├─────────────────┤
    │ 26 27 28 29 30 │  南部 (26-39号)
    │ 31 32 33 34 35 │
    │ 36 37 38 39    │
    └─────────────────┘
```

## 工具说明

### poi_search.js - 地点检索工具

**功能**：在指定区域内搜索特定类型的地点

**使用方法**：
```bash
node scripts/poi_search.js "关键词"
```

**示例**：
```bash
node scripts/poi_search.js "厕所"
node scripts/poi_search.js "餐厅"
node scripts/poi_search.js "停车场"
```

**输出**：控制台输出搜索结果，包括地点名称、地址、坐标

### map_screenshot.py - 地图截图工具

**功能**：生成包含POI标记和39个可清扫区域的地图截图

**使用方法**：
```bash
python scripts/map_screenshot.py \
    --poi-file pois.json \
    --screenshot-path output.png
```

**参数说明**：
- `--poi-file`：POI数据文件路径（JSON格式）
- `--screenshot-path`：截图输出路径
- `--port`：HTTP服务器端口（默认8765）

## 常见使用场景

### 场景1：日常清扫任务

```bash
# 清扫全部区域
python task_generator.py --prompt "清扫1-39号区域" --output daily_task.json

# 清扫重点区域
python task_generator.py --prompt "清扫1-10号区域" --output task.json
```

### 场景2：特定地点清扫

```bash
# 清扫厕所附近
python task_generator.py --prompt "清扫厕所附近区域" --output toilet_task.json

# 清扫餐厅周围5个区域
python task_generator.py --prompt "清扫餐厅周围5个区域" --output restaurant_task.json
```

### 场景3：分区域清扫

```bash
# 北部区域
python task_generator.py --prompt "清扫北部10个区域" --output north_task.json

# 中部区域
python task_generator.py --prompt "清扫中部区域" --output center_task.json

# 南部区域
python task_generator.py --prompt "清扫南部区域" --output south_task.json
```

## 故障排除

### 问题1：POI搜索无结果

**原因**：网络问题或关键词不匹配

**解决方案**：
- 检查网络连接
- 尝试使用同义词（如"卫生间"代替"厕所"）
- 改用直接指定区域编号的方式

### 问题2：地图截图失败

**原因**：Playwright未安装或浏览器内核缺失

**解决方案**：
```bash
pip install playwright
playwright install chromium
```

### 问题3：区域编号无效

**原因**：输入的编号不在1-39范围内

**解决方案**：
- 确认使用1-39之间的编号
- 使用 `--verbose` 参数查看详细日志

## 注意事项

1. **scripts目录下的文件不要修改** - 这些工具文件已开发完成
2. **POI搜索需要网络** - 确保有互联网连接
3. **首次运行需要初始化** - Playwright需要下载浏览器内核
4. **输出文件会覆盖** - 同名文件会被覆盖，请注意备份
5. **区域编号从1开始** - 与地图显示一致，内部数据从0开始

## 技术支持

如有问题，请检查：
1. 环境是否满足要求（Python 3.8+, Node.js 14+）
2. 依赖是否正确安装（playwright）
3. 网络连接是否正常（POI搜索需要）
4. 日志输出是否有错误信息（使用 `--verbose`）
