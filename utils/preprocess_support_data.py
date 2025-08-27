import os
import shutil
import time
import json
import olefile
import cv2
import pytesseract
import numpy as np
from PIL import Image

def extract_text_from_hwp(file_path):
    try:
        temp_path = os.path.join(os.getcwd(), "temp.hwp")
        shutil.copy(file_path, temp_path)

        with olefile.OleFileIO(temp_path) as f:
            encoded_text = f.openstream('PrvText').read()
            decoded_text = encoded_text.decode('utf-16')

        os.remove(temp_path)
        return decoded_text

    except Exception as e:
        return None

def convert_all_hwp_to_json(base_dir):
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.lower().endswith(".hwp"):
                full_path = os.path.join(root, file)
                text = extract_text_from_hwp(full_path)
                if text:
                    json_name = os.path.splitext(file)[0] + ".json"
                    json_path = os.path.join(root, json_name)

                    with open(json_path, "w", encoding="utf-8") as f:
                        json.dump({"file_name": file, "text": text}, f, ensure_ascii=False, indent=2)


def extract_text_from_image(image_path: str) -> str:
    try:
        pil_img = Image.open(image_path).convert("RGB")
        img = np.array(pil_img)

        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)

        thresh = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w < 15 and h < 15:
                cv2.rectangle(thresh, (x, y), (x + w, y + h), 255, -1)

        scale_percent = 150
        width = int(thresh.shape[1] * scale_percent / 100)
        height = int(thresh.shape[0] * scale_percent / 100)
        resized = cv2.resize(thresh, (width, height), interpolation=cv2.INTER_CUBIC)

        custom_config = r'--oem 3 --psm 4'
        text = pytesseract.image_to_string(resized, lang='kor', config=custom_config)

        return text.strip()

    except Exception as e:
        return None

def convert_all_images_to_json(base_dir: str):
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.lower().endswith((".png", ".jpg", ".jpeg")):
                full_path = os.path.join(root, file)

                text = extract_text_from_image(full_path)
                if text:
                    json_name = os.path.splitext(file)[0] + ".json"
                    json_path = os.path.join(root, json_name)

                    with open(json_path, "w", encoding="utf-8") as f:
                        json.dump({"file_name": file, "text": text}, f, ensure_ascii=False, indent=2)

                else:
                    print(f"텍스트 없음: {file}")
                time.sleep(0.1)

def preprocess_support_run_all():
    base_dir = os.path.join(os.getcwd(), "utils/data/download(support)")
    convert_all_hwp_to_json(base_dir)

    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    convert_all_images_to_json(base_dir)
