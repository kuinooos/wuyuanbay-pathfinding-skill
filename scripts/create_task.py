#!/usr/bin/env python3
"""
创建清扫任务脚本

功能：
- 读取输入参数（--area 待清扫区域, --desc 任务说明, --name 任务名）
- 生成 task_id 并创建任务文件夹
- 写入 task_params.json
- 从 task_params.json 读取任务数据，生成可视化 HTML 页面
- 启动/复用 HTTP 服务，返回访问地址与任务 ID
"""

import argparse
import json
import os
import sys
from datetime import datetime

from visualize_regions import (
    generate_visualization_html,
    load_rectangles,
    start_or_reuse_background_http_server,
    _get_local_ip,
)


def main():
    parser = argparse.ArgumentParser(
        description="创建清扫任务",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：\n"
               "  python create_task.py --area 3,4,5,6 --desc \"打扫海水浴场到cafe\" --name \"海水浴场到cafe\"\n"
               "  python create_task.py --area 1,2 --name \"测试任务\" --port 8002",
    )

    parser.add_argument('--area', type=str, required=True,
                        help='待清扫区域序号，逗号分隔（1-based，如: 3,4,5,6）')
    parser.add_argument('--desc', type=str, default='',
                        help='任务说明 / 用户提示词')
    parser.add_argument('--name', type=str, required=True,
                        help='任务名称')
    parser.add_argument('--port', type=int, default=8001,
                        help='HTTP 服务端口（默认 8001，会优先复用已有服务）')

    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)  # car-toolv1.0.1/

    # ---------- 3.1 解析区域参数 ----------
    raw_areas = [a.strip() for a in args.area.split(',') if a.strip()]
    area_ids_1based = []
    for a in raw_areas:
        try:
            area_ids_1based.append(int(a))
        except ValueError:
            print(f"[错误] 无效的区域序号: {a}")
            sys.exit(1)

    if not area_ids_1based:
        print("[错误] 至少需要指定一个区域")
        sys.exit(1)

    # 转换为 0-based 内部 ID
    internal_ids = [a - 1 for a in area_ids_1based]

    # ---------- 3.2 生成 task_id 并创建任务文件夹 ----------
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    task_id = f'task-{timestamp}'

    task_dir = os.path.join(project_root, 'task', task_id)
    os.makedirs(task_dir, exist_ok=True)

    print(f"[信息] 任务文件夹已创建: {task_dir}")

    # ---------- 3.3 写入 task_params.json ----------
    session_id = f'{timestamp}_session1'

    task_params = {
        'task_id': task_id,
        'user_prompt': args.desc,
        'task_type': 'path_cleaning',
        'tasks': [
            {
                'id': session_id,
                'name': args.name,
                'regions': [{'id': rid, 'status': 1} for rid in internal_ids],
                'color': '#00008B',
                'selected_regions': list(internal_ids),
            }
        ],
        'selected_regions': list(internal_ids),
        'total_regions': 39,
        'selected_count': len(internal_ids),
        'execution_confirmed': False,
        'confirmed_at': '',
    }

    params_path = os.path.join(task_dir, 'task_params.json')
    with open(params_path, 'w', encoding='utf-8') as f:
        json.dump(task_params, f, ensure_ascii=False, indent=2)

    print(f"[成功] task_params.json 已写入: {params_path}")

    # ---------- 3.4 从 task_params.json 读取参数，生成可视化 HTML ----------
    # 严格参照 visualize_regions.py main() 的流程：
    #   加载 rectangles → 解析 task_groups → 转换 1-based → 过滤无效 id
    #   → generate_visualization_html() → 写入 HTML → 启动服务

    rectangles_path = os.path.join(script_dir, 'rectangles.json')
    if not os.path.exists(rectangles_path):
        print(f"[错误] 找不到矩形数据文件: {rectangles_path}")
        sys.exit(1)

    rectangles = load_rectangles(rectangles_path)
    print(f"[信息] 总共加载了 {len(rectangles)} 个区域")

    # 从 task_params.json 读取任务分组（作为页面绘制的唯一参数来源）
    with open(params_path, 'r', encoding='utf-8') as f:
        params_data = json.load(f)

    task_groups = params_data.get('tasks', [])

    # task_params.json 中的区域 ID 已经是 0-based，直接提取并校验
    selected_ids = []
    for task in task_groups:
        regions = task.get('regions', [])
        if not regions:
            continue
        # 提取区域 ID（支持 int 和 {"id":N,"status":1} 两种格式）
        raw_ids = []
        for r in regions:
            if isinstance(r, dict):
                raw_ids.append(r['id'])
            else:
                raw_ids.append(r)
        # 过滤无效 id（ID 已经是 0-based，无需转换）
        valid = []
        for rid in raw_ids:
            if rid in rectangles:
                valid.append(rid)
            else:
                print(f"[警告] 任务分组中区域 {rid} 不存在，已忽略")
        task['regions'] = valid
        selected_ids.extend(valid)

    task_names = [{"name": t.get("name", ""), "count": len(t.get("regions", []))} for t in task_groups]
    print(f"[信息] 任务分组: {json.dumps(task_names, ensure_ascii=False)}")

    # 生成 HTML（与 visualize_regions.py 完全相同的调用方式）
    # session_path 传空字符串，不启用 .index 文件监听显示
    html_content = generate_visualization_html(
        rectangles, selected_ids, task_groups, args.name, ''
    )

    index_path = os.path.join(task_dir, 'index.html')
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"[成功] HTML 文件已生成: {index_path}")

    # ---------- 启动 HTTP 服务（与 visualize_regions.py 完全相同的调用方式）----------
    serve_root = project_root
    abs_task_dir = os.path.abspath(task_dir)
    page_rel_path = os.path.relpath(index_path, project_root).replace('\\', '/')

    server_info = start_or_reuse_background_http_server(
        serve_root,
        task_dir=abs_task_dir,
        port=args.port,
        page_rel_path=page_rel_path,
    )

    server_url = server_info['url']
    try:
        actual_port = int(server_url.split(':')[-1].split('/')[0])
    except (ValueError, IndexError):
        actual_port = args.port

    local_ip = _get_local_ip()
    local_url = f'http://{local_ip}:{actual_port}/{page_rel_path}'

    # ---------- 3.6 返回访问地址与任务 ID ----------
    print(f"[成功] 服务器监听: 0.0.0.0:{actual_port}")
    print(f"[成功] 本地访问: {local_url}")
    print(f"")
    print(f"  任务ID:     {task_id}")
    print(f"  访问地址:   {local_url}")

    if server_info.get('reused'):
        pid = server_info.get('pid')
        if pid:
            print(f"[成功] 复用已有 HTTP 服务 (PID: {pid})")
    else:
        pid = server_info.get('pid')
        print(f"[成功] 后台 HTTP 服务已启动 (PID: {pid})")


if __name__ == '__main__':
    main()
