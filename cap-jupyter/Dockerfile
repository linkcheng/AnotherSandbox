# syntax=docker/dockerfile:1.6
FROM base-python312:latest

LABEL org.opencontainers.image.title="cap-jupyter"
LABEL org.opencontainers.image.description="AI 个人沙箱 cap-jupyter：JupyterLab（P1 token=空，FR-025）"

# 安装 JupyterLab + 常用内核（base-python312 venv 用 uv 管理，不含 pip）
RUN uv pip install --python /opt/venv/bin/python --no-cache \
        "jupyterlab>=4.2" \
        "notebook" \
        "ipykernel" \
        "matplotlib" \
        "pandas" \
        "numpy" && \
    /opt/venv/bin/python -m ipykernel install --user --name python3

EXPOSE 8888

CMD ["/opt/venv/bin/jupyter", "lab", \
     "--ip=0.0.0.0", \
     "--port=8888", \
     "--no-browser", \
     "--ServerApp.token=", \
     "--ServerApp.password=", \
     "--ServerApp.allow_origin=*", \
     "--notebook-dir=/workspace/notebooks"]
