import subprocess
import os
import time
import sys
from pathlib import Path
import streamlit as st
# 确保 analyze_crispresso.py 和 portal_gen.py 在同一目录
try:
    import portal_gen
except ImportError:
    portal_gen = None

# ================= 配置区域 =================
# 必须与 analyze_crispresso.py 中的 DEFAULT_OUTPUT_BASE 保持一致
DEFAULT_OUTPUT_BASE = Path("/data/lulab_commonspace/guozehua/crispresso_out")
CURRENT_SCRIPT_DIR = Path(__file__).parent.resolve()
ANALYSIS_SCRIPT = CURRENT_SCRIPT_DIR / "analyze_crispresso.py"
# ===========================================

st.set_page_config(page_title="CRISPResso Async UI", layout="wide")
st.title("CRISPResso 异步分析平台")
# 假设 run.sh 里设置的端口是 8000，且服务器 IP 可访问
# 这里为了通用性，可以用相对提示，或者让用户知道端口
PORTAL_PORT = 8505
# 获取当前浏览器 URL 的主机名比较困难，通常建议硬编码服务器 IP 或者提示用户使用相同 IP
st.markdown(f"""
**模式**: 异步后台任务 (Fire-and-Forget)
**数据中心**: `{DEFAULT_OUTPUT_BASE}`  
**查看所有任务**: [点击打开任务监控门户 (http://<Server_IP>:{PORTAL_PORT})](http://202.120.41.69:{PORTAL_PORT}) 
*(请将链接中的 0.0.0.0 替换为您服务器的实际 IP)*
""")

# ================= Sidebar =================
with st.sidebar:
    st.header("运行参数")
    executable = st.text_input("CRISPResso 路径", value="CRISPResso", help="建议填绝对路径，例如 /home/user/miniconda3/envs/bio/bin/CRISPResso")
    sample_name = st.text_input("样本名称 (必填)", value="Sample_01")
    
    st.divider()
    min_read_length = st.number_input("最小读长", value=0)
    min_base_quality = st.number_input("最小质量", value=0)
    n_processes = st.number_input("CPU核心数", value=4)

# ================= Main Interface =================
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("输入文件 (服务器绝对路径)")
    fastq_r1_path = st.text_input("FASTQ R1 路径")
    fastq_r2_path = st.text_input("FASTQ R2 路径 (可选)")

    with st.expander("🛠️ 高级：非重叠拼接 (中间填 N)", expanded=True):
        st.info("当 PE Reads 不重叠且参考序列中间含 N 时使用。")
        n_padding = st.number_input("中间填充 N 的数量 (0=标准模式)", value=0)

with col_right:
    st.subheader("序列信息")
    amplicon_seq = st.text_area("扩增子序列 (5'->3')", height=150)
    guide_seq = st.text_area("sgRNA 序列", height=80)

run_clicked = st.button("🚀 启动后台任务", type="primary")

if run_clicked:
    # --- 1. 基础校验 ---
    errors = []
    if not fastq_r1_path or not amplicon_seq or not guide_seq or not sample_name:
        st.error("❌ 请填写所有必填项（R1, 样本名, 序列信息）")
        st.stop()
    if n_padding > 0 and not fastq_r2_path:
        st.error("❌ 拼接模式必须提供 R2")
        st.stop()
    
    # 检查 analyze_crispresso.py 是否存在
    if not ANALYSIS_SCRIPT.exists():
        st.error(f"❌ 找不到后台脚本: {ANALYSIS_SCRIPT}")
        st.stop()

    # --- 2. 准备独立的任务目录 ---
    # 格式: Job_YYYYMMDD_HHMMSS_样本名
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    safe_name = "".join([c for c in sample_name if c.isalnum() or c in ('-', '_')])
    job_folder_name = f"Job_{timestamp}_{safe_name}"
    job_dir = DEFAULT_OUTPUT_BASE / job_folder_name
    
    try:
        job_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        st.error(f"无法创建目录: {e}")
        st.stop()

    log_file = job_dir / "CRISPResso_RUNNING_LOG.txt"

    # --- 3. 构造 Shell 命令 ---
    # 我们不直接调用 function，而是构造一个 shell 字符串扔给 nohup
    
    # 拼接参数
    cmd_parts = [
        "python", f'"{ANALYSIS_SCRIPT}"',
        "--fastq_r1", f'"{fastq_r1_path}"',
        "--amplicon", f'"{amplicon_seq.strip()}"',
        "--guide", f'"{guide_seq.strip()}"',
        "--output", f'"{job_dir}"', # 直接传入绝对路径
        "--name", f'"{safe_name}"',
        "--executable", f'"{executable}"'
    ]
    
    if fastq_r2_path:
        cmd_parts.extend(["--fastq_r2", f'"{fastq_r2_path}"'])
    if n_padding > 0:
        cmd_parts.extend(["--n_padding", str(n_padding)])
    if min_read_length > 0:
        cmd_parts.extend(["--min_read_length", str(min_read_length)])
    if min_base_quality > 0:
        cmd_parts.extend(["--min_base_quality", str(min_base_quality)])
    if n_processes > 0:
        cmd_parts.extend(["--n_processes", str(n_processes)])

    full_cmd_str = " ".join(cmd_parts)

    # 构造 nohup 命令: (cmd) > log 2>&1 & echo $!
    # echo $! 用于获取 PID
    nohup_cmd = f"nohup {full_cmd_str} > {log_file} 2>&1 & echo $!"

    st.info("正在提交任务...")
    
    try:
        # 执行 nohup
        # 使用 shell=True 来支持 nohup 和重定向
        process = subprocess.Popen(nohup_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()
        
        # stdout 的第一行应该是 PID (因为 echo $!)
        if stdout:
            pid = stdout.strip().split('\n')[-1]
        else:
            pid = "Unknown"

        # --- 4. 立即更新 Portal ---
        # 这样用户打开 index.html 就能立刻看到处于“运行中”的任务
        if portal_gen:
            try:
                portal_gen.generate_portal()
            except Exception:
                pass

        # --- 5. 反馈结果 ---
        st.success(f"✅ 任务已后台启动！ PID: **{pid}**")
        
        st.markdown(f"""
        **任务详情**:
        - **任务ID**: `{job_folder_name}`
        - **日志文件**: `{log_file}`
        - **输出目录**: `{job_dir}`
        
        👉 **[点击这里下载/查看日志文件]** (需通过文件浏览器访问 `{log_file}`)
        
        请访问 **Portal 门户页面** 查看进度。您可以关闭此页面，任务不会中断。
        """)
        
        # 可选：显示日志文件的前几行，确认开始运行
        time.sleep(1) # 等1秒让日志生成
        if log_file.exists():
            with open(log_file, 'r') as f:
                head = f.read(500)
            with st.expander("查看实时日志预览 (前500字符)"):
                st.code(head)

    except Exception as e:
        st.error(f"提交失败: {e}")

st.caption("Tasks are running in background via nohup.")