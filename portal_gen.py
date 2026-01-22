#!/usr/bin/env python3
"""
Portal Generator for CRISPResso Analysis (Robust Version).
Scans the output directory and generates an index.html dashboard.
Auto-detects report HTML files regardless of naming convention.
"""
import os
import datetime
from pathlib import Path

# 定义硬编码的输出根目录 (必须与 analyze_crispresso.py 一致)
ROOT_DIR = Path("/data/lulab_commonspace/guozehua/crispresso_out")
HTML_FILE = ROOT_DIR / "index.html"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>CRISPResso 任务监控门户</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 20px; background-color: #f4f6f9; }}
        h1 {{ color: #333; }}
        .card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; table-layout: fixed; }}
        th, td {{ text-align: left; padding: 12px; border-bottom: 1px solid #ddd; word-wrap: break-word; }}
        th {{ background-color: #007bff; color: white; }}
        tr:hover {{ background-color: #f1f1f1; }}
        .status-running {{ color: #e67e22; font-weight: bold; }}
        .status-done {{ color: #27ae60; font-weight: bold; }}
        .status-error {{ color: #c0392b; font-weight: bold; }}
        a {{ text-decoration: none; color: #3498db; }}
        a:hover {{ text-decoration: underline; }}
        .refresh-btn {{ position: absolute; top: 20px; right: 20px; padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }}
        .path-info {{ font-size: 0.85em; color: #666; font-family: monospace; }}
    </style>
    <script>
        // 每60秒自动刷新一次
        setTimeout(function(){{ location.reload(); }}, 60000);
    </script>
</head>
<body>
    <button class="refresh-btn" onclick="location.reload()">刷新状态</button>
    <div class="card">
        <h1>🧬 CRISPResso 任务列表</h1>
        <p><strong>数据根目录:</strong> {root_dir}</p>
        <p><strong>最后更新时间:</strong> {update_time}</p>
        <p>💡 提示：请确保通过 HTTP 服务 (Run.sh启动的端口) 访问此页面，否则报告中的图标可能无法显示。</p>
        <table>
            <thead>
                <tr style="background: #eee;">
                    <th style="width: 25%;">任务名称 (ID)</th>
                    <th style="width: 15%;">提交时间</th>
                    <th style="width: 10%;">状态</th>
                    <th style="width: 10%;">日志</th>
                    <th style="width: 40%;">结果报告</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
    </div>
</body>
</html>
"""

def get_job_status(log_file: Path):
    """根据日志文件特征推测任务状态"""
    if not log_file.exists():
        return '<span class="status-error">无日志</span>'
    
    try:
        # 读取日志最后几行
        with open(log_file, 'rb') as f:
            try:  # Seek to end
                f.seek(-2048, 2) 
            except OSError: # File too small
                f.seek(0)
            last_content = f.read().decode('utf-8', errors='ignore')
            
        if "[Status] Job Completed Successfully" in last_content:
            return '<span class="status-done">已完成 ✅</span>'
        elif "Error" in last_content or "Exception" in last_content or "Traceback" in last_content:
            return '<span class="status-error">可能报错 ❌</span>'
        else:
            return '<span class="status-running">运行中 ⏳</span>'
    except Exception:
        return '<span class="status-running">运行中 ⏳</span>'

def find_report_html(job_dir: Path):
    """
    智能搜索报告文件。
    CRISPResso 的输出结构可能是:
    1. Job/CRISPResso_on_Name/CRISPResso2_report.html (标准)
    2. Job/CRISPResso_on_Name/CRISPResso_on_Name.html (旧版/特定设置)
    3. Job/CRISPResso_on_Name.html (异常情况)
    """
    # 策略 1: 搜索所有子目录中的 html 文件
    html_candidates = list(job_dir.rglob("*.html"))
    
    best_candidate = None
    
    for html in html_candidates:
        # 忽略 index.html (如果是门户本身)
        if html.name == "index.html":
            continue
            
        # 优先寻找名字里带 report 的
        if "report" in html.name.lower():
            return html
        
        # 其次寻找名字里带 CRISPResso_on 的
        if "crispresso_on" in html.name.lower():
            best_candidate = html
            
    return best_candidate

def generate_portal():
    if not ROOT_DIR.exists():
        print(f"Directory {ROOT_DIR} does not exist.")
        return

    # 扫描所有 Job_ 开头的子目录
    jobs = []
    for item in ROOT_DIR.iterdir():
        if item.is_dir() and item.name.startswith("Job_"):
            # 解析时间戳用于排序
            try:
                # 格式: Job_YYYYMMDD_HHMMSS_SampleName
                # 字符串排序对于 YYYYMMDD_HHMMSS 是有效的
                sort_key = item.name 
                parts = item.name.split('_')
                # 简单展示: 2026-01-22 20:39
                display_time = f"{parts[1][:4]}-{parts[1][4:6]}-{parts[1][6:]} {parts[2][:2]}:{parts[2][2:]}"
            except:
                sort_key = item.name
                display_time = "Unknown"
            
            jobs.append({
                "path": item,
                "name": item.name,
                "time": display_time,
                "sort": sort_key
            })
    
    # 按时间倒序排列 (最新的在最上面)
    jobs.sort(key=lambda x: x['sort'], reverse=True)

    rows_html = ""
    for job in jobs:
        job_dir = job['path']
        log_file = job_dir / "CRISPResso_RUNNING_LOG.txt"
        
        # === 智能查找报告 ===
        report_file = find_report_html(job_dir)
        
        if report_file:
            # 计算相对路径: 从 ROOT_DIR 到 report_file
            # 例如: ./Job_XXX/CRISPResso_on_YYY/report.html
            rel_path = report_file.relative_to(ROOT_DIR)
            result_link = f'<a href="./{rel_path}" target="_blank">📄 查看报告 ({report_file.name})</a>'
            result_path_display = f'<div class="path-info">{rel_path}</div>'
        else:
            result_link = '<span style="color:#999">等待生成或未找到...</span>'
            result_path_display = ''
        
        status = get_job_status(log_file)
        
        # Log 链接
        if log_file.exists():
             log_link = f'<a href="./{job["name"]}/{log_file.name}" target="_blank">查看日志</a>'
        else:
             log_link = "-"

        rows_html += f"""
            <tr>
                <td><strong>{job['name']}</strong></td>
                <td>{job['time']}</td>
                <td>{status}</td>
                <td>{log_link}</td>
                <td>
                    {result_link}
                    {result_path_display}
                </td>
            </tr>
        """

    final_html = HTML_TEMPLATE.format(
        root_dir=ROOT_DIR,
        update_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        rows=rows_html
    )

    try:
        with open(HTML_FILE, 'w') as f:
            f.write(final_html)
        print(f"Portal updated at: {HTML_FILE}")
    except Exception as e:
        print(f"Error writing portal file: {e}")

if __name__ == "__main__":
    generate_portal()