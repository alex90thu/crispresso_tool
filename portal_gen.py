#!/usr/bin/env python3
"""
Portal Generator for CRISPResso Analysis.
Scans the output directory and generates an index.html dashboard.
"""
import os
import datetime
from pathlib import Path

# 定义硬编码的输出根目录
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
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        th, td {{ text-align: left; padding: 12px; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #007bff; color: white; }}
        tr:hover {{ background-color: #f1f1f1; }}
        .status-running {{ color: #e67e22; font-weight: bold; }}
        .status-done {{ color: #27ae60; font-weight: bold; }}
        .status-error {{ color: #c0392b; font-weight: bold; }}
        a {{ text-decoration: none; color: #3498db; }}
        a:hover {{ text-decoration: underline; }}
        .refresh-btn {{ position: absolute; top: 20px; right: 20px; padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }}
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
        <p>数据根目录: {root_dir}</p>
        <p>最后更新时间: {update_time}</p>
        <table>
            <thead>
                <tr>
                    <th>任务名称 (ID)</th>
                    <th>提交时间</th>
                    <th>状态推测</th>
                    <th>日志</th>
                    <th>结果文件夹</th>
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

def get_job_status(job_dir: Path, log_file: Path):
    """根据文件特征推测任务状态"""
    if not log_file.exists():
        return '<span class="status-error">无日志</span>'
    
    # 检查是否有完成标记 (CRISPResso2 通常会生成 report html)
    # 或者我们在 analyze_crispresso.py 结束时打印的特殊标记
    try:
        # 读取日志最后几行
        with open(log_file, 'rb') as f:
            try:  # Seek to end
                f.seek(-1024, 2) 
            except OSError: # File too small
                f.seek(0)
            last_content = f.read().decode('utf-8', errors='ignore')
            
        if "[Status] Job Completed Successfully" in last_content:
            return '<span class="status-done">已完成 ✅</span>'
        elif "Error" in last_content or "Exception" in last_content:
            return '<span class="status-error">可能报错 ❌</span>'
        else:
            return '<span class="status-running">运行中 ⏳</span>'
    except Exception:
        return '<span class="status-running">运行中 ⏳</span>'

def generate_portal():
    if not ROOT_DIR.exists():
        print(f"Directory {ROOT_DIR} does not exist.")
        return

    # 扫描所有 Job_ 开头的子目录
    jobs = []
    for item in ROOT_DIR.iterdir():
        if item.is_dir() and item.name.startswith("Job_"):
            # 解析时间戳
            try:
                # 格式: Job_YYYYMMDD_HHMMSS_SampleName
                parts = item.name.split('_')
                ts_str = f"{parts[1]} {parts[2][:2]}:{parts[2][2:]}" # 简单格式化
                sort_key = item.name # 字典序正好按时间排
            except:
                ts_str = "Unknown"
                sort_key = item.name
            
            jobs.append({
                "path": item,
                "name": item.name,
                "time": ts_str,
                "sort": sort_key
            })
    
    # 按时间倒序排列
    jobs.sort(key=lambda x: x['sort'], reverse=True)

    rows_html = ""
    for job in jobs:
        job_dir = job['path']
        log_file = job_dir / "CRISPResso_RUNNING_LOG.txt"
        
        # 查找结果文件夹 (CRISPResso_on_...)
        result_link = "等待生成..."
        for sub in job_dir.iterdir():
            if sub.is_dir() and sub.name.startswith("CRISPResso_on_"):
                # 相对路径链接
                result_link = f'<a href="./{job["name"]}/{sub.name}/CRISPResso2_report.html" target="_blank">查看报告</a>'
                break
        
        status = get_job_status(job_dir, log_file)
        
        rows_html += f"""
            <tr>
                <td>{job['name']}</td>
                <td>{job['time']}</td>
                <td>{status}</td>
                <td><a href="./{job['name']}/CRISPResso_RUNNING_LOG.txt" target="_blank">查看日志</a></td>
                <td>{result_link}</td>
            </tr>
        """

    final_html = HTML_TEMPLATE.format(
        root_dir=ROOT_DIR,
        update_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        rows=rows_html
    )

    with open(HTML_FILE, 'w') as f:
        f.write(final_html)
    
    print(f"Portal updated at: {HTML_FILE}")

if __name__ == "__main__":
    generate_portal()