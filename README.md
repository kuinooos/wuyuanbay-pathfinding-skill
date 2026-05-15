# car_tool

简体中文说明，English summary below.

## 项目简介
`car_tool` 是一个面向清洁小车任务下发的辅助技能，核心目标是把用户的自然语言清扫需求转换为可执行、可视化、可追踪的区域任务。

这个项目主要解决三类问题：
- 从 39 个预定义可清扫区域中快速确定目标区域
- 结合 POI 搜索、地图截图和区域匹配，辅助判断地点应落在哪个区域
- 生成标准化任务参数与交互式地图结果，方便人工确认和后续自动化处理

换句话说，它不是一个单纯的“查地图”工具，而是一套围绕清洁任务规划、区域确认和结果展示的工作流。

## 适用场景
- 用户只说“清扫某个地点附近”，需要先把地点映射到区域编号
- 用户给出多个地点，需要判断是连续路径还是并列任务
- 需要生成带 POI 标记的地图截图，辅助视觉确认
- 需要把最终任务结果保存到独立的 session 目录中，便于追踪和复用

## 核心能力
- 39 个可清扫区域的任务映射与区域选择
- POI 搜索与地点坐标获取，见 [scripts/poi_search.js](scripts/poi_search.js)
- 地图截图生成，见 [scripts/map_screenshot.py](scripts/map_screenshot.py)
- 区域可视化与路径展示，见 [scripts/visualize_regions.py](scripts/visualize_regions.py)
- 已知地标查询与任务会话管理，见 [scripts/preset_scripts.py](scripts/preset_scripts.py) 和 [scripts/session_manager.py](scripts/session_manager.py)

## 工作流程
1. 解析用户输入，识别单点、路径、多点或组合任务
2. 优先查询已知地标，判断是否能直接映射到区域编号
3. 对未知地标执行 POI 搜索，获取坐标并生成地图截图
4. 结合区域边界、视觉结果或距离规则，确认最终清扫区域
5. 保存任务参数，并生成可视化结果用于检查和展示

## 目录说明
- [scripts/](scripts/)：核心脚本目录，包含 POI 搜索、截图、可视化和会话管理逻辑
- [docs/](docs/)：使用说明和补充文档
- [references/](references/)：参考资料和算法说明
- [evals/](evals/)：评测配置
- [examples/](examples/)：示例调用方式

## 使用说明
### 1. 进入脚本目录

```bash
cd c:\Users\18325\.claude\skills\car-tool\scripts
```

### 2. 生成区域可视化

```bash
python visualize_regions.py 0 1 2 --no-open
```

### 3. 查询地标或生成任务

具体调用方式以 [docs/USAGE.md](docs/USAGE.md) 和各脚本头部注释为准。不同任务类型会走不同分支，通常不需要手工拼接所有中间产物。

## 配置文件
- [scripts/config.json](scripts/config.json)：任务下发与运行配置
- [scripts/known_landmarks.json](scripts/known_landmarks.json)：已知地标与区域映射
- [scripts/rectangles.json](scripts/rectangles.json)：区域边界与布局数据

## GitHub 发布
如果需要把当前仓库推送到 GitHub，可以按常规流程执行：

```bash
git init
git add .
git commit -m "Refine car_tool documentation"
git branch -M main
git remote add origin https://github.com/kuinooos/wuyuanbay-pathfinding-skill.git
git push -u origin main
```

如果仓库已经存在远端，只需要在本地提交后执行 `git push` 即可。

## English Summary
`car_tool` is a workflow-oriented skill for cleaning-task dispatch. It maps natural-language cleaning requests to one of 39 predefined regions, uses POI search and map screenshots when a location is not already known, and produces task parameters plus visual output for review and execution.
