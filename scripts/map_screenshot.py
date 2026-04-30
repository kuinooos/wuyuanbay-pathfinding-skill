#!/usr/bin/env python3
"""
生成地图落地页并截图的Python脚本
"""

import argparse
import json
import shutil
import os
import re
import time
import http.server
import socketserver
import threading
from pathlib import Path
import time

# Playwright用于截图
from playwright.sync_api import sync_playwright


def read_poi_file(poi_file_path: str) -> list:
    """读取POI文件"""
    with open(poi_file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def read_html_template(html_path: str) -> str:
    """读取HTML模板文件"""
    with open(html_path, 'r', encoding='utf-8') as f:
        return f.read()


def generate_new_html(html_content: str, pois: list) -> str:
    """
    生成新的HTML内容，将POI数据替换到pois变量中
    """
    # 将POI数据转换为JavaScript数组格式
    # 确保格式与模板一致: { name: "...", position: [lng, lat] }
    formatted_pois = []
    for poi in pois:
        if isinstance(poi, dict):
            name = poi.get('name', '未命名')
            # 支持 position 或 center 字段
            position = poi.get('position') or poi.get('center', [0, 0])
            formatted_pois.append({'name': name, 'position': position})

    pois_js = json.dumps(formatted_pois, ensure_ascii=False, indent=4)

    # 使用正则表达式替换pois数组定义
    # 匹配 const pois = [...]; 这种模式
    pattern = r'(const pois = )\[[\s\S]*?\](;)'

    def replace_pois(match):
        return f'{match.group(1)}{pois_js}{match.group(2)}'

    new_html = re.sub(pattern, replace_pois, html_content, count=1)

    # 强制使用经典栅格样式，避免矢量模式下POI/标注渲染不完整
    map_style_pattern = r"(const map = new AMap\.Map\('map-container', \{\n\s*zoom: 14,\n\s*center: \[118\.170645, 24\.51649\], // 五缘湾湿地公园中心点\n\s*resizeEnable: true)(\n\s*\}\);)"

    def replace_map_style(match):
        return f"{match.group(1)},\n            mapStyle: 'amap://styles/light',{match.group(2)}"

    new_html = re.sub(map_style_pattern, replace_map_style, new_html, count=1)

    # 验证替换是否成功
    if 'const pois = [];' in new_html and len(formatted_pois) > 0:
        print(f"[警告] POI数据替换可能失败，尝试备用方法")
        # 备用：直接字符串替换
        old_pattern = 'const pois = [\n                { name: "公园入口", position: [118.173501,24.520202] },\n                { name: "公园出口", position: [118.176368,24.519747] },\n            ];'
        new_html = html_content.replace(old_pattern, f'const pois = {pois_js};')

    return new_html


def copy_files_to_temp(temp_dir: str, poi_file_path: str, rectangles_file_path: str, config_file_path: str):
    """复制必要的文件到临时文件夹"""
    # 复制POI文件
    poi_dest = os.path.join(temp_dir, 'pois.json')
    if os.path.exists(poi_file_path):
        shutil.copy2(poi_file_path, poi_dest)
    else:
        pois = []
        with open(poi_dest, 'w', encoding='utf-8') as f:
            json.dump(pois, f, ensure_ascii=False, indent=4)


    # 复制rectangles.json
    rect_dest = os.path.join(temp_dir, 'rectangles.json')
    shutil.copy2(rectangles_file_path, rect_dest)

    # 复制config.json（重要：确保地图范围配置生效）
    config_dest = os.path.join(temp_dir, 'config.json')
    if os.path.exists(config_file_path):
        shutil.copy2(config_file_path, config_dest)
        print(f"[信息] 已复制配置文件: {config_file_path} -> {config_dest}")
    else:
        print(f"[警告] 配置文件不存在: {config_file_path}")

    return poi_dest, rect_dest, config_dest


def save_html(html_content: str, temp_dir: str) -> str:
    """保存生成的HTML文件"""
    html_path = os.path.join(temp_dir, 'index.html')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    return html_path


class SimpleHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """自定义HTTP请求处理器"""

    def __init__(self, *args, directory=None, **kwargs):
        self.directory = directory
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format, *args):
        # 静默日志输出
        pass


