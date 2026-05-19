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
import socket
import subprocess
import sys
import time
import threading
import urllib.error
import urllib.request
from typing import List
import math

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


SERVER_STATE_FILE = 'http_server_state.json'
PAGE_SIGNATURE = 'visualize_regions_generated_page'
SERVER_FEATURE_VERSION = 'vehicle_poll_v1'
VEHICLE_API_BASE_URL = os.environ.get('CAR_TOOL_BASE_URL', 'http://36.212.131.89:19008')
VEHICLE_API_TOKEN = os.environ.get('CAR_TOOL_AUTH_TOKEN', 'sk453bkf923rnlfw93rtbgnkc29fgd')
VEHICLE_DEVICE_ID = os.environ.get('CAR_TOOL_VEHICLE_DEV_ID', 'UD130-2V310-41204-0730')
VEHICLE_POLL_INTERVAL = int(os.environ.get('CAR_TOOL_VEHICLE_POLL_INTERVAL', '10'))


def _out_of_china(lon: float, lat: float) -> bool:
    return lon < 72.004 or lon > 137.8347 or lat < 0.8293 or lat > 55.8271


def _transform_lat(x: float, y: float) -> float:
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * abs(x) ** 0.5
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin((y / 3.0) * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin((y / 12.0) * math.pi) + 320.0 * math.sin((y * math.pi) / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng(x: float, y: float) -> float:
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * abs(x) ** 0.5
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin((x / 3.0) * math.pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin((x / 12.0) * math.pi) + 300.0 * math.sin((x / 30.0) * math.pi)) * 2.0 / 3.0
    return ret


def wgs84_to_gcj02(lon: float, lat: float) -> tuple[float, float]:
    """将 WGS84 坐标转换为 GCJ-02 坐标。"""
    if _out_of_china(lon, lat):
        return lon, lat

    a = 6378245.0
    ee = 0.00669342162296594323
    dlat = _transform_lat(lon - 105.0, lat - 35.0)
    dlng = _transform_lng(lon - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = magic ** 0.5
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * math.pi)
    dlng = (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * math.pi)
    mg_lat = lat + dlat
    mg_lng = lon + dlng
    return mg_lng, mg_lat


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


def generate_visualization_html(all_regions: dict, selected_ids: List[int], task_groups: list = None, title: str = "清扫区域展示", session_path: str = '') -> str:
    # 任务自动色调色盘（8种高区分度颜色，视觉友好）
    TASK_PALETTE = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#F39C12', '#9B59B6', '#2ECC71', '#E74C3C', '#1ABC9C']
    DEFAULT_TASK_COLOR = '#1E3A5F'
    USER_SELECTED_COLOR = '#ADD8E6'

    # Enrich task_groups with default colors and normalize regions before serialization
    enriched_task_groups = []
    if task_groups:
        for i, task in enumerate(task_groups):
            enriched_task = dict(task)
            if 'color' not in enriched_task or not enriched_task['color']:
                enriched_task['color'] = TASK_PALETTE[i % len(TASK_PALETTE)]
            # Normalize regions: handle both int array and [{"id":N, "status":1}] formats
            regions = task.get('regions', [])
            normalized_regions = []
            region_statuses = {}
            for r in regions:
                if isinstance(r, dict):
                    rid = r['id']
                    normalized_regions.append(rid)
                    region_statuses[rid] = r.get('status', 1)
                else:
                    normalized_regions.append(r)
                    region_statuses[r] = 1
            enriched_task['regions'] = normalized_regions
            enriched_task['region_statuses'] = region_statuses
            # Generate task id if not provided (timestamp_sessionXX)
            if 'id' not in enriched_task:
                from datetime import datetime
                enriched_task['id'] = datetime.now().strftime('%y%m%d%H%M') + '_session' + str(i + 1)
            enriched_task_groups.append(enriched_task)

    # Build region-color mapping from task groups
    region_task_map = {}
    if enriched_task_groups:
        for i, task in enumerate(enriched_task_groups):
            color = task['color']
            for rid in task['regions']:
                if rid not in region_task_map:
                    region_task_map[rid] = {"color": color, "name": task.get('name', ''), "is_task_default": True}

    # 单任务模式：所有选中区域使用默认深蓝色
    single_task_color = DEFAULT_TASK_COLOR if not enriched_task_groups else None

    regions_with_colors = []
    for idx, (rid, region) in enumerate(sorted(all_regions.items())):
        task_info = region_task_map.get(rid, {})
        if rid in region_task_map:
            color = task_info["color"]
        elif single_task_color is not None and rid in selected_ids:
            color = single_task_color
        else:
            color = '#CCCCCC'
        regions_with_colors.append({
            'id': rid,
            'center': region['center'],
            'boundary': region['boundary'],
            'color': color,
            'task': task_info.get('name', ''),
            'is_task_default': task_info.get('is_task_default', False),
            'name': 'region_{}'.format(rid + 1),
            'selected': True if rid in selected_ids else False
        })

    regions_js = json.dumps(regions_with_colors, ensure_ascii=False)
    task_groups_js = json.dumps(enriched_task_groups if enriched_task_groups else [], ensure_ascii=False)

    _template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'visualize_template.html')
    with open(_template_dir, 'r', encoding='utf-8') as _f:
        html = _f.read()

    result = html.replace('__TITLE__', title).replace('__REGIONS_JS__', regions_js).replace('__TASK_GROUPS_JS__', task_groups_js)
    result = result.replace('__PAGE_SIGNATURE__', PAGE_SIGNATURE)
    result = result.replace('__SESSION_PATH__', session_path)
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


def _get_local_ip() -> str:
    """获取本机的局域网 IP 地址"""
    try:
        # 创建一个不连接的 socket 来获取本机 IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # 连接到一个公网地址（不真实发包）
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _find_free_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return int(s.getsockname()[1])


def _is_process_alive(pid: int) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _kill_process(pid: int):
    """终止指定PID的进程"""
    if not pid:
        return
    try:
        os.kill(pid, 9)
        time.sleep(0.5)
    except Exception:
        pass


def _wait_url_ready(url: str, retries: int = 20, timeout: float = 0.5):
    for _ in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=timeout):
                return True
        except (urllib.error.URLError, urllib.error.HTTPError):
            time.sleep(0.1)
    return False


