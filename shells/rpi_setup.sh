sudo apt -y install python3-pip python3-numpy python3-opencv python3-picamera2 hx build-essential cmake ripgrep
pip install mpremote --break-system-packages

wget https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf -O $HOME/fyp/edge-server/models/qwen2.5-0.5b-instruct-q4_k_m.gguf

CMAKE_ARGS="-DGGML_CPU_ARM_ARCH=armv8-a" pip install llama-cpp-python

