import os
from datetime import datetime

import cv2
import numpy as np


class VisionService:
    COLOR_RANGES = {
        "red": [
            ([0, 120, 70], [10, 255, 255]),
            ([170, 120, 70], [180, 255, 255]),
        ],
        "green": [
            ([35, 80, 40], [85, 255, 255]),
        ],
        "pink": [
            ([140, 100, 100], [170, 255, 255]),
        ],
    }

    def __init__(self, analysis_dir: str):
        self.analysis_dir = analysis_dir

    @staticmethod
    def _ensure_odd(value: int) -> int:
        value = max(3, int(value))
        return value if value % 2 else value + 1

    @staticmethod
    def _build_color_mask(hsv_image, hsv_ranges):
        mask = np.zeros(hsv_image.shape[:2], dtype=np.uint8)
        for lower, upper in hsv_ranges:
            lower_arr = np.array(lower, dtype=np.uint8)
            upper_arr = np.array(upper, dtype=np.uint8)
            mask = cv2.bitwise_or(mask, cv2.inRange(hsv_image, lower_arr, upper_arr))
        return mask

    def _refine_mask(self, mask):
        short_side = min(mask.shape[:2])
        open_size = self._ensure_odd(min(5, max(3, short_side // 180)))
        close_size = self._ensure_odd(min(17, max(7, short_side // 45)))
        bridge_size = self._ensure_odd(min(31, max(11, short_side // 28)))

        open_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (open_size, open_size))
        close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close_size, close_size))
        bridge_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (bridge_size, bridge_size))

        cleaned = cv2.morphologyEx(mask, cv2.MORPH_OPEN, open_kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, close_kernel)
        return cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, bridge_kernel)

    @staticmethod
    def _boxes_intersect(box_a, box_b, padding=0):
        ax, ay, aw, ah = box_a
        bx, by, bw, bh = box_b
        return (
            ax - padding <= bx + bw and
            ax + aw + padding >= bx and
            ay - padding <= by + bh and
            ay + ah + padding >= by
        )

    @staticmethod
    def _pad_box(box, width, height, padding):
        x, y, w, h = box
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(width, x + w + padding)
        y2 = min(height, y + h + padding)
        return x1, y1, x2 - x1, y2 - y1

    def _find_target_box(self, mask):
        height, width = mask.shape
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        image_area = height * width
        min_contour_area = max(500, int(image_area * 0.0005))
        candidate_contours = [
            contour for contour in contours
            if cv2.contourArea(contour) >= min_contour_area
        ]
        if not candidate_contours:
            return None

        candidate_contours.sort(key=cv2.contourArea, reverse=True)
        merged_contours = [candidate_contours[0]]
        current_box = cv2.boundingRect(np.vstack(merged_contours))
        merge_padding = max(25, int(min(height, width) * 0.04))
        pending_contours = candidate_contours[1:]

        while pending_contours:
            merged_in_pass = False
            next_pending = []
            for contour in pending_contours:
                contour_box = cv2.boundingRect(contour)
                if self._boxes_intersect(current_box, contour_box, padding=merge_padding):
                    merged_contours.append(contour)
                    current_box = cv2.boundingRect(np.vstack(merged_contours))
                    merged_in_pass = True
                else:
                    next_pending.append(contour)
            if not merged_in_pass:
                break
            pending_contours = next_pending

        return current_box

    def analyze_flower_color(self, image_path: str):
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"无法读取图像: {image_path}")
        hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        masks = {}
        scores = {}
        for color, hsv_ranges in self.COLOR_RANGES.items():
            raw_mask = self._build_color_mask(hsv_image, hsv_ranges)
            refined_mask = self._refine_mask(raw_mask)
            masks[color] = refined_mask
            scores[color] = cv2.countNonZero(refined_mask)

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
            target_box = self._find_target_box(masks[detected_color])
            if target_box:
                box_padding = max(12, int(min(height, width) * 0.015))
                x, y, w, h = self._pad_box(target_box, width, height, box_padding)
                line_len = max(35, min(90, min(w, h) // 4))
                thick = max(4, min(8, min(height, width) // 220))
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
