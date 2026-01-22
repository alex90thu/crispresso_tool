**中文** | [English](./readme.md)

# CRISPResso 异步平台（中文说明）

基于 Streamlit 的前端与后台脚本组合，支持异步提交 CRISPResso2 任务，并通过静态门户页面浏览日志与结果。

## 仓库内容
- `run.sh`：启动 Streamlit UI、静态文件服务器（结果门户），全部以 `nohup` 后台运行。
- `streamlit_app.py`：前端提交表单，调用 `analyze_crispresso.py` 生成后台任务并刷新门户。
- `analyze_crispresso.py`：CLI 包装器，支持 R1/R2 拼接（N 填充），调用 CRISPResso2，结束后更新门户。
- `portal_gen.py`：扫描输出根目录，生成 `index.html` 状态面板。
- `environment.yml` / `requirements.txt`：依赖定义，默认 conda 环境名 `crispresso-env`。

## 环境准备
1. 安装 conda / mamba，并保证非交互 shell 能找到 `conda`。
2. 创建环境（首次）：
   ```bash
   conda env create -f environment.yml
   ```
   已有环境更新依赖：
   ```bash
   conda env update -f environment.yml --prune
   ```
3. 手工使用时可激活：
   ```bash
   conda activate crispresso-env
   ```

## 启动服务
`run.sh` 会自动激活 `crispresso-env`，启动结果门户的静态 HTTP 服务，并将 Streamlit 置于后台。
```bash
bash run.sh --port 8504 --address 0.0.0.0
```
- Streamlit: http://<server>:8504，日志 `streamlit_app.log`
- Portal:    http://<server>:8505，日志 `portal_server.log`

### 路径需保持一致
如需更换数据根目录，请同时修改以下三处：
- `DATA_DIR`：`run.sh`
- `DEFAULT_OUTPUT_BASE`：`analyze_crispresso.py`
- `ROOT_DIR`：`portal_gen.py`

## 使用 Streamlit UI
1. 打开 Streamlit 地址。
2. 填写必填项：R1 FASTQ、扩增子序列、gRNA 序列、样本名。可选：R2 FASTQ、N 填充拼接、最小读长/质量、CPU 核数、CRISPResso 可执行路径。
3. 提交后生成 `Job_<时间>_<样本>` 目录，写入 `CRISPResso_RUNNING_LOG.txt`，后台 `nohup` 运行 CRISPResso2。
4. 在门户查看进度（60 秒自动刷新）或直接打开日志文件。

## 直接使用 CLI
无需前端即可调用后台脚本，例如：
```bash
python analyze_crispresso.py \
  --fastq_r1 /path/to/R1.fastq.gz \
  --amplicon ACTG... \
  --guide GGG... \
  --output /path/to/output_dir \
  --name Sample01 \
  --executable /path/to/CRISPResso \
  --n_padding 10 \
  --fastq_r2 /path/to/R2.fastq.gz \
  --min_read_length 0 \
  --min_base_quality 0 \
  --n_processes 4
```
说明：
- `--n_padding > 0` 时会对 R1/R2 做拼接（R2 反向互补并以 N 填充），随后按单端模式运行。
- `--output` 为相对路径时，会被解析到 `DEFAULT_OUTPUT_BASE` 下。

## 门户生成器
`portal_gen.py` 会在输出根目录生成 `index.html`，列出任务、状态（运行/完成/可能错误）、日志与报告链接。脚本在任务提交和完成时会被自动调用，也可手动执行：
```bash
python portal_gen.py
```

## 常见问题
- `conda` 未在 PATH：请先初始化 shell，否则 `run.sh` 会退出。
- 端口占用：调整 `--port` 或在 `run.sh` 中修改 `PORTAL_PORT`。
- 输出根目录无写权限：确保目录存在且可写；`run.sh` 会尝试创建。
- 找不到 CRISPResso：在 UI 中填入绝对路径，或在 CLI 中使用 `--executable` 指定。
- 查看日志：前端日志见 `streamlit_app.log`，门户 HTTP 日志见 `portal_server.log`，每个任务的运行日志位于对应 `Job_*` 目录下。
