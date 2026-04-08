from __future__ import annotations

from datetime import datetime


class AgronomyService:
    # 这里定义“理想区间”和“可接受区间”，后续评分、告警和建议都围绕它展开。
    SENSOR_RULES = {
        "temperature": {
            "label": "温度",
            "unit": "℃",
            "ideal": (16.0, 22.0),
            "acceptable": (10.0, 28.0),
        },
        "humidity": {
            "label": "空气湿度",
            "unit": "%",
            "ideal": (45.0, 65.0),
            "acceptable": (30.0, 80.0),
        },
        "lux": {
            "label": "光照",
            "unit": "lux",
            "ideal": (1500.0, 8000.0),
            "acceptable": (300.0, 16000.0),
        },
        "soil": {
            "label": "土壤湿度",
            "unit": "%",
            "ideal": (35.0, 55.0),
            "acceptable": (20.0, 75.0),
        },
    }

    def build_diagnosis(self, current_data: dict, history_rows: list[dict] | None = None,
                        policy: dict | None = None, irrigation_state: dict | None = None) -> dict:
        # 诊断输出是首页智能面板和 LLM 提示词的共同上游，所以尽量保持结构稳定。
        history = self._prepare_history(history_rows or [], current_data or {})
        metrics = [self._score_sensor(key, (current_data or {}).get(key)) for key in self.SENSOR_RULES]
        valid_scores = [item["score"] for item in metrics if item["score"] is not None]
        overall_score = int(round(sum(valid_scores) / len(valid_scores))) if valid_scores else 0
        freshness = self._build_freshness((current_data or {}).get("timestamp"))
        soil_trend = self._compute_trend(history, "soil")
        irrigation = self.plan_irrigation(
            current_data=current_data or {},
            history_rows=history_rows or [],
            policy=policy or {},
            irrigation_state=irrigation_state or {},
        )
        alerts = self._build_alerts(
            current_data=current_data or {},
            metrics=metrics,
            freshness=freshness,
            soil_trend=soil_trend,
            irrigation=irrigation,
        )
        recommendations = self._build_recommendations(
            current_data=current_data or {},
            alerts=alerts,
            irrigation=irrigation,
            metrics=metrics,
        )
        level = self._resolve_risk_level(overall_score, alerts)

        return {
            "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "overall_score": overall_score,
            "risk_level": level["key"],
            "risk_label": level["label"],
            "summary": self._build_summary(
                overall_score=overall_score,
                risk_label=level["label"],
                alerts=alerts,
                recommendations=recommendations,
                irrigation=irrigation,
            ),
            "metrics": metrics,
            "trends": [self._compute_trend(history, key) for key in self.SENSOR_RULES],
            "alerts": alerts,
            "recommendations": recommendations,
            "data_freshness": freshness,
            "irrigation_decision": irrigation,
        }

    def plan_irrigation(self, current_data: dict, history_rows: list[dict] | None = None,
                        policy: dict | None = None, irrigation_state: dict | None = None) -> dict:
        policy = policy or {}
        irrigation_state = irrigation_state or {}
        base_threshold = self._as_float(policy.get("soil_threshold_min"))
        base_duration = self._as_int(policy.get("watering_seconds"))
        enabled = bool(policy.get("enabled"))
        current_soil = self._as_float((current_data or {}).get("soil"))
        current_temp = self._as_float((current_data or {}).get("temperature"))
        current_humidity = self._as_float((current_data or {}).get("humidity"))
        current_lux = self._as_float((current_data or {}).get("lux"))
        freshness = self._build_freshness((current_data or {}).get("timestamp"))
        history = self._prepare_history(history_rows or [], current_data or {})
        soil_trend = self._compute_trend(history, "soil")

        factors: list[dict] = []
        effective_threshold = base_threshold if base_threshold is not None else 30.0

        def apply_factor(reason: str, delta: float):
            nonlocal effective_threshold
            effective_threshold += delta
            factors.append({"reason": reason, "delta": round(delta, 1)})

        # 动态阈值不是固定常量，而是根据蒸腾压力、光照和近期土壤走势做补偿。
        if current_temp is not None and current_temp >= 28:
            apply_factor("高温导致蒸腾增强", 4.0)
        elif current_temp is not None and current_temp >= 24:
            apply_factor("温度偏高，适当提前补水", 2.0)
        elif current_temp is not None and current_temp <= 12:
            apply_factor("温度偏低，降低浇水激进度", -2.0)

        if current_lux is not None and current_lux >= 9000:
            apply_factor("光照较强，土壤蒸发会更快", 2.0)
        elif current_lux is not None and current_lux <= 500:
            apply_factor("光照偏弱，蒸发压力较低", -1.0)

        if current_humidity is not None and current_humidity >= 75:
            apply_factor("空气湿度较高，适当放宽阈值", -1.0)

        if soil_trend["direction"] == "falling" and soil_trend["delta"] <= -6:
            apply_factor("土壤湿度下降明显，提前进入补水准备", 3.0)
        elif soil_trend["direction"] == "falling" and soil_trend["delta"] <= -3:
            apply_factor("土壤持续走低，略微抬高触发线", 1.5)

        effective_threshold = round(min(max(effective_threshold, 15.0), 75.0), 1)
        gap = round((effective_threshold - current_soil), 1) if current_soil is not None else None
        recommended_duration = base_duration if base_duration is not None else 0
        if gap is not None and base_duration:
            # 土壤偏离越大，建议浇水时长越长，但仍受基准时长约束，避免过度补水。
            if gap >= 12:
                recommended_duration = min(base_duration + 6, int(base_duration * 1.75))
            elif gap >= 6:
                recommended_duration = min(base_duration + 3, int(base_duration * 1.5))
            recommended_duration = max(recommended_duration, base_duration)

        decision_hint = "等待有效传感器数据"
        should_water = False
        allowed = enabled

        if not enabled:
            decision_hint = "自动灌溉策略已关闭"
        elif base_threshold is None or base_duration is None or base_duration <= 0:
            allowed = False
            decision_hint = "策略参数不完整，无法自动决策"
        elif current_soil is None:
            allowed = False
            decision_hint = "缺少土壤湿度数据，暂停自动浇水"
        elif freshness["stale"]:
            allowed = False
            decision_hint = "传感器数据超过 3 分钟未更新，暂停自动浇水"
        elif irrigation_state.get("watering"):
            decision_hint = "当前正在浇水，等待本轮执行完成"
        elif current_soil < effective_threshold:
            should_water = True
            decision_hint = f"当前土壤 {current_soil}% 低于动态阈值 {effective_threshold}%"
        else:
            decision_hint = f"当前土壤 {current_soil}% 高于动态阈值 {effective_threshold}%"

        action = "建议立即浇水" if should_water else "继续监测"
        return {
            "enabled": enabled,
            "allowed": allowed,
            "should_water": should_water,
            "action": action,
            "base_threshold": base_threshold,
            "effective_threshold": effective_threshold,
            "current_soil": current_soil,
            "gap_to_threshold": gap,
            "base_duration": base_duration,
            "recommended_duration": recommended_duration,
            "soil_trend": soil_trend,
            "factors": factors,
            "reason": decision_hint,
        }

    def format_assistant_context(self, diagnosis: dict) -> str:
        # 把结构化诊断压成一段短上下文，适合放进提示词或日志。
        alerts = "；".join(item["title"] for item in diagnosis.get("alerts", [])[:3]) or "无明显异常"
        recommendations = "；".join(diagnosis.get("recommendations", [])[:3]) or "保持当前策略"
        irrigation = diagnosis.get("irrigation_decision", {})
        return (
            f"综合评分 {diagnosis.get('overall_score', 0)}/100，风险等级 {diagnosis.get('risk_label', '未知')}。"
            f"摘要：{diagnosis.get('summary', '暂无摘要')}。"
            f"异常：{alerts}。"
            f"建议：{recommendations}。"
            f"灌溉决策：{irrigation.get('reason', '暂无')}，"
            f"动态阈值 {irrigation.get('effective_threshold', '未知')}%，"
            f"建议浇水时长 {irrigation.get('recommended_duration', '未知')} 秒。"
        )

    def generate_rule_based_answer(self, env_data: dict, diagnosis: dict, user_msg: str) -> str:
        summary = diagnosis.get("summary", "当前缺少足够数据，建议继续采集环境信息。")
        recommendations = diagnosis.get("recommendations", [])[:2]
        recommendation_text = "；".join(recommendations) if recommendations else "保持现有策略并继续观察。"
        return f"{summary}。建议：{recommendation_text}"

    def _score_sensor(self, key: str, value) -> dict:
        rule = self.SENSOR_RULES[key]
        low_ideal, high_ideal = rule["ideal"]
        low_ok, high_ok = rule["acceptable"]
        numeric = self._as_float(value)
        if numeric is None:
            return {
                "key": key,
                "label": rule["label"],
                "value": None,
                "display_value": "--",
                "target": f"{low_ideal:g}-{high_ideal:g}{rule['unit']}",
                "score": None,
                "status": "missing",
                "status_label": "缺失",
            }

        if low_ideal <= numeric <= high_ideal:
            score = 100
        elif low_ok <= numeric < low_ideal:
            score = 60 + 40 * (numeric - low_ok) / max(low_ideal - low_ok, 1e-6)
        elif high_ideal < numeric <= high_ok:
            score = 60 + 40 * (high_ok - numeric) / max(high_ok - high_ideal, 1e-6)
        else:
            distance = (low_ok - numeric) if numeric < low_ok else (numeric - high_ok)
            score = max(0.0, 45.0 - distance * 4.0)

        score = int(round(score))
        if score >= 90:
            status = ("ideal", "理想")
        elif score >= 65:
            status = ("watch", "可接受")
        else:
            status = ("risk", "偏离")

        return {
            "key": key,
            "label": rule["label"],
            "value": round(numeric, 1),
            "display_value": f"{numeric:.1f}{rule['unit']}",
            "target": f"{low_ideal:g}-{high_ideal:g}{rule['unit']}",
            "score": score,
            "status": status[0],
            "status_label": status[1],
        }

    def _build_freshness(self, timestamp_value) -> dict:
        parsed = self._parse_timestamp(timestamp_value)
        if not parsed:
            return {
                "timestamp": timestamp_value,
                "age_seconds": None,
                "stale": True,
                "label": "无有效时间戳",
            }
        age_seconds = max(0, int((datetime.utcnow() - parsed).total_seconds()))
        return {
            "timestamp": timestamp_value,
            "age_seconds": age_seconds,
            "stale": age_seconds > 180,
            "label": f"{age_seconds} 秒前更新",
        }

    def _build_alerts(self, current_data: dict, metrics: list[dict], freshness: dict,
                      soil_trend: dict, irrigation: dict) -> list[dict]:
        alerts: list[dict] = []
        metric_map = {item["key"]: item for item in metrics}

        # 告警优先反映“控制风险”和“数据可信度”，而不只是单个传感器是否越界。
        if freshness["stale"]:
            alerts.append({
                "severity": "high",
                "title": "传感器数据过期",
                "detail": "最近一条环境数据距离现在超过 3 分钟，自动控制已进入保守模式。",
            })

        soil = self._as_float(current_data.get("soil"))
        if soil is not None and irrigation.get("effective_threshold") is not None and soil < irrigation["effective_threshold"]:
            alerts.append({
                "severity": "high" if soil < 25 else "medium",
                "title": "土壤湿度低于动态阈值",
                "detail": f"当前土壤 {soil}% ，动态阈值 {irrigation['effective_threshold']}%。",
            })

        if soil_trend["direction"] == "falling" and soil_trend["delta"] <= -6:
            alerts.append({
                "severity": "medium",
                "title": "土壤正在快速变干",
                "detail": soil_trend["text"],
            })

        for key in ("temperature", "humidity", "lux"):
            item = metric_map.get(key)
            if item and item["status"] == "risk":
                alerts.append({
                    "severity": "medium",
                    "title": f"{item['label']}偏离适宜区间",
                    "detail": f"当前 {item['display_value']}，目标区间 {item['target']}。",
                })

        return alerts[:6]

    def _build_recommendations(self, current_data: dict, alerts: list[dict], irrigation: dict,
                               metrics: list[dict]) -> list[str]:
        recommendations: list[str] = []
        metric_map = {item["key"]: item for item in metrics}

        if irrigation.get("should_water"):
            recommendations.append(
                f"建议立即执行一次 {irrigation.get('recommended_duration', 0)} 秒的补水，随后观察土壤回升情况。"
            )
        elif irrigation.get("enabled"):
            recommendations.append("当前无需立刻浇水，维持自动灌溉监测即可。")

        lux = self._as_float(current_data.get("lux"))
        if lux is not None and lux < 700:
            recommendations.append("光照偏弱，可开启补光灯 15-30 分钟后复测。")

        temp = self._as_float(current_data.get("temperature"))
        if temp is not None and temp > 26:
            recommendations.append("温度偏高，建议加强通风并降低箱体积热。")
        elif temp is not None and temp < 12:
            recommendations.append("温度偏低，建议适当保温，避免低温抑制生长。")

        humidity = self._as_float(current_data.get("humidity"))
        if humidity is not None and humidity > 75:
            recommendations.append("空气湿度偏高，建议短时通风，降低霉变风险。")

        if not recommendations:
            recommendations.append("整体环境较稳定，建议维持当前参数并持续采样。")

        return recommendations[:5]

    def _resolve_risk_level(self, overall_score: int, alerts: list[dict]) -> dict:
        # 风险等级同时考虑分数和告警权重，避免“均值高但存在致命问题”被低估。
        severity_weight = {"high": 3, "medium": 2, "low": 1}
        risk_points = sum(severity_weight.get(item.get("severity"), 1) for item in alerts)
        if overall_score < 45 or risk_points >= 5:
            return {"key": "high", "label": "高风险"}
        if overall_score < 70 or risk_points >= 2:
            return {"key": "medium", "label": "需关注"}
        return {"key": "low", "label": "稳定"}

    def _build_summary(self, overall_score: int, risk_label: str, alerts: list[dict],
                       recommendations: list[str], irrigation: dict) -> str:
        if alerts:
            lead = alerts[0]["title"]
        else:
            lead = "环境处于可接受范围"
        action = irrigation.get("action", "继续监测")
        follow = recommendations[0] if recommendations else "继续采集更多数据"
        return f"当前综合评分 {overall_score} 分，状态 {risk_label}。{lead}，系统判定 {action}。{follow}"

    def _compute_trend(self, history_rows: list[dict], key: str) -> dict:
        rule = self.SENSOR_RULES[key]
        values = []
        for row in history_rows:
            numeric = self._as_float(row.get(key))
            parsed_ts = self._parse_timestamp(row.get("timestamp"))
            if numeric is None or parsed_ts is None:
                continue
            values.append((parsed_ts, numeric))

        if len(values) < 2:
            return {
                "key": key,
                "label": rule["label"],
                "direction": "unknown",
                "delta": 0.0,
                "rate_per_hour": 0.0,
                "text": "历史数据不足",
            }

        start_ts, start_value = values[0]
        end_ts, end_value = values[-1]
        delta = round(end_value - start_value, 1)
        elapsed_hours = max((end_ts - start_ts).total_seconds() / 3600.0, 1e-6)
        rate_per_hour = round(delta / elapsed_hours, 2)

        stable_threshold = {
            "temperature": 0.8,
            "humidity": 4.0,
            "lux": 500.0,
            "soil": 2.0,
        }[key]
        # 不同指标的“平稳”阈值不同，避免光照和温度共用同一个灵敏度。
        if abs(delta) < stable_threshold:
            direction = "stable"
            text = f"{rule['label']}整体平稳"
        elif delta > 0:
            direction = "rising"
            text = f"{rule['label']}上升 {abs(delta):.1f}{rule['unit']}"
        else:
            direction = "falling"
            text = f"{rule['label']}下降 {abs(delta):.1f}{rule['unit']}"

        return {
            "key": key,
            "label": rule["label"],
            "direction": direction,
            "delta": delta,
            "rate_per_hour": rate_per_hour,
            "text": text,
        }

    def _prepare_history(self, history_rows: list[dict], current_data: dict) -> list[dict]:
        # 把数据库历史和当前内存快照拼成统一序列，减少“最新一帧未落库”带来的诊断延迟。
        prepared = []
        for row in history_rows:
            timestamp = row.get("timestamp")
            if not self._parse_timestamp(timestamp):
                continue
            prepared.append({
                "timestamp": timestamp,
                "temperature": row.get("temperature"),
                "humidity": row.get("humidity"),
                "lux": row.get("lux"),
                "soil": row.get("soil"),
            })

        current_ts = current_data.get("timestamp")
        if self._parse_timestamp(current_ts):
            prepared.append({
                "timestamp": current_ts,
                "temperature": current_data.get("temperature"),
                "humidity": current_data.get("humidity"),
                "lux": current_data.get("lux"),
                "soil": current_data.get("soil"),
            })

        prepared.sort(key=lambda item: item["timestamp"])
        return prepared[-36:]

    def _parse_timestamp(self, value):
        if not value:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
            try:
                return datetime.strptime(value, fmt)
            except Exception:
                continue
        return None

    def _as_float(self, value):
        try:
            if value is None or value == "":
                return None
            return float(value)
        except Exception:
            return None

    def _as_int(self, value):
        try:
            if value is None or value == "":
                return None
            return int(value)
        except Exception:
            return None
