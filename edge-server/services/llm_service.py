import os


try:
    from llama_cpp import Llama

    LLM_AVAILABLE = True
    print("llama_cpp 库加载成功。")
except Exception as exc:
    LLM_AVAILABLE = False
    Llama = None
    print(f"警告: llama_cpp 初始化失败: {exc}。本地 LLM 功能将不可用。")


class LocalLLMService:
    def __init__(self, model_path: str):
        self.model_path = model_path
        self._model = None

    @property
    def available(self) -> bool:
        return LLM_AVAILABLE and os.path.exists(self.model_path)

    def get_model(self):
        if self._model is None and self.available:
            print("正在加载 Qwen 模型到内存，请稍候...")
            self._model = Llama(
                model_path=self.model_path,
                n_ctx=512,
                n_threads=4,
                verbose=False,
            )
            print("Qwen 模型加载完成！")
        return self._model

    def answer(self, env_data: dict, user_msg: str) -> str:
        model = self.get_model()
        if not model:
            raise RuntimeError("模型加载失败。")

        prompt = (
            f"<|im_start|>system\n"
            f"你是一个专业的藏红花种植AI助手。请根据以下当前环境数据回答问题，要求语言简明扼要，控制在100字以内。\n"
            f"当前温度:{env_data.get('temperature', '未知')}℃, "
            f"湿度:{env_data.get('humidity', '未知')}%, "
            f"光照:{env_data.get('lux', '未知')}lux, "
            f"土壤湿度:{env_data.get('soil', '未知')}%。<|im_end|>\n"
            f"<|im_start|>user\n{user_msg}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )
        response = model(prompt, max_tokens=150, stop=["<|im_end|>"], echo=False)
        return response["choices"][0]["text"].strip()
