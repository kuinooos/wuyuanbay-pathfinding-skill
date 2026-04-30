#!/usr/bin/env python3
"""
自动清理car_tool生成的文件
这个脚本应该在skill执行后被调用
"""

import os
import sys
import glob

def main():
    """主函数：清理所有生成的文件"""
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # 清理所有可能的生成文件
    patterns = [
        '*.png',           # 地图截图
        'pois*.json',      # POI文件
        '*result*.json',   # 结果文件
        'task*.json',      # 任务文件
        'map*.png',        # 地图文件
        'cleaning_*.json', # 清扫任务文件
    ]

    cleaned_files = []

    for pattern in patterns:
        files = glob.glob(os.path.join(script_dir, pattern))
        for file_path in files:
            try:
                os.remove(file_path)
                cleaned_files.append(os.path.basename(file_path))
            except Exception as e:
                # 静默失败，不输出错误
                pass

    # 清理临时目录
    tmp_dir = os.path.join(script_dir, 'scripts', 'tmp')
    if os.path.exists(tmp_dir):
        try:
            import shutil
            shutil.rmtree(tmp_dir)
            os.makedirs(tmp_dir, exist_ok=True)
        except:
            pass

    # 只在有文件被清理时才输出
    if cleaned_files:
        print(f"[自动清理] 已清理: {', '.join(cleaned_files)}")

if __name__ == "__main__":
    main()