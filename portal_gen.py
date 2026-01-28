#!/usr/bin/env python3
"""
Portal Generator for CRISPResso Analysis (Grouped & Cleanable).
Features:
1. Groups tasks into 'Active/Success' and 'Failed/Error'.
2. Provides copy-pasteable 'rm -rf' commands for easy cleanup.
3. Auto-detects report HTML files.
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
        h2 {{ margin-top: 0; }}
        .card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 30px; }}
        
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; table-layout: fixed; }}
        th, td {{ text-align: left; padding: 12px; border-bottom: 1px solid #ddd; word-wrap: break-word; }}
        th {{ background-color: #f8f9fa; color: #333; font-weight: 600; border-top: 2px solid #ddd; }}
        tr:hover {{ background-color: #f1f1f1; }}
        
        /* 状态颜色 */
        .status-running {{ color: #e67e22; font-weight: bold; }}
        .status-done {{ color: #27ae60; font-weight: bold; }}
        .status-error {{ color: #c0392b; font-weight: bold; }}
        
        a {{ text-decoration: none; color: #007bff; }}
        a:hover {{ text-decoration: underline; }}
        
        .refresh-btn {{ position: absolute; top: 20px; right: 20px; padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }}
        .path-info {{ font-size: 0.85em; color: #666; font-family: monospace; display: block; margin-top: 4px; }}
        
        /* 清理命令样式 */
        .cmd-code {{
            background: #fff0f0;
            border: 1px solid #ffcccc;
            color: #d63031;
            padding: 4px 8px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 0.85em;
            cursor: pointer;
            display: inline-block;
            user-select: all; /* 点击即可全选 */
        }}
        .cmd-code:hover {{ background: #ffe6e6; }}
        .cmd-hint {{ font-size: 0.8em; color: #999; margin-left: 5px; }}
        
        /* 分区标题颜色 */
        .header-success {{ border-left: 5px solid #27ae60; padding-left: 10px; color: #2c3e50; }}
        .header-error {{ border-left: 5px solid #c0392b; padding-left: 10px; color: #c0392b; }}
    </style>
    <script>
        // 每60秒自动刷新一次
        setTimeout(function(){{ location.reload(); }}, 60000);
    </script>
</head>
<body>
    <button class="refresh-btn" onclick="location.reload()">刷新状态</button>
    
    <div style="margin-bottom: 20px;">
        <h1>🧬 CRISPResso 任务看板</h1>
        <p style="color: #666;">数据根目录: <code>{root_dir}</code> | 更新时间: {update_time}</p>
    </div>

    <div class="card">
        <h2 class="header-success">🚀 进行中 & 已完成 (Active Tasks)</h2>
        {table_active}
    </div>

    <div class="card">
        <h2 class="header-error">❌ 异常 & 失败记录 (Failed / Errors)</h2>
        <p>💡 提示：点击红色的清理命令可直接全选，复制到服务器终端运行即可删除该记录。</p>
        {table_failed}
    </div>
</body>
</html>
"""

TABLE_HEADER_TEMPLATE = """
<table>
    <thead>
        <tr>
            <th style="width: 20%;">任务名称</th>
            <th style="width: 15%;">提交时间</th>
            <th style="width: 10%;">状态</th>
            <th style="width: 10%;">日志</th>
            <th style="width: {result_col_width};">{result_col_name}</th>
        </tr>
    </thead>
    <tbody>
        {rows}
    </tbody>
</table>
"""

def analyze_job_status(log_file: Path):
    """
    分析任务状态。
    返回: (Status_Category, HTML_String)
    Category: 'DONE', 'RUNNING', 'ERROR'
    """
    if not log_file.exists():
        return 'ERROR', '<span class="status-error">无日志 (启动失败?)</span>'
    
    try:
        # 读取日志最后几行
        with open(log_file, 'rb') as f:
            try:  # Seek to end
                f.seek(-4096, 2) 
            except OSError: # File too small
                f.seek(0)
            last_content = f.read().decode('utf-8', errors='ignore')
            
        if "[Status] Job Completed Successfully" in last_content:
            return 'DONE', '<span class="status-done">已完成 ✅</span>'
        elif "Error" in last_content or "Exception" in last_content or "Traceback" in last_content:
            return 'ERROR', '<span class="status-error">报错 ❌</span>'
        else:
            return 'RUNNING', '<span class="status-running">运行中 ⏳</span>'
    except Exception:
        return 'ERROR', '<span class="status-error">读取异常 ❓</span>'

