#!/usr/bin/env python3
"""
地图区域可视化脚本
指定序号来显示特定的清扫区域，生成交互式HTML地图界面

功能：
- 显示所有 39 个区域
- 用户通过命令行指定若干区域（0-38）作为初始高亮
- 其余区域以灰色无标号显示
- 用户点击灰色区域后，切换为彩色并显示编号与信息；再次点击可取消
"""

import argparse
import json
import os
import shutil
from typing import List

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


def load_rectangles(rectangles_path: str) -> dict:
    with open(rectangles_path, 'r', encoding='utf-8') as f:
        return {item['id']: item for item in json.load(f)}


def filter_regions(rectangles: dict, region_ids: List[int]) -> dict:
    filtered = {}
    for rid in region_ids:
        if rid in rectangles:
            filtered[rid] = rectangles[rid]
        else:
            print("[警告] 区域 {} 不存在".format(rid))
    return filtered


def generate_visualization_html(all_regions: dict, selected_ids: List[int], title: str = "清扫区域展示") -> str:
    colors = [
        '#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8',
        '#F7DC6F', '#BB8FCE', '#85C1E2', '#F8B739', '#52B788',
    ]

    regions_with_colors = []
    for idx, (rid, region) in enumerate(sorted(all_regions.items())):
        color = colors[idx % len(colors)]
        regions_with_colors.append({
            'id': rid,
            'center': region['center'],
            'boundary': region['boundary'],
            'color': color,
            'name': 'region_{}'.format(rid + 1),
            'selected': True if rid in selected_ids else False
        })

    regions_js = json.dumps(regions_with_colors, ensure_ascii=False)

    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>__TITLE__</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body, html {{ width: 100%; height: 100%; font-family: "Microsoft YaHei", Arial, sans-serif; }}
        #container {{ display: flex; width: 100%; height: 100%; }}
        #map-container {{ flex: 1; width: 100%; height: 100%; }}
        #info-panel {{ width: 300px; background: white; border-left: 1px solid #ddd; overflow-y: auto; padding: 20px; box-shadow: -2px 0 4px rgba(0,0,0,0.1); }}
        #info-panel h2 {{ margin-bottom: 20px; color: #333; border-bottom: 2px solid #4ECDC4; padding-bottom: 10px; }}
        .region-item {{ padding: 12px; margin-bottom: 10px; background: #f9f9f9; border-left: 4px solid #ccc; border-radius: 2px; cursor: pointer; transition: all 0.3s ease; }}
        .region-item:hover {{ background: #f0f0f0; transform: translateX(4px); }}
        .region-item.active {{ background: #e8f4f8; border-left-color: #4ECDC4; }}
        .region-name {{ font-weight: bold; color: #333; margin-bottom: 4px; }}
        .region-color {{ display: inline-block; width: 12px; height: 12px; border-radius: 2px; margin-right: 6px; vertical-align: middle; }}
        .region-coords {{ font-size: 12px; color: #666; margin-top: 6px; font-family: monospace; }}
        @media (max-width: 768px) {{ #info-panel {{ width: 100%; max-height: 200px; border-left: none; border-top: 1px solid #ddd; }} #container {{ flex-direction: column; }} }}
    </style>
</head>
<body>
    <div id="container">
        <div id="map-container"></div>
        <div id="info-panel">
            <h2>📍 选定区域</h2>
            <div id="region-list"></div>
        </div>
    </div>
    <script>
        // 捕获页面错误以便调试地图加载问题
        window.__errors = [];
        window.onerror = function(message, source, lineno, colno, error) {
            window.__errors.push({message, source, lineno, colno, stack: error && error.stack});
        };
        (function(){
            const origErr = console.error;
            console.error = function(...args){ window.__errors.push({console:'error', args: args}); origErr.apply(console, args); };
        })();
    </script>
    <script src="https://webapi.amap.com/maps?v=2.0&key=ff74f328ab12ebcae370a2f3780a5fbb"></script>
    <script>
        const regionsData = __REGIONS_JS__;
        const map = new AMap.Map("map-container", {{ zoom: 14, center: [118.170645, 24.51649], resizeEnable: true, mapStyle: "amap://styles/light" }});
        const polygons = [], markers = [];

        function initMap() {{
            let minLng = Infinity, minLat = Infinity, maxLng = -Infinity, maxLat = -Infinity;
            regionsData.forEach((region) => {{
                region.boundary.forEach(point => {{
                    minLng = Math.min(minLng, point[0]);
                    minLat = Math.min(minLat, point[1]);
                    maxLng = Math.max(maxLng, point[0]);
                    maxLat = Math.max(maxLat, point[1]);
                }});

                const fillCol = region.selected ? region.color : '#CCCCCC';
                const strokeCol = region.selected ? region.color : '#999999';
                const polygon = new AMap.Polygon({{
                    path: region.boundary, strokeColor: strokeCol, strokeWeight: 2, strokeOpacity: 0.9,
                    fillColor: fillCol, fillOpacity: region.selected ? 0.2 : 0.12, strokeStyle: "solid"
                }});
                map.add(polygon);
                polygons.push(polygon);

                if (region.selected) {{
                    const marker = new AMap.Marker({ position: region.center, offset: new AMap.Pixel(-12, -12), title: region.name, zIndex: 100 });
                    const markerContent = document.createElement("div");
                    markerContent.style.cssText = "width:28px;height:28px;line-height:28px;background:"+region.color+";color:white;border-radius:50%;text-align:center;font-weight:bold;font-size:14px;box-shadow:0 2px 6px rgba(0,0,0,0.4);border:3px solid white";
                    markerContent.innerText = region.id + 1;
                    marker.setContent(markerContent);
                    marker.on("click", function() {{
                        const infoWindow = new AMap.InfoWindow({ content: `<div style="padding:10px;min-width:200px;"><div style="font-weight:bold;margin-bottom:8px;color:${region.color};"><strong>■ ${region.name} (${region.id + 1})</strong></div><div style="font-size:12px;color:#666;"><p><strong>中心坐标：</strong><br/>${region.center[0].toFixed(6)}°, ${region.center[1].toFixed(6)}°</p><p style="margin-top:8px;"><strong>边界点数：</strong> ${region.boundary.length}</p></div></div>` , offset: new AMap.Pixel(0, -35) });
                        infoWindow.open(map, region.center);
                    }});
                    map.add(marker);
                    markers.push({ id: region.id, marker: marker });
                }}

                // 多边形点击：非选中 -> 临时选中（显示彩色与标号）；已临时选中 -> 取消临时选中
                polygon.on('click', function() {{
                    // region.selected 表示初始化选中，region._selected 表示用户点击临时选中
                    if (!region.selected && !region._selected) {{
                        region._selected = true;
                        polygon.setOptions({ fillColor: region.color, strokeColor: region.color, fillOpacity: 0.2 });
                        const newMarker = new AMap.Marker({ position: region.center, offset: new AMap.Pixel(-12, -12), title: region.name, zIndex: 100 });
                            const mc = document.createElement('div');
                            mc.style.cssText = "width:28px;height:28px;line-height:28px;background:"+region.color+";color:white;border-radius:50%;text-align:center;font-weight:bold;font-size:14px;box-shadow:0 2px 6px rgba(0,0,0,0.4);border:3px solid white";
                            mc.innerText = region.id + 1;
                        newMarker.setContent(mc);
                        map.add(newMarker);
                        markers.push({ id: region.id, marker: newMarker });
                        fillInfoPanel();
                    }} else if (region._selected) {{
                        region._selected = false;
                        polygon.setOptions({ fillColor: '#CCCCCC', strokeColor: '#999999', fillOpacity: 0.12 });
                        for (let i = markers.length - 1; i >= 0; i--) {{
                            if (markers[i].id === region.id) {{
                                map.remove(markers[i].marker);
                                markers.splice(i, 1);
                            }}
                        }}
                        fillInfoPanel();
                    }}
                }});

            }});

            const bounds = new AMap.Bounds([minLng, minLat], [maxLng, maxLat]);
            map.setBounds(bounds, false, [50, 50, 50, 50]);
            fillInfoPanel();
        }}

        function fillInfoPanel() {{
            const listContainer = document.getElementById("region-list");
            listContainer.innerHTML = "";
            regionsData.forEach(region => {{
                const isSelected = region.selected || region._selected;
                if (!isSelected) return;
                const item = document.createElement("div");
                item.className = "region-item";
                item.innerHTML = `<div class="region-name"><span class="region-color" style="background-color:${region.color}"></span>${region.name} (ID: ${region.id + 1})</div><div class="region-coords">中心: [${region.center[0].toFixed(4)}, ${region.center[1].toFixed(4)}]</div>`;
                item.addEventListener("click", function() {{
                    map.setCenter(region.center);
                    map.setZoom(16);
                    this.classList.toggle("active");
                }});
                listContainer.appendChild(item);
            }});
        }}

        (function start() {{
            function tryInit() {{
                if (typeof AMap !== 'undefined') {{
                    initMap();
                }} else {{
                    console.error('高德地图API 加载失败');
                }}
            }}
            if (document.readyState === 'loading') {{
                document.addEventListener('DOMContentLoaded', tryInit);
            }} else {{
                tryInit();
            }}
        }})();

        window.addEventListener("resize", function() {{ map.resize(); }});
    </script>
</body>
</html>"""

    result = html.replace('__TITLE__', title).replace('__REGIONS_JS__', regions_js)
    # 模板中使用了双大括号来防止 Python format 解析，写出时恢复为单大括号
    result = result.replace('{{', '{').replace('}}', '}')
    return result


def take_screenshot(url: str, output_path: str, width: int = 1920, height: int = 1200):
    if sync_playwright is None:
        print("[警告] 未安装 Playwright，无法进行截图")
        return False
    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception:
                print("[警告] Chromium 未安装，运行: python -m playwright install chromium")
                return False
            page = browser.new_page(viewport={'width': width, 'height': height})
            page.goto(url)
            page.wait_for_timeout(3000)
            page.screenshot(path=output_path, full_page=False)
            browser.close()
            print("[成功] 截图已保存: {}".format(output_path))
            return True
    except Exception as e:
        print("[错误] 截图失败: {}".format(str(e)))
        return False


def main():
    parser = argparse.ArgumentParser(
        description="地图区域可视化工具 - 显示指定序号的清扫区域",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：\n  python visualize_regions.py 0 1 2 3\n  python visualize_regions.py 37 38\n  python visualize_regions.py 0 1 2 --screenshot regions_map.png"
    )

    parser.add_argument('region_ids', nargs='*', type=int, help='要显示的区域序号（空格分隔，0-38对应1-39号区域）')
    parser.add_argument('--screenshot', type=str, help='生成截图文件的路径')
    parser.add_argument('--no-open', action='store_true', help='不自动打开浏览器')
    parser.add_argument('--title', type=str, default="清扫区域展示", help='页面标题')

    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    rectangles_path = os.path.join(script_dir, "rectangles.json")
    if not os.path.exists(rectangles_path):
        print("[错误] 找不到矩形数据文件: {}".format(rectangles_path))
        return

    rectangles = load_rectangles(rectangles_path)
    print("[信息] 总共加载了 {} 个区域".format(len(rectangles)))

    # 如果用户未指定任何 id，则不高亮任何区域（全部灰色）
    selected_ids = args.region_ids if args.region_ids else []
    print("[信息] 用户指定的区域序号: {}".format(selected_ids))

    # 生成 HTML
    html_content = generate_visualization_html(rectangles, selected_ids, args.title)

    temp_dir = os.path.join(script_dir, "tmp", "visualize")
    os.makedirs(temp_dir, exist_ok=True)

    html_path = os.path.join(temp_dir, 'index.html')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print("[成功] HTML文件已生成: {}".format(html_path))

    file_url = 'file:///{}'.format(html_path.replace('\\', '/'))
    print("[成功] 文件地址: {}".format(file_url))

    if args.screenshot:
        screenshot_path = args.screenshot
        if not os.path.isabs(screenshot_path):
            screenshot_path = os.path.abspath(screenshot_path)
        take_screenshot(file_url, screenshot_path)

    if not args.no_open:
        import webbrowser
        webbrowser.open(file_url)
        print("[成功] 浏览器已打开")
    else:
        print("[提示] 在浏览器中打开: {}".format(file_url))


if __name__ == '__main__':
    main()
