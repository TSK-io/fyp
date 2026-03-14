from llama_cpp import Llama
import sys

model_path = "/home/rpi/fyp/edge-server/models/Qwen3.5-0.8B-Q4_K_M.gguf"
print(f"尝试加载模型: {model_path}")

try:
    # 开启 verbose=True 会让底层 C++ 引擎打印出所有详细日志
    llm = Llama(model_path=model_path, n_ctx=512, verbose=True)
    print("\n✅ 模型加载成功！C++ 引擎没问题！")
    
    # 顺便测试一下推理
    print("正在测试推理...")
    output = llm("你好，测试一下", max_tokens=10, echo=False)
    print("生成结果:", output['choices'][0]['text'])
    
except Exception as e:
    print(f"\n❌ Python 层面捕获到的错误: {e}")
    sys.exit(1)
