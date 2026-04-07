import os
from datetime import datetime

import cv2
import numpy as np


class VisionService:
    def __init__(self, analysis_dir: str):
        self.analysis_dir = analysis_dir

    def analyze_flower_color(self, image_path: str):
        image = cv2.imread(image_path)
        hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        color_ranges = {
            "red": ([0, 120, 70], [10, 255, 255]),
            "green": ([35, 80, 40], [85, 255, 255]),
            "pink": ([140, 100, 100], [170, 255, 255]),
        }

        scores = {}
        for color, (lower, upper) in color_ranges.items():
            mask = cv2.inRange(hsv_image, np.array(lower), np.array(upper))
            scores[color] = cv2.countNonZero(mask)

        detected_color = "none" if not any(scores.values()) else max(scores, key=scores.get)
        growth_stage_map = {
            "green": "花蕾期 (Budding Stage)",
            "pink": "盛开期 (Flowering Stage)",
            "red": "成熟/凋谢期 (Mature/Withered Stage)",
            "none": "未识别到有效目标",
        }
        tech_stage_map = {
            "green": "SYS_CLASS: BUDDING_PHASE",
            "pink": "SYS_CLASS: BLOOMING_PHASE",
            "red": "SYS_CLASS: MATURE_DECAY",
            "none": "SYS_CLASS: TGT_NOT_FOUND",
        }
        growth_stage = growth_stage_map.get(detected_color, "未知")
        tech_stage = tech_stage_map.get(detected_color, "SYS_CLASS: UNKNOWN")
        height, width, _ = image.shape

        if detected_color != "none":
            lower, upper = color_ranges[detected_color]
            mask = cv2.inRange(hsv_image, np.array(lower), np.array(upper))
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                largest_contour = max(contours, key=cv2.contourArea)
                if cv2.contourArea(largest_contour) > 500:
                    x, y, w, h = cv2.boundingRect(largest_contour)
                    line_len = 50
                    thick = 6
                    color_t = (0, 255, 0)
                    cv2.line(image, (x, y), (x + line_len, y), color_t, thick)
                    cv2.line(image, (x, y), (x, y + line_len), color_t, thick)
                    cv2.line(image, (x + w, y), (x + w - line_len, y), color_t, thick)
                    cv2.line(image, (x + w, y), (x + w, y + line_len), color_t, thick)
                    cv2.line(image, (x, y + h), (x + line_len, y + h), color_t, thick)
                    cv2.line(image, (x, y + h), (x, y + h - line_len), color_t, thick)
                    cv2.line(image, (x + w, y + h), (x + w - line_len, y + h), color_t, thick)
                    cv2.line(image, (x + w, y + h), (x + w, y + h - line_len), color_t, thick)
                    cv2.rectangle(image, (x, y), (x + w, y + h), (0, 150, 0), 3)
                    text_y = y - 25 if y - 25 > 40 else y + 50
                    cv2.putText(image, f"TARGET: {detected_color.upper()}", (x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 2.5, (0, 255, 255), 5)

        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        cv2.putText(image, "SAFFRON_EDGE_VISION // OVERRIDE: ALPHA", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0, 255, 0), 4)
        cv2.putText(image, f"TS_STREAM: {timestamp_str}", (30, 160), cv2.FONT_HERSHEY_SIMPLEX, 1.8, (0, 200, 0), 4)
        cv2.putText(image, f"DOMINANT_SPEC: {detected_color.upper()}", (30, 240), cv2.FONT_HERSHEY_SIMPLEX, 2.5, (0, 255, 255), 5)
        cv2.putText(image, tech_stage, (30, 320), cv2.FONT_HERSHEY_SIMPLEX, 3.0, (0, 255, 0), 7)
        cv2.putText(image, "MEM_ALLOC: 48.2MB", (width - 650, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.8, (0, 200, 0), 4)
        cv2.putText(image, "MODEL: CV_HEURISTIC_V2", (width - 850, 160), cv2.FONT_HERSHEY_SIMPLEX, 1.8, (0, 200, 0), 4)

        analysis_filename = "analyzed_" + os.path.basename(image_path)
        analysis_filepath = os.path.join(self.analysis_dir, analysis_filename)
        cv2.imwrite(analysis_filepath, image)
        return {
            "status": "success",
            "detected_color": detected_color,
            "growth_stage": growth_stage,
            "scores": scores,
            "analysis_filename": analysis_filename,
        }
