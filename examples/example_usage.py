#!/usr/bin/env python3
"""
使用示例脚本

演示如何使用清洁小车任务生成器的各种功能
"""

import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from task_generator import CleaningTaskGenerator
from task_selector import RegionSelector


def example_1_basic_usage():
    """示例1: 基本使用"""
    print("=" * 70)
    print("示例1: 基本使用 - 指定区域编号")
    print("=" * 70)

    generator = CleaningTaskGenerator(verbose=True)

    result = generator.generate_task(
        prompt="清扫1到5号区域",
        output_path="example1_result.json",
        use_poi=False
    )

    print(f"\n结果:")
    print(f"  选择区域: {result.selected_regions}")
    print(f"  选择理由: {result.reasoning}")
    print()


def example_2_poi_based():
    """示例2: 基于POI的选择"""
    print("=" * 70)
    print("示例2: 基于POI的选择")
    print("=" * 70)

    generator = CleaningTaskGenerator(verbose=True)

    # 模拟POI坐标（实际使用时可以通过poi_search.js获取）
    poi_lng, poi_lat = 118.173, 24.520

    # 直接指定区域，跳过POI搜索
    result = generator.generate_task(
        prompt="清扫厕所附近的5个区域",
        poi_keyword="厕所",
        output_path="example2_result.json",
        use_poi=True  # 启用POI搜索
    )

    print(f"\n结果:")
    print(f"  选择区域: {result.selected_regions}")
    print(f"  相关POI: {len(result.poi_info)}个")
    print(f"  选择理由: {result.reasoning}")
    print()


def example_3_location_based():
    """示例3: 基于位置的选择"""
    print("=" * 70)
    print("示例3: 基于位置的选择")
    print("=" * 70)

    generator = CleaningTaskGenerator(verbose=True)

    result = generator.generate_task(
        prompt="清扫北部区域的3个区域",
        output_path="example3_result.json",
        use_poi=False
    )

    print(f"\n结果:")
    print(f"  选择区域: {result.selected_regions}")
    print(f"  选择理由: {result.reasoning}")
    print()


def example_4_complex_prompt():
    """示例4: 复杂需求解析"""
    print("=" * 70)
    print("示例4: 复杂需求解析")
    print("=" * 70)

    generator = CleaningTaskGenerator(verbose=True)

    test_cases = [
        "清扫1、3、5号区域",
        "打扫1-10号区域",
        "清理厕所和餐厅附近",
        "清扫展厅周围的5个区域",
        "打扫中南部区域",
    ]

    for prompt in test_cases:
        print(f"\n输入: '{prompt}'")
        parsed = generator.parse_user_prompt(prompt)
        print(f"  解析结果:")
        print(f"    - 指定区域: {parsed['specified_regions']}")
        print(f"    - POI关键词: {parsed['poi_keywords']}")
        print(f"    - 区域数量: {parsed['region_count']}")
        print(f"    - 位置提示: {parsed['location_hints']}")
        print(f"    - 使用POI: {parsed['use_poi']}")

    print()


def example_5_region_selector():
    """示例5: 使用区域选择器"""
    print("=" * 70)
    print("示例5: 使用区域选择器")
    print("=" * 70)

    selector = RegionSelector()

    # 测试点
    test_point = (118.173, 24.520)

    print(f"\n测试点坐标: {test_point}")
    print()

    # 基于距离选择
    print("基于距离选择最近的5个区域:")
    regions = selector.select_by_distance(test_point, count=5)
    print(f"  结果: {regions}")
    print()

    # 基于位置选择
    print("基于位置选择:")
    for loc in ['north', 'center', 'south']:
        regions = selector.select_by_location(loc, count=5)
        print(f"  {loc}: {regions}")
    print()

    # 智能选择
    print("智能选择测试:")
    test_inputs = [
        "清扫1-3号区域",
        "打扫北部区域",
        "清理南部",
        "清扫中部",
    ]
    for input_text in test_inputs:
        result = selector.select_smart(input_text, default_count=5)
        print(f"  输入: '{input_text}'")
        print(f"    结果: {result['selected_regions']}")
        print(f"    策略: {result['strategies_used']}")
    print()


def example_6_region_info():
    """示例6: 获取区域信息"""
    print("=" * 70)
    print("示例6: 获取区域信息")
    print("=" * 70)

    selector = RegionSelector()

    # 获取1号区域信息
    print("\n1号区域信息:")
    info = selector.get_region_info(1)
    if info:
        print(f"  ID: {info['id']}")
        print(f"  中心坐标: {info['center']}")
        print(f"  边界点数量: {len(info['boundary'])}")

    # 获取最近的区域
    test_point = (118.173, 24.520)
    nearest = selector.get_nearest_region(test_point)
    print(f"\n距离{test_point}最近的区域: {nearest}")

    # 获取边界内的区域
    regions = selector.get_regions_in_bounds(
        min_lng=118.16, max_lng=118.18,
        min_lat=24.51, max_lat=24.53
    )
    print(f"\n在指定边界内的区域数量: {len(regions)}")
    print(f"  区域: {regions[:10]}...")  # 只显示前10个
    print()


def example_7_direct_regions():
    """示例7: 直接指定区域"""
    print("=" * 70)
    print("示例7: 直接指定区域")
    print("=" * 70)

    generator = CleaningTaskGenerator(verbose=True)

    # 使用--regions参数的效果
    result = generator.generate_task(
        prompt="清扫任务",
        specified_regions=[1, 3, 5, 7, 9],
        output_path="example7_result.json",
        use_poi=False
    )

    print(f"\n结果:")
    print(f"  指定区域: [1, 3, 5, 7, 9]")
    print(f"  实际选择: {result.selected_regions}")
    print(f"  选择理由: {result.reasoning}")
    print()


def main():
    """运行所有示例"""
    print("\n" + "=" * 70)
    print("清洁小车任务生成器 - 使用示例")
    print("=" * 70)
    print()

    examples = [
        ("基本使用", example_1_basic_usage),
        ("基于POI的选择", example_2_poi_based),
        ("基于位置的选择", example_3_location_based),
        ("复杂需求解析", example_4_complex_prompt),
        ("使用区域选择器", example_5_region_selector),
        ("获取区域信息", example_6_region_info),
        ("直接指定区域", example_7_direct_regions),
    ]

    print("可用示例:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")
    print()

    # 运行所有示例
    for name, func in examples:
        try:
            func()
        except Exception as e:
            print(f"示例执行失败 '{name}': {e}")
            print()

    print("=" * 70)
    print("示例运行完成")
    print("=" * 70)


if __name__ == "__main__":
    main()
