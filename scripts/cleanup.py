#!/usr/bin/env python3
"""
清理car_tool生成的临时文件
"""

import os
import glob

def cleanup_car_tool_files(mode="temp_only"):
    """清理car_tool根目录下的生成文件

    Args:
        mode: 清理模式
            - "temp_only": 只清理临时文件（pois、地图等）
            - "all": 清理所有生成文件包括结果
    """
    # 获取car_tool根目录
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if mode == "temp_only":
        # 只清理临时文件，保留任务结果
        patterns = [
            '*.png',           # 地图截图
            'pois*.json',      # POI文件
            'map*.png',        # 地图文件
        ]
    else:
        # 清理所有生成文件
        patterns = [
            '*.png',           # 地图截图
            'pois*.json',      # POI文件
            '*result*.json',   # 结果文件
            'task*.json',      # 任务文件
            'map*.png',        # 地图文件
        ]

    cleaned_files = []

    for pattern in patterns:
        files = glob.glob(os.path.join(script_dir, pattern))
        for file_path in files:
            try:
                os.remove(file_path)
                cleaned_files.append(os.path.basename(file_path))
            except Exception as e:
                print(f"[警告] 删除文件失败 {file_path}: {e}")

    # 清理临时目录
    tmp_dir = os.path.join(script_dir, 'scripts', 'tmp')
    if os.path.exists(tmp_dir):
        try:
            import shutil
            shutil.rmtree(tmp_dir)
            os.makedirs(tmp_dir, exist_ok=True)
            print(f"[信息] 已清理临时目录: {tmp_dir}")
        except Exception as e:
            print(f"[警告] 清理临时目录失败: {e}")

    if cleaned_files:
        print(f"[信息] 已清理文件: {', '.join(cleaned_files)}")
    else:
        print(f"[信息] 没有需要清理的文件")

if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "temp_only"
    cleanup_car_tool_files(mode)