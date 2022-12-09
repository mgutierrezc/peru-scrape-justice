import json
import os
import time
from pathlib import Path
import io
import requests
from PIL import Image
from dotenv import load_dotenv
import logging

logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s',
                    level=logging.INFO)

load_dotenv()


def azcaptcha_solver_get(captcha_id):
    azcaptcha_url = "http://azcaptcha.com/res.php"
    params = {
        "key": os.getenv("CAPTCHA_APIKEY"),
        "action": "get",
        "id": captcha_id,
        "json": 1
    }
    try:
        res = requests.get(azcaptcha_url, params=params)
        res_answer = json.loads(res.text)
        captcha_itext = res_answer["request"]
        print({"captcha_itext":captcha_itext})
    except requests.exceptions.RequestException as e:
        raise SystemExit(e)
    if captcha_itext == "ERROR_USER_BALANCE_ZERO":
        raise SystemExit(captcha_itext)
    return captcha_itext


def azcaptcha_solver_post(driver):
    try:
        image = driver.find_element_by_id('captcha_image').screenshot_as_png
        screenshot = Image.open(io.BytesIO(image))
        screenshot.save("captcha/image-captch.png")
    except Exception as e:
        exit(2)

    azcaptcha_url = "http://azcaptcha.com/in.php"
    payload = {
        "method": "post",
        "key": os.getenv("CAPTCHA_APIKEY"),
        "json": 1
    }
    try:
        image_captcha_path = Path(__file__).parent / "captcha/image-captch.png"
        image_to_upload = (
            os.path.basename(image_captcha_path), open(image_captcha_path, 'rb'), 'application/octet-stream')
    except FileNotFoundError as e:
        logging.error("file not found")
        return None

    files = {
        "file": image_to_upload
    }

    try:
        res = requests.post(azcaptcha_url, data=payload, files=files)
        res_answer = json.loads(res.text)
        captcha_id = res_answer["request"]
        if captcha_id:
            time.sleep(5)
            return azcaptcha_solver_get(captcha_id)
        return None
    except requests.exceptions.RequestException as e:
        logging.error(e)
        raise SystemExit(e)