def start_http_server(temp_dir: str, port: int = 8765) -> socketserver.TCPServer:
    """启动HTTP服务器"""
    handler = lambda *args, **kwargs: SimpleHTTPRequestHandler(*args, directory=temp_dir, **kwargs)
    httpd = socketserver.TCPServer(("", port), handler)

    server_thread = threading.Thread(target=httpd.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    return httpd


def take_screenshot(url: str, output_path: str, width: int = 1920, height: int = 1200):
    """使用Playwright对页面进行截图"""
    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception as e:
                # 浏览器未安装或启动失败，创建占位符图像
                if "Executable doesn't exist" in str(e) or "playwright" in str(e).lower():
                    print(f"[警告] Chromium 浏览器未安装，生成占位符图像")
                    print(f"[提示] 请运行以下命令安装浏览器：")
                    print(f"      python -m playwright install chromium")
                    create_placeholder_image(output_path, width, height)
                    return
                raise

            page = browser.new_page(viewport={'width': width, 'height': height})

            # 加载页面
            page.goto(url)

            # 等待页面加载完成（等待地图渲染）
            # 等待一段时间让高德地图API加载和渲染
            page.wait_for_timeout(10000)  # 等待10秒让地图完全渲染

            # 也可以等待特定的元素出现来表示地图已加载
            # page.wait_for_selector('#map-container', state='visible')

            # 截图
            page.screenshot(path=output_path, full_page=False)

            browser.close()
    except Exception as e:
        print(f"[错误] 截图生成失败: {e}")
        # 生成占位符图像作为备选
        try:
            create_placeholder_image(output_path, width, height)
            print(f"[信息] 已生成占位符图像: {output_path}")
        except:
            pass


def create_placeholder_image(output_path: str, width: int = 1920, height: int = 1200):
    """创建占位符图像"""
    try:
        from PIL import Image, ImageDraw, ImageFont

        # 创建灰色背景图像
        img = Image.new('RGB', (width, height), color=(220, 220, 220))
        draw = ImageDraw.Draw(img)

        # 绘制中心文字
        text = "地图加载中...\n请确保 Chromium 已安装\n运行: python -m playwright install"

        # 计算文字位置（大致中心）
        text_bbox = draw.textbbox((0, 0), text, font=None)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        x = (width - text_width) // 2
        y = (height - text_height) // 2

        # 绘制文字
        draw.text((x, y), text, fill=(100, 100, 100), align="center")

        # 保存图像
        img.save(output_path)
    except ImportError:
        # 如果没有 PIL，使用 JSON 来记录信息（作为最后的备选）
        import json
        metadata = {
            "status": "placeholder",
            "message": "地图生成失败 - Chromium 浏览器未安装",
            "width": width,
            "height": height,
            "installation_command": "python -m playwright install"
        }
        json_path = output_path.replace('.png', '_metadata.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)


def main(
        poi_file_path: str = '',
        screenshot_path: str = 'screenshot.png',
        port: int = 8765
):
    """主函数"""
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # 1. 读取POI文件
    pois = []
    if poi_file_path and len(poi_file_path) > 0:
        # 转换为绝对路径
        if not os.path.isabs(poi_file_path):
            poi_file_path = os.path.abspath(poi_file_path)

        if not os.path.exists(poi_file_path):
            print(f"[警告] POI文件不存在: {poi_file_path}")
            pois = []
        else:
            try:
                pois = read_poi_file(poi_file_path)
                print(f"[信息] 已读取POI文件: {poi_file_path}")
                print(f"[信息] 已向地图中添加 {len(pois)} 个坐标点")
                # 打印POI详情用于调试
                for i, poi in enumerate(pois[:5]):  # 只打印前5个
                    print(f"       POI {i+1}: {poi}")
            except Exception as e:
                print(f"[错误] 读取POI文件失败: {e}")
                pois = []
    else:
        print("[信息] 未提供POI文件，将生成空白地图")

    # 2. 读取HTML模板
    html_template_path = os.path.join(script_dir, "map_draw_template.html")
    html_content = read_html_template(html_template_path)

    # 3. 生成新的HTML内容
    new_html = generate_new_html(html_content, pois)

    # 4. 创建临时文件夹并复制文件
    temp_dir = os.path.join(script_dir, "tmp", "current")
    # 清理旧的临时文件
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir, exist_ok=True)
    print(f"[信息] 创建临时目录: {temp_dir}")

    rectangles_file_path = os.path.join(script_dir, "rectangles.json")
    config_file_path = os.path.join(script_dir, "config.json")
    print(f"[信息] 区域数据文件: {rectangles_file_path}")
    print(f"[信息] 配置文件: {config_file_path}")

    # 复制POI文件到临时目录（如果存在）
    if poi_file_path and os.path.exists(poi_file_path):
        copy_files_to_temp(temp_dir, poi_file_path, rectangles_file_path, config_file_path)
    else:
        # 创建空的POI文件
        empty_poi_path = os.path.join(temp_dir, 'pois.json')
        with open(empty_poi_path, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=4)
        # 复制rectangles.json
        rect_dest = os.path.join(temp_dir, 'rectangles.json')
        shutil.copy2(rectangles_file_path, rect_dest)
        # 复制config.json（重要：确保地图范围配置生效）
        if os.path.exists(config_file_path):
            config_dest = os.path.join(temp_dir, 'config.json')
            shutil.copy2(config_file_path, config_dest)
            print(f"[信息] 已复制配置文件到临时目录")

    html_path = save_html(new_html, temp_dir)
    print(f"[信息] HTML文件已保存: {html_path}")

    # 5. 启动HTTP服务器
    httpd = start_http_server(temp_dir, port)
    url = f"http://localhost:{port}/index.html"

    # 等待服务器启动
    time.sleep(1)

    # 6. 截图
    # 确保截图路径是绝对路径
    if not os.path.isabs(screenshot_path):
        screenshot_path = os.path.abspath(screenshot_path)

    print(f"[信息] 开始截图，保存到: {screenshot_path}")
    take_screenshot(url, screenshot_path)

    # 关闭服务器
    httpd.shutdown()

    # 检查截图是否生成成功
    if os.path.exists(screenshot_path):
        file_size = os.path.getsize(screenshot_path)
        print(f"[成功] 地图截图已保存: {screenshot_path} ({file_size} bytes)")

        # 清理临时目录
        try:
            shutil.rmtree(temp_dir)
            print(f"[信息] 已清理临时目录: {temp_dir}")
        except Exception as e:
            print(f"[警告] 清理临时目录失败: {e}")

        # 清理输入的POI文件（如果是临时创建的）
        if poi_file_path and os.path.exists(poi_file_path):
            # 检查是否是临时文件（在skill根目录下的poi_开头的文件）
            poi_filename = os.path.basename(poi_file_path)
            if poi_filename.startswith('poi_') and not poi_filename == 'pois_example.json':
                try:
                    os.remove(poi_file_path)
                    print(f"[信息] 已清理临时POI文件: {poi_file_path}")
                except Exception as e:
                    print(f"[警告] 清理临时POI文件失败: {e}")
    else:
        print(f"[警告] 截图文件未生成: {screenshot_path}")

    # 执行清理
    try:
        cleanup_script = os.path.join(script_dir, "cleanup.py")
        if os.path.exists(cleanup_script):
            os.system(f"python '{cleanup_script}' > /dev/null 2>&1")
    except Exception as e:
        print(f"[警告] 执行清理失败: {e}")

    return temp_dir, screenshot_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='生成地图落地页并截图')
    parser.add_argument(
        '--poi-file',
        type=str,
        default='',
        help='POI数据文件路径 (JSON格式)'
    )
    parser.add_argument(
        '--screenshot-path',
        type=str,
        default='screenshot.png',
        help='截图输出路径'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8765,
        help='HTTP服务器端口 (默认: 8765)'
    )

    args = parser.parse_args()

    main(
        poi_file_path=args.poi_file,
        screenshot_path=args.screenshot_path,
        port=args.port
    )
