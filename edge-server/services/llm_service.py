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
            # 模型按需懒加载，避免应用启动时就占满树莓派内存。
            print("正在加载 Qwen 模型到内存，请稍候...")
            self._model = Llama(
                model_path=self.model_path,
                n_ctx=512,
                n_threads=4,
                verbose=False,
            )
            print("Qwen 模型加载完成！")
        return self._model

    def respond(self, env_data: dict, user_msg: str, diagnosis: dict | None = None) -> dict:
        # 优先尝试本地模型；任何异常都自动回退到规则回答，保证接口始终可用。
        if self.available:
            try:
                model = self.get_model()
                if model:
                    prompt = self._build_prompt(env_data, user_msg, diagnosis or {})
                    response = model(prompt, max_tokens=180, stop=["<|im_end|>"], echo=False)
                    return {
                        "mode": "llm",
                        "answer": response["choices"][0]["text"].strip(),
                    }
            except Exception as exc:
                print(f"LLM 推理失败，自动降级到规则引擎: {exc}")

        return {
            "mode": "heuristic",
            "answer": self._build_rule_based_answer(env_data, diagnosis or {}),
        }

    def answer(self, env_data: dict, user_msg: str, diagnosis: dict | None = None) -> str:
        return self.respond(env_data, user_msg, diagnosis=diagnosis)["answer"]

    def _build_prompt(self, env_data: dict, user_msg: str, diagnosis: dict) -> str:
        # 提示词同时注入原始环境数据和规则诊断，尽量让模型“基于事实回答”。
        alerts = "；".join(item["title"] for item in diagnosis.get("alerts", [])[:3]) or "无明显异常"
        recommendations = "；".join(diagnosis.get("recommendations", [])[:3]) or "保持当前策略"
        irrigation = diagnosis.get("irrigation_decision", {})
        return (
            f"<|im_start|>system\n"
            f"你是一个专业的藏红花种植AI助手。"
            f"请根据实时环境与规则引擎诊断回答问题，给出明确判断与动作建议，"
            f"语言简明扼要，控制在120字以内。\n"
            f"当前温度:{env_data.get('temperature', '未知')}℃, "
            f"湿度:{env_data.get('humidity', '未知')}%, "
            f"光照:{env_data.get('lux', '未知')}lux, "
            f"土壤湿度:{env_data.get('soil', '未知')}%。\n"
            f"规则引擎评分:{diagnosis.get('overall_score', '未知')}分, "
            f"风险等级:{diagnosis.get('risk_label', '未知')}。\n"
            f"规则引擎摘要:{diagnosis.get('summary', '暂无')}。\n"
            f"异常告警:{alerts}。\n"
            f"建议动作:{recommendations}。\n"
            f"动态浇水阈值:{irrigation.get('effective_threshold', '未知')}%, "
            f"推荐浇水时长:{irrigation.get('recommended_duration', '未知')}秒, "
            f"当前决策:{irrigation.get('reason', '暂无')}。<|im_end|>\n"
            f"<|im_start|>user\n{user_msg}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )

    def _build_rule_based_answer(self, env_data: dict, diagnosis: dict) -> str:
        # 降级回答尽量复用诊断摘要，避免在模型不可用时体验断崖式下降。
        summary = diagnosis.get("summary")
        recommendations = diagnosis.get("recommendations", [])
        if not summary:
            summary = (
                f"当前温度 {env_data.get('temperature', '未知')}℃，"
                f"湿度 {env_data.get('humidity', '未知')}%，"
                f"光照 {env_data.get('lux', '未知')}lux，"
                f"土壤湿度 {env_data.get('soil', '未知')}%。"
            )
        if recommendations:
            return f"{summary} 建议：{'；'.join(recommendations[:2])}"
        return summary
