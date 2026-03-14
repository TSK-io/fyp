sudo apt -y install python3-pip python3-numpy python3-opencv python3-picamera2 hx
pip install mpremote --break-system-packages
# 安装工具
pip install huggingface_hub --break-system-packages

# 下载指定文件
hf download unsloth/Qwen3.5-0.8B-GGUF \
  Qwen3.5-0.8B-Q4_K_M.gguf \
  --local-dir ./qwen3.5-0.8b