def _url_has_expected_page(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=0.8) as resp:
            body = resp.read(4096).decode('utf-8', errors='ignore')
            return PAGE_SIGNATURE in body
    except (urllib.error.URLError, urllib.error.HTTPError):
        return False


def _load_server_state(state_path: str):
    if not os.path.exists(state_path):
        return None
    try:
        with open(state_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _save_server_state(state_path: str, host: str, port: int, pid: int, serve_dir: str = '', task_dir: str = ''):
    state = {
        'host': host,
        'port': port,
        'pid': pid,
        'serve_dir': os.path.abspath(serve_dir) if serve_dir else '',
        'task_dir': os.path.abspath(task_dir) if task_dir else '',
        'feature_version': SERVER_FEATURE_VERSION,
        'vehicle_dev_id': VEHICLE_DEVICE_ID,
        'vehicle_poll_interval': VEHICLE_POLL_INTERVAL,
    }
    with open(state_path, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _fetch_vehicle_info(dev_id: str, base_url: str = VEHICLE_API_BASE_URL, token: str = VEHICLE_API_TOKEN) -> dict:
    url = f"{base_url.rstrip('/')}/api/device/info/search"
    payload = json.dumps({'devId': dev_id}).encode('utf-8')
    request = urllib.request.Request(
        url,
        data=payload,
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        },
        method='POST',
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        return json.loads(response.read().decode('utf-8'))


def _normalize_vehicle_snapshot(payload: dict) -> dict:
    result = payload.get('result') if isinstance(payload, dict) else {}
    if not isinstance(result, dict):
        result = {}

    map_gps = result.get('mapGps')
    if isinstance(map_gps, str):
        try:
            map_gps = json.loads(map_gps)
        except Exception:
            map_gps = {}

    lat = None
    lon = None
    if isinstance(map_gps, dict):
        lat = map_gps.get('lat', map_gps.get('latitude'))
        lon = map_gps.get('lon', map_gps.get('lng', map_gps.get('longitude')))

    if lat is None or lon is None:
        return {
            'ok': False,
            'error': '车辆坐标缺失',
            'updated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'vehicle': None,
        }

    gcj_lng, gcj_lat = wgs84_to_gcj02(float(lon), float(lat))
    vehicle = {
        'devId': result.get('devId') or VEHICLE_DEVICE_ID,
        'plateId': result.get('plateId', ''),
        'status': result.get('status', ''),
        'operationalStatus': result.get('operationalStatus', ''),
        'offlineTime': result.get('offlineTime', ''),
        'batteryVoltage': result.get('batteryVoltage'),
        'speedMode': result.get('speedMode', ''),
        'raw_position': [float(lon), float(lat)],
        'position': [gcj_lng, gcj_lat],
        'gcj02_position': [gcj_lng, gcj_lat],
        'wgs84_position': [float(lon), float(lat)],
        'lat': float(lat),
        'lon': float(lon),
        'label': result.get('plateId') or result.get('devId') or '小车',
    }
    return {
        'ok': True,
        'code': payload.get('code', 200) if isinstance(payload, dict) else 200,
        'message': payload.get('message', '') if isinstance(payload, dict) else '',
        'updated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'vehicle': vehicle,
    }


def _find_pid_using_port(host: str, port: int):
    """查找占用指定端口的PID (使用 lsof, Linux 专用)"""
    try:
        result = subprocess.run(
            ['lsof', '-ti', ':{}'.format(port)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
        )
        pid_str = (result.stdout or '').strip()
        if pid_str:
            return int(pid_str)
    except Exception:
        pass
    return None


def _ensure_port_free(host: str, port: int, own_pid: int = 0):
    """确保端口可用，如果被其他进程占用则杀掉"""
    pid_on_port = _find_pid_using_port(host, port)
    if pid_on_port and pid_on_port != own_pid:
        print("[信息] 端口 {} 被 PID {} 占用，正在释放...".format(port, pid_on_port))
        _kill_process(pid_on_port)
        # 等待端口释放
        for _ in range(10):
            time.sleep(0.2)
            if not _find_pid_using_port(host, port):
                return True
        print("[警告] 端口 {} 未能释放".format(port))
        return False
    return True


def run_task_server(serve_dir: str = '', task_dir: str = '', host: str = '0.0.0.0', port: int = 8001, index_dir: str = ''):
    """启动一个支持静态文件 + POST /api/confirm 的 HTTP 服务器。
    由 subprocess 调用，作为独立进程运行。"""
    import datetime
    from http.server import HTTPServer, SimpleHTTPRequestHandler

    _task_dir = task_dir or serve_dir
    _index_dir = index_dir or _task_dir
    _params_dir = _index_dir if index_dir else _task_dir
    vehicle_state = {
        'ok': False,
        'error': '',
        'updated_at': '',
        'vehicle': None,
    }
    vehicle_lock = threading.Lock()

    def _refresh_vehicle_state():
        nonlocal vehicle_state
        try:
            raw_payload = _fetch_vehicle_info(VEHICLE_DEVICE_ID)
            snapshot = _normalize_vehicle_snapshot(raw_payload)
        except Exception as exc:
            snapshot = {
                'ok': False,
                'error': str(exc),
                'updated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'vehicle': None,
            }
        with vehicle_lock:
            vehicle_state = snapshot
        return snapshot

    def _vehicle_poll_loop():
        while True:
            _refresh_vehicle_state()
            time.sleep(max(1, VEHICLE_POLL_INTERVAL))

    polling_thread = threading.Thread(target=_vehicle_poll_loop, daemon=True)
    polling_thread.start()

    class _Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=serve_dir, **kwargs)

        def end_headers(self):
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
            super().end_headers()

        def do_OPTIONS(self):
            self.send_response(204)
            self.end_headers()

        def do_POST(self):
            if self.path == '/api/confirm':
                params_path = os.path.join(_params_dir, 'task_params.json')
                try:
                    content_length = int(self.headers.get('Content-Length', 0))
                    body = self.rfile.read(content_length).decode('utf-8')
                    req = json.loads(body) if body else {}
                    if os.path.exists(params_path):
                        with open(params_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                    else:
                        data = {}
                    # 同步前端传过来的完整任务数据
                    if 'tasks' in req:
                        data['tasks'] = req['tasks']
                    if 'selected_regions' in req:
                        data['selected_regions'] = req['selected_regions']
                    if 'selected_count' in req:
                        data['selected_count'] = req['selected_count']
                    data['execution_confirmed'] = True
                    data['confirmed_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    with open(params_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    self._json_reply(200, {"ok": True, "confirmed_at": data['confirmed_at']})
                except Exception as e:
                    self._json_reply(500, {"ok": False, "error": str(e)})
            elif self.path == '/api/toggle_region':
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length).decode('utf-8')
                req = json.loads(body)
                region_id = req.get('region_id')
                selected = req.get('selected', False)
                task_index = req.get('task_index', -1)
                params_path = os.path.join(_params_dir, 'task_params.json')
                try:
                    if os.path.exists(params_path):
                        with open(params_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                    else:
                        data = {"selected_regions": [], "selected_count": 0}
                    # 更新顶层 selected_regions
                    regions = data.get('selected_regions', [])
                    if selected and region_id not in regions:
                        regions.append(region_id)
                        regions.sort()
                    elif not selected and region_id in regions:
                        regions.remove(region_id)
                    data['selected_regions'] = regions
                    data['selected_count'] = len(regions)
                    # 更新对应任务的 selected_regions 和 regions（含status）
                    if task_index >= 0 and 'tasks' in data and isinstance(data['tasks'], list) and task_index < len(data['tasks']):
                        task = data['tasks'][task_index]
                        task_regions = task.get('selected_regions', [])
                        if selected and region_id not in task_regions:
                            task_regions.append(region_id)
                            task_regions.sort()
                        elif not selected and region_id in task_regions:
                            task_regions.remove(region_id)
                        task['selected_regions'] = task_regions
                        # 同步更新 regions 数组（对象格式 [{"id":N, "status":1}]）
                        task_all_regions = task.get('regions', [])
                        if selected:
                            if not any((r['id'] if isinstance(r, dict) else r) == region_id for r in task_all_regions):
                                task_all_regions.append({"id": region_id, "status": 1})
                                task_all_regions.sort(key=lambda x: x['id'] if isinstance(x, dict) else x)
                        else:
                            task_all_regions = [r for r in task_all_regions if (r['id'] if isinstance(r, dict) else r) != region_id]
                        task['regions'] = task_all_regions
                    with open(params_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    self._json_reply(200, {"ok": True, "selected_regions": regions, "selected_count": len(regions)})
                except Exception as e:
                    self._json_reply(500, {"ok": False, "error": str(e)})
            else:
                self.send_response(404)
                self.end_headers()

        def do_GET(self):
            if self.path == '/api/confirm':
                params_path = os.path.join(_params_dir, 'task_params.json')
                try:
                    with open(params_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    self._json_reply(200, {
                        "execution_confirmed": data.get('execution_confirmed', False),
                        "confirmed_at": data.get('confirmed_at', ''),
                    })
                except Exception as e:
                    self._json_reply(500, {"ok": False, "error": str(e)})
            elif self.path == '/api/task_params':
                params_path = os.path.join(_params_dir, 'task_params.json')
                try:
                    with open(params_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    self._json_reply(200, data)
                except Exception as e:
                    self._json_reply(500, {"ok": False, "error": str(e)})
            elif self.path == '/api/index':
                index_path = os.path.join(_index_dir, '.index')
                try:
                    if os.path.exists(index_path):
                        with open(index_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        self._json_reply(200, data)
                    else:
                        self._json_reply(200, {"exists": False, "message": ".index 文件尚未创建"})
                except Exception as e:
                    self._json_reply(500, {"ok": False, "error": str(e)})
            elif self.path == '/api/vehicle':
                with vehicle_lock:
                    payload = dict(vehicle_state)
                if not payload.get('updated_at'):
                    payload = _refresh_vehicle_state()
                self._json_reply(200, payload)
            else:
                super().do_GET()

        def _json_reply(self, code, obj):
            body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(body)

    server = HTTPServer((host, port), _Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


def start_or_reuse_background_http_server(directory: str, task_dir: str = '', index_dir: str = '', host: str = '0.0.0.0', port: int = 8001, page_rel_path: str = 'index.html'):
    state_path = os.path.join(directory, SERVER_STATE_FILE)
    state = _load_server_state(state_path)
    requested_dir = os.path.abspath(directory)

    if state:
        saved_host = state.get('host')
        saved_port = int(state.get('port', 0) or 0)
        saved_pid = int(state.get('pid', 0) or 0)
        saved_serve_dir = state.get('serve_dir', '')
        saved_task_dir = state.get('task_dir', '')
        saved_feature_version = state.get('feature_version', '')
        saved_vehicle_dev_id = state.get('vehicle_dev_id', '')
        saved_vehicle_poll_interval = int(state.get('vehicle_poll_interval', 0) or 0)
        saved_url = 'http://127.0.0.1:{}/{}'.format(saved_port, page_rel_path.lstrip('/'))
        requested_task_dir = os.path.abspath(task_dir) if task_dir else ''

        if (
            saved_host == host
            and saved_port == port
            and saved_serve_dir == requested_dir
            and saved_task_dir == requested_task_dir
            and saved_feature_version == SERVER_FEATURE_VERSION
            and saved_vehicle_dev_id == VEHICLE_DEVICE_ID
            and saved_vehicle_poll_interval == VEHICLE_POLL_INTERVAL
        ):
            if _is_process_alive(saved_pid) and _url_has_expected_page(saved_url):
                return {'url': saved_url, 'pid': saved_pid, 'reused': True, 'new_process': False}
            else:
                try:
                    os.remove(state_path)
                except Exception:
                    pass
        else:
            if saved_pid:
                print("[信息] 服务配置变化，终止旧进程 PID {} (旧目录: {})".format(saved_pid, saved_serve_dir or '未知'))
                _kill_process(saved_pid)
                try:
                    os.remove(state_path)
                except Exception:
                    pass

    # 根据绑定地址决定访问地址（0.0.0.0 使用 localhost）
    display_host_for_url = 'localhost' if host == '0.0.0.0' else host
    expected_url = 'http://{}:{}/index.html'.format(display_host_for_url, port)
    _ensure_port_free(host, port)

    # 通过 subprocess 启动 run_task_server，使其作为独立后台进程运行
    script_dir = os.path.dirname(os.path.abspath(__file__))
    index_dir_escaped = index_dir  # raw string preserves backslashes
    server_cmd_template = (
        'import sys; sys.path.insert(0, r"{script_dir}");'
        'from visualize_regions import run_task_server;'
        'run_task_server(r"{serve_dir}", r"{task_dir}", "{host}", __PORT__, r"{index_dir}")'
    ).format(script_dir=script_dir, serve_dir=directory, task_dir=task_dir or requested_dir, host=host, index_dir=index_dir_escaped or '')
    server_cmd = server_cmd_template.replace('__PORT__', str(port))

    # 将后台进程的 stdout/stderr 重定向到日志文件，便于排查崩溃或异常。
    out_log_path = os.path.join(directory, 'http_server.out.log')
    err_log_path = os.path.join(directory, 'http_server.err.log')
    try:
        out_log_f = open(out_log_path, 'a', encoding='utf-8')
        err_log_f = open(err_log_path, 'a', encoding='utf-8')
    except Exception:
        out_log_f = subprocess.DEVNULL
        err_log_f = subprocess.DEVNULL

    popen_kwargs = {
        'stdin': subprocess.DEVNULL,
        'stdout': out_log_f,
        'stderr': err_log_f,
        'cwd': directory,
        'start_new_session': True,  # Linux: 启动新会话
    }

    def _try_start(p: int, retry_on_port_conflict: bool = True):
        max_retries = 3
        for attempt in range(max_retries):
            # 先确保端口空闲（杀掉占用进程）
            if not _ensure_port_free(host, p):
                if attempt < max_retries - 1:
                    print("[警告] 端口 {} 无法释放，{} 秒后重试...".format(p, 2))
                    time.sleep(2)
                    continue
                else:
                    print("[错误] 端口 {} 无法释放".format(p))
                    return None
            
            # 再等待一下，确保进程真的释放了端口
            time.sleep(0.5)
            
            cmd = server_cmd_template.replace('__PORT__', str(p))
            proc = subprocess.Popen([sys.executable, '-c', cmd], **popen_kwargs)
            url = 'http://127.0.0.1:{}/{}'.format(p, page_rel_path.lstrip('/'))
            if _wait_url_ready(url):
                _save_server_state(state_path, host, p, proc.pid, directory, task_dir)
                #print("[成功] 服务器启动成功，端口 {}".format(p))
                return {'url': url, 'pid': proc.pid, 'reused': False, 'new_process': True}
            
            # 启动失败，杀掉新进程，准备重试
            _kill_process(proc.pid)
            occupying_pid = _find_pid_using_port(host, p)
            if occupying_pid:
                print("[信息] 端口 {} 仍被 PID {} 占用，尝试强制释放...".format(p, occupying_pid))
                _kill_process(occupying_pid)
            
            if attempt < max_retries - 1:
                print("[信息] 启动失败，{}秒后重试... (尝试 {}/{})".format(2, attempt + 1, max_retries))
                time.sleep(2)
        
        print("[错误] 尝试 {} 次后仍无法启动服务器，端口 {}".format(max_retries, p))
        return None

    result = _try_start(port)
    if result:
        return result

    raise RuntimeError("无法启动 HTTP 服务器，端口 {} 无法获得".format(port))


def main():
    parser = argparse.ArgumentParser(
        description="地图区域可视化工具 - 显示指定序号的清扫区域",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：\n  python visualize_regions.py 1 2 3\n  python visualize_regions.py 38 39\n  python visualize_regions.py 1 2 3 --screenshot regions_map.png\n（注意：命令行传入的序号为 1-based，即从 1 开始）"
    )

    parser.add_argument('region_ids', nargs='*', type=int, help='要显示的区域序号（空格分隔，1-39 对应第 1-39 号区域，脚本会自动转换为 0-based）')
    parser.add_argument('--tasks', type=str, help='JSON格式的任务分组: [{"name":"任务描述","regions":[0,1,2,3],"color":"#FF6B6B"}] — 不同任务用不同颜色显示')
    parser.add_argument('--tasks-file', type=str, help='从JSON文件读取任务分组（推荐在Windows PowerShell上使用）')
    parser.add_argument('--screenshot', type=str, help='生成截图文件的路径')
    parser.add_argument('--no-open', action='store_true', help='不自动打开浏览器')
    parser.add_argument('--port', type=int, default=8001, help='HTTP服务端口（默认 8001，会优先复用）')
    parser.add_argument('--title', type=str, default="清扫区域展示", help='页面标题')
    parser.add_argument('--output-dir', type=str, default=None, help='HTML文件输出目录（默认 scripts/tmp/visualize）')
    parser.add_argument('--task-dir', type=str, default=None, help='task_params.json 所在目录（默认与输出目录相同，session 模式下设为 SESSION_DIR）')
    parser.add_argument('--session-name', type=str, default='', help='会话子目录名（如 session1），用于 .index 文件监听路径')

    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    rectangles_path = os.path.join(script_dir, "rectangles.json")
    if not os.path.exists(rectangles_path):
        print("[错误] 找不到矩形数据文件: {}".format(rectangles_path))
        return

    rectangles = load_rectangles(rectangles_path)
    print("[信息] 总共加载了 {} 个区域".format(len(rectangles)))

    # 如果用户未指定任何 id，则不高亮任何区域（全部灰色）
    # 脚本接受 1-based 输入（例如 1 表示第 1 区域），在内部转换为 0-based
    selected_ids = []
    if args.region_ids:
        user_inputs = args.region_ids
        converted = []
        for uid in user_inputs:
            rid = uid - 1
            if rid < 0:
                print("[警告] 忽略无效序号 {}（必须 >= 1）".format(uid))
                continue
            if rid not in rectangles:
                print("[警告] 区域 {} 不存在（输入 {}）".format(uid, uid))
                continue
            converted.append(rid)
        selected_ids = converted
    task_groups = None

    # 解析任务分组
    if args.tasks_file:
        try:
            with open(args.tasks_file, 'r', encoding='utf-8') as f:
                task_groups = json.load(f)
            print("[成功] 从文件读取任务分组: {}".format(args.tasks_file))
        except Exception as e:
            print("[错误] 读取任务文件失败: {}".format(str(e)))
            return

    if args.tasks:
        try:
            task_groups = json.loads(args.tasks)
        except json.JSONDecodeError as e:
            print("[错误] JSON解析失败: {}".format(str(e)))
            print("[提示] 请检查 --tasks 参数的引号和格式")
            print("[提示] PowerShell 用法示例:")
            print('  python visualize_regions.py --tasks "[{\"name\":\"任务1\",\"regions\":[1,2],\"color\":\"#FF6B6B\"}]" --no-open')
            print("[提示] 或者使用文件方式（推荐）:")
            print("  python visualize_regions.py --tasks-file tasks.json --no-open")
            return

    if task_groups:
        # 任务分组中的 regions 支持两种格式：简单整数 或 {"id":N,"status":1} 对象
        selected_ids = []
        for task in task_groups:
            regions = task.get('regions', [])
            if not regions:
                continue
            # 提取区域ID（handle both formats）
            raw_ids = []
            for r in regions:
                if isinstance(r, dict):
                    raw_ids.append(r['id'])
                else:
                    raw_ids.append(r)
            # 判断是否为 1-based（没有 0 出现且所有值 >=1）
            if all(isinstance(r, int) and r >= 1 for r in raw_ids) and not any(r == 0 for r in raw_ids):
                converted = [r - 1 for r in raw_ids]
            else:
                converted = raw_ids
            # 过滤无效 id
            valid = []
            for r in converted:
                if r in rectangles:
                    valid.append(r)
                else:
                    print("[警告] 任务分组中区域 {} 不存在，已忽略".format(r if r >= 0 else r))
            task['regions'] = valid
            selected_ids.extend(valid)
        print("[信息] 任务分组: {}".format(json.dumps([{"name": t.get("name", ""), "count": len(t.get("regions", []))} for t in task_groups], ensure_ascii=False)))
    else:
        print("[信息] 用户指定的区域序号: {}".format(selected_ids))

    # 构建 session 显示路径（相对 project root）
    project_root = os.path.dirname(script_dir)  # car-tool/
    session_path_display = ''
    if args.task_dir:
        abs_task_dir = os.path.abspath(args.task_dir)
        rel = os.path.relpath(abs_task_dir, project_root).replace('\\', '/')
        if args.session_name:
            session_path_display = '{}/{}'.format(rel, args.session_name)
        else:
            session_path_display = rel

    # 生成 HTML
    html_content = generate_visualization_html(rectangles, selected_ids, task_groups, args.title, session_path_display)

    if args.output_dir:
        temp_dir = os.path.abspath(args.output_dir)
    else:
        temp_dir = os.path.join(script_dir, "tmp", "visualize")
    os.makedirs(temp_dir, exist_ok=True)

    # 服务器以项目根目录为静态根目录，便于通过 task/.../session... 访问生成页面
    serve_root = project_root

    html_path = os.path.join(temp_dir, 'index.html')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print("[成功] HTML文件已生成: {}".format(html_path))

    serve_dir = serve_root
    task_dir = os.path.abspath(args.task_dir) if args.task_dir else serve_dir
    index_dir = ''
    if args.session_name and args.task_dir:
        index_dir = os.path.join(task_dir, args.session_name)
    page_rel_path = os.path.relpath(html_path, project_root).replace('\\', '/')
    server_info = start_or_reuse_background_http_server(serve_dir, task_dir=task_dir, index_dir=index_dir, port=args.port, page_rel_path=page_rel_path)

    # 根据绑定的 host 决定显示地址
    server_url = server_info['url']
    # 从 server URL 提取实际端口（可能 fallback 到其他端口）
    try:
        actual_port = int(server_url.split(':')[-1].split('/')[0])
    except (ValueError, IndexError):
        actual_port = args.port
    
    # 获取本机 IP（0.0.0.0 监听所有网卡）
    local_ip = _get_local_ip()
    
    # 访问生成页面的相对路径
    local_url = 'http://{}:{}/{}'.format(local_ip, actual_port, page_rel_path)
    http_url = 'http://{}:{}/{}'.format(local_ip, actual_port, page_rel_path)
    
    # 显示多个访问地址
    print("[成功] 服务器监听: 0.0.0.0:{}".format(actual_port))
    print("[成功] 本地访问: {}".format(local_url))
    print("[成功] 网络访问: {}".format(http_url))

    # 显示 .index 监听路径
    if session_path_display:
        print("[信息] 监听路径: {}  (.index)".format(session_path_display))
    if server_info.get('reused'):
        pid = server_info.get('pid')
        if pid:
            print("[成功] 复用已有HTTP服务 (PID: {})".format(pid))
            print("[提示] 如需停止服务，可执行: taskkill /PID {} /F".format(pid))
        else:
            print("[成功] 复用端口 {} 上的现有页面服务".format(args.port))
    else:
        pid = server_info.get('pid')
        print("[成功] 后台HTTP服务已启动 (PID: {})".format(pid))
        print("[提示] 如需停止服务，可执行: kill {}".format(pid))

    if args.screenshot:
        screenshot_path = args.screenshot
        if not os.path.isabs(screenshot_path):
            screenshot_path = os.path.abspath(screenshot_path)
        take_screenshot(http_url, screenshot_path)

    if not args.no_open:
        import webbrowser
        webbrowser.open(http_url)
        print("[成功] 浏览器已打开")
    else:
        print("[提示] 在浏览器中打开: {}".format(http_url))


if __name__ == '__main__':
    main()

