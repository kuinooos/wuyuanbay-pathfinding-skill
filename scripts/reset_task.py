#!/usr/bin/env python3
"""
重置清扫任务脚本

功能：
- 读取输入参数（--area 待清扫区域, --desc 任务说明, --name 任务名, --task_id 任务id）
- 根据任务id检查对应文件夹下 task_params.json 的任务状态
- 如果已经在执行（execution_confirmed == true）则返回错误
- 清空 task-xxxxx 文件夹下所有文件，重新生成 task_params.json 与 index.html
- 启动/复用 HTTP 服务，返回访问地址与任务 ID
"""

import argparse
import json
import os
import shutil
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
        description="重置清扫任务",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：\n"
               "  python reset_task.py --task_id task-20260519092001 --area 3,4,5,6 --desc \"新描述\" --name \"新任务名\"\n"
               "  python reset_task.py --task_id task-20260519092001 --area 1,2 --port 8002",
    )

    parser.add_argument('--task_id', type=str, required=True,
                        help='待重置的任务 ID（如 task-20260519092001）')
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

    task_dir = os.path.join(project_root, 'task', args.task_id)

    # ---------- 4.2 检查任务状态 ----------
    params_path = os.path.join(task_dir, 'task_params.json')
    if os.path.exists(params_path):
        with open(params_path, 'r', encoding='utf-8') as f:
            existing_params = json.load(f)
        if existing_params.get('execution_confirmed', False):
            print(f"[错误] 任务 {args.task_id} 已确认执行，无法重置")
            sys.exit(1)
        print(f"[信息] 任务 {args.task_id} 状态正常，可以重置")
    else:
        print(f"[信息] 任务 {args.task_id} 不存在 task_params.json，将创建新任务文件夹")

    # ---------- 4.3 清空文件夹并重新生成 ----------
    # 如果文件夹存在则清空，否则创建
    if os.path.exists(task_dir):
        shutil.rmtree(task_dir)
        print(f"[信息] 已清空任务文件夹: {task_dir}")
    os.makedirs(task_dir, exist_ok=True)
    print(f"[信息] 任务文件夹已创建: {task_dir}")

    # 解析区域参数
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

    # 写入 task_params.json
    session_id = f'{args.task_id.replace("task-", "")}_session1'

    task_params = {
        'task_id': args.task_id,
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

    with open(params_path, 'w', encoding='utf-8') as f:
        json.dump(task_params, f, ensure_ascii=False, indent=2)

    print(f"[成功] task_params.json 已写入: {params_path}")

    # 加载 rectangles 生成 HTML
    rectangles_path = os.path.join(script_dir, 'rectangles.json')
    if not os.path.exists(rectangles_path):
        print(f"[错误] 找不到矩形数据文件: {rectangles_path}")
        sys.exit(1)

    rectangles = load_rectangles(rectangles_path)
    print(f"[信息] 总共加载了 {len(rectangles)} 个区域")

    # 从 task_params.json 读取任务分组
    with open(params_path, 'r', encoding='utf-8') as f:
        params_data = json.load(f)

    task_groups = params_data.get('tasks', [])

    selected_ids = []
    for task in task_groups:
        regions = task.get('regions', [])
        if not regions:
            continue
        raw_ids = []
        for r in regions:
            if isinstance(r, dict):
                raw_ids.append(r['id'])
            else:
                raw_ids.append(r)
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

    html_content = generate_visualization_html(
        rectangles, selected_ids, task_groups, args.name, ''
    )

    index_path = os.path.join(task_dir, 'index.html')
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"[成功] HTML 文件已生成: {index_path}")

    # ---------- 4.4 启动 HTTP 服务，返回访问地址与任务 ID ----------
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

    print(f"[成功] 服务器监听: 0.0.0.0:{actual_port}")
    print(f"[成功] 本地访问: {local_url}")
    print(f"")
    print(f"  任务ID:     {args.task_id}")
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