def find_report_html(job_dir: Path):
    """智能搜索报告文件"""
    # 策略: 搜索所有子目录中的 html 文件
    try:
        html_candidates = list(job_dir.rglob("*.html"))
    except Exception:
        return None
    
    best_candidate = None
    for html in html_candidates:
        if html.name == "index.html": continue
        if "report" in html.name.lower(): return html
        if "crispresso_on" in html.name.lower(): best_candidate = html
            
    return best_candidate

def generate_row_html(job, status_html, result_content):
    return f"""
        <tr>
            <td><strong>{job['name']}</strong></td>
            <td>{job['time']}</td>
            <td>{status_html}</td>
            <td><a href="./{job['name']}/CRISPResso_RUNNING_LOG.txt" target="_blank">查看日志</a></td>
            <td>{result_content}</td>
        </tr>
    """

def generate_portal():
    if not ROOT_DIR.exists():
        print(f"Directory {ROOT_DIR} does not exist.")
        return

    # 1. 扫描任务
    jobs = []
    for item in ROOT_DIR.iterdir():
        if item.is_dir() and item.name.startswith("Job_"):
            try:
                # 格式: Job_YYYYMMDD_HHMMSS_SampleName
                sort_key = item.name 
                parts = item.name.split('_')
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
    
    # 按时间倒序
    jobs.sort(key=lambda x: x['sort'], reverse=True)

    rows_active = ""
    rows_failed = ""
    
    count_active = 0
    count_failed = 0

    # 2. 分类处理
    for job in jobs:
        job_dir = job['path']
        log_file = job_dir / "CRISPResso_RUNNING_LOG.txt"
        
        status_cat, status_html = analyze_job_status(log_file)
        
        # === 成功/进行中 组 ===
        if status_cat in ['DONE', 'RUNNING']:
            report_file = find_report_html(job_dir)
            if report_file:
                rel_path = report_file.relative_to(ROOT_DIR)
                result_content = f'<a href="./{rel_path}" target="_blank">📄 查看报告 ({report_file.name})</a>'
                result_content += f'<div class="path-info">{rel_path}</div>'
            else:
                result_content = '<span style="color:#999">等待生成...</span>'
            
            rows_active += generate_row_html(job, status_html, result_content)
            count_active += 1
            
        # === 失败/错误 组 ===
        else:
            # 生成清理命令
            clean_cmd = f"rm -rf {job_dir}"
            result_content = f'<code class="cmd-code" title="点击全选，复制去终端运行">{clean_cmd}</code>'
            
            rows_failed += generate_row_html(job, status_html, result_content)
            count_failed += 1

    # 3. 组装表格
    if count_active > 0:
        table_active = TABLE_HEADER_TEMPLATE.format(
            result_col_width="45%", result_col_name="结果报告", rows=rows_active
        )
    else:
        table_active = "<p style='padding:20px; color:#666;'>暂无活跃任务。</p>"

    if count_failed > 0:
        table_failed = TABLE_HEADER_TEMPLATE.format(
            result_col_width="45%", result_col_name="清理命令 (Server)", rows=rows_failed
        )
    else:
        table_failed = "<p style='padding:20px; color:#27ae60;'>暂无失败记录，太棒了！</p>"

    # 4. 生成最终HTML
    final_html = HTML_TEMPLATE.format(
        root_dir=ROOT_DIR,
        update_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        table_active=table_active,
        table_failed=table_failed
    )

    try:
        with open(HTML_FILE, 'w') as f:
            f.write(final_html)
        print(f"Portal updated at: {HTML_FILE}")
    except Exception as e:
        print(f"Error writing portal file: {e}")

if __name__ == "__main__":
    generate_portal()