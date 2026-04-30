# car_tool — 清洁小车任务下发助手


## 概述
`car_tool` 是一个用于生成与可视化清洁小车任务的技能（skill）。它包含区域配置、基于地图的 POI 与可视化脚本，方便将清扫任务下发到机器人/小车系统或用于调试与展示。

## 主要功能
- 从预定义的 39 个可清扫区域中选择目标区域并生成任务指令
- POI 搜索与地图截图生成（`map_screenshot.py`）
- 可视化清扫路径与区域（`visualize_regions.py`）

## 依赖与环境
- Python 3.8+
- 推荐安装依赖（如果需要额外包，见各脚本头注释）：

```bash
python -m pip install -r requirements.txt  # 若项目没有 requirements.txt，可按需安装 pillow、requests 等
```

## 快速开始
1. 进入脚本目录：

```bash
cd c:\Users\18325\.claude\skills\car_tool\scripts
```

2. 示例：生成可视化（不自动打开浏览器）

```bash
python visualize_regions.py 0 1 2 --no-open
```

## 配置
- `config.json`：包含任务下发相关配置（示例见 `scripts/config.json`）。
- `known_landmarks.json`：已知地标（用于地图匹配与标注）。

## 开发与贡献
- 欢迎提交 issue 和 PR。提交前请在本地运行脚本验证可视化输出。

## 许可
本仓库采用 MIT 许可证（见 LICENSE 文件）。

## 联系
- 作者/联系人邮箱：1832578485@qq.com
- GitHub: https://github.com/kuinooos

---

English summary

car_tool is a small toolkit for generating cleaning-robot tasks and visualizing regions/paths on a map. See scripts/ for examples and configuration files.
