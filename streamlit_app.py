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

# 硬编码的可执行文件路径 (用户要求隐藏输入框)
# 如果环境变量里找不到，请修改这里为绝对路径，例如 "/home/user/bin/CRISPResso"
CRISPRESSO_EXECUTABLE = "CRISPResso" 
# ===========================================

st.set_page_config(page_title="CRISPResso Async UI", layout="wide")

# 初始化 Session State 用于存储提交后的结果
if 'last_job_info' not in st.session_state:
    st.session_state['last_job_info'] = None

st.title("CRISPResso 异步分析平台")

# 获取 Portal 端口 (假设 run.sh 里配置的是 8505)
PORTAL_PORT = "8505"  
portal_url = f"http://{st.session_state.get('server_ip', '202.120.41.69')}:{PORTAL_PORT}"

st.markdown(f"""
**模式**: 异步后台任务 (Fire-and-Forget)
**数据中心**: `{DEFAULT_OUTPUT_BASE}`  
**任务监控**: [点击打开任务监控门户 (Index.html)]({portal_url}) *(需确认 run.sh 中的端口配置)*
""")

# ================= Sidebar (精简版) =================
with st.sidebar:
    st.header("运行参数")
    # 已移除 executable 和 sample_name 输入框
    
    st.info("💡 样本名称将在点击运行后弹出输入。")
    st.divider()
    
    min_read_length = st.number_input("最小读长 (0=不限制)", value=0)
    min_base_quality = st.number_input("最小质量 (0=不限制)", value=0)
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

# ================= 核心逻辑函数 =================

def submit_job(sample_name, r1, r2, amp, guide, padding, min_len, min_qual, n_proc):
    """实际执行提交任务的逻辑"""
    
    # 1. 准备目录
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    safe_name = "".join([c for c in sample_name if c.isalnum() or c in ('-', '_')])
    # 格式优化：把用户输入的名称放在前面，方便看
    job_folder_name = f"Job_{timestamp}_{safe_name}" 
    job_dir = DEFAULT_OUTPUT_BASE / job_folder_name
    
    try:
        job_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return False, f"无法创建目录: {e}", None

    log_file = job_dir / "CRISPResso_RUNNING_LOG.txt"

    # 2. 构造命令
    cmd_parts = [
        "python", f'"{ANALYSIS_SCRIPT}"',
        "--fastq_r1", f'"{r1}"',
        "--amplicon", f'"{amp.strip()}"',
        "--guide", f'"{guide.strip()}"',
        "--output", f'"{job_dir}"',
        "--name", f'"{safe_name}"',
        "--executable", f'"{CRISPRESSO_EXECUTABLE}"' # 使用头部定义的常量
    ]
    
    if r2:
        cmd_parts.extend(["--fastq_r2", f'"{r2}"'])
    if padding > 0:
        cmd_parts.extend(["--n_padding", str(padding)])
    if min_len > 0:
        cmd_parts.extend(["--min_read_length", str(min_len)])
    if min_qual > 0:
        cmd_parts.extend(["--min_base_quality", str(min_qual)])
    if n_proc > 0:
        cmd_parts.extend(["--n_processes", str(n_proc)])

    full_cmd_str = " ".join(cmd_parts)
    nohup_cmd = f"nohup {full_cmd_str} > {log_file} 2>&1 & echo $!"

    # 3. 执行
    try:
        process = subprocess.Popen(nohup_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()
        pid = stdout.strip().split('\n')[-1] if stdout else "Unknown"
        
        # 4. 触发 Portal 刷新
        if portal_gen:
            try:
                portal_gen.generate_portal()
            except:
                pass
        
        return True, pid, {
            "job_id": job_folder_name,
            "log": log_file,
            "dir": job_dir,
            "pid": pid,
            "name": safe_name
        }
    except Exception as e:
        return False, str(e), None


# ================= 模态对话框 (Dialog) =================
@st.dialog("🏷️ 为当前任务命名")
def name_submission_dialog():
    st.warning("请务必输入一个清晰的样本名称，以便后续查找！")
    
    # 获取当前时间作为默认后缀，防止用户懒得填
    default_val = f"Sample_{time.strftime('%H%M')}"
    user_input_name = st.text_input("样本名称", value="", placeholder="例如: 20260122_Tomato_Mutant_1")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("取消"):
            st.rerun()
            
    with col2:
        if st.button("✅ 确认并提交", type="primary"):
            if not user_input_name.strip():
                st.error("名称不能为空！")
            else:
                with st.spinner("正在提交后台任务..."):
                    success, msg, info = submit_job(
                        user_input_name, 
                        fastq_r1_path, 
                        fastq_r2_path, 
                        amplicon_seq, 
                        guide_seq, 
                        n_padding, 
                        min_read_length, 
                        min_base_quality, 
                        n_processes
                    )
                    
                    if success:
                        # 将结果存入 session_state 以便在弹窗关闭后显示
                        st.session_state['last_job_info'] = info
                        st.rerun() # 重新运行以关闭弹窗并显示结果
                    else:
                        st.error(f"提交失败: {msg}")

# ================= 触发逻辑 =================

# 1. 显示上次提交成功的消息 (如果存在)
if st.session_state['last_job_info']:
    info = st.session_state['last_job_info']
    st.success(f"✅ 任务 **{info['name']}** 已后台启动！ PID: **{info['pid']}**")
    st.markdown(f"""
    - **日志文件**: `{info['log']}`
    - **输出目录**: `{info['dir']}`
    
    请访问 **Portal 门户页面** 查看进度。您可以继续提交下一个任务。
    """)
    # 添加一个按钮清除消息
    if st.button("开始新任务 (清除上方消息)"):
        st.session_state['last_job_info'] = None
        st.rerun()
    st.divider()

# 2. 准备提交按钮
run_clicked = st.button("🚀 准备提交任务", type="primary")

if run_clicked:
    # 基础校验
    errors = []
    if not fastq_r1_path: errors.append("请填写 FASTQ R1 路径")
    if not amplicon_seq: errors.append("请填写扩增子序列")
    if not guide_seq: errors.append("请填写 gRNA 序列")
    if n_padding > 0 and not fastq_r2_path: errors.append("拼接模式必须提供 R2")
    if not ANALYSIS_SCRIPT.exists(): errors.append(f"找不到后台脚本: {ANALYSIS_SCRIPT}")

    if errors:
        for err in errors:
            st.error(f"❌ {err}")
    else:
        # 校验通过，弹出对话框
        name_submission_dialog()

st.caption("Tasks are running in background via nohup.")