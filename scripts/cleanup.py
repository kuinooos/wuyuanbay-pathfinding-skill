#!/usr/bin/env python3
"""
文件保留模式：所有生成的文件均保留，不执行任何清理。
"""
import sys

def cleanup_car_tool_files(mode="temp_only"):
    print("[文件保留] 根据策略配置，所有生成文件已保留，未执行清理操作。")
    sys.exit(0)

if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "temp_only"
    cleanup_car_tool_files(mode)
