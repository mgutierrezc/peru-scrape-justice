import json
import os
import random
import string
import time
import io
import requests
from PIL import Image
from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from utils import logger


load_dotenv()

tries = 0


def azcaptcha_solver_get(captcha_id):

    azcaptcha_url = "http://azcaptcha.com/res.php"
    params = {
        "key": os.getenv("CAPTCHA_APIKEY"),
        "action": "get",
        "id": captcha_id,
        "json": 1,
    }
    try:
        res = requests.get(azcaptcha_url, params=params)
        res_answer = json.loads(res.text)
        captcha_itext = res_answer["request"]
        logger.info({"captcha_text": captcha_itext})
        logger.info({"captcha_id": captcha_id})
    except requests.exceptions.RequestException as e:
        raise SystemExit(e)
    if captcha_itext == "ERROR_USER_BALANCE_ZERO":
        raise SystemExit(captcha_itext)

    if (
        captcha_itext == "CAPCHA_NOT_READY"
        or captcha_itext == "ERROR_CAPTCHA_UNSOLVABLE"
    ):
        global tries
        tries += 1
        logger.info(
            f"captcha_id: {captcha_id} Retrying to get captcha  in 5 seconds..."
        )
        time.sleep(5)
        if tries < 6:
            return azcaptcha_solver_get(captcha_id)
    return captcha_itext


def azcaptcha_solver_post(driver):
    letters = string.ascii_lowercase
    random_string = "".join(random.choice(letters) for i in range(10))
    captcha_name = f"image-captcha-{random_string}.png"
    image_captcha_path = os.path.join(
        os.path.realpath(os.path.dirname(__file__)), "captcha", captcha_name
    )
    # image_captcha_path = fr"{os.path.realpath(os.path.dirname(__file__))}\{os.path.join('captcha', captcha_name)}"
    try:
        image = driver.find_element(By.ID, "captcha_image").screenshot_as_png
        screenshot = Image.open(io.BytesIO(image))
        screenshot.save(image_captcha_path)
        logger.info("captcha image saved")
    except Exception as e:
        logger.error(f"azcaptcha_solver_post error; {e}")
        exit(2)

    azcaptcha_url = "http://azcaptcha.com/in.php"
    payload = {"method": "post", "key": os.getenv("CAPTCHA_APIKEY"), "json": 1}
    try:
        captcha_image = open(image_captcha_path, "rb")
        image_to_upload = (
            os.path.basename(image_captcha_path),
            captcha_image,
            "application/octet-stream",
        )
    except FileNotFoundError as e:
        logger.error("file not found")
        return None

    files = {"file": image_to_upload}

    try:
        res = requests.post(azcaptcha_url, data=payload, files=files)
        if os.path.isfile(image_captcha_path):
            captcha_image.close()
            os.remove(image_captcha_path)

        res_answer = json.loads(res.text)
        captcha_id = res_answer["request"]
        if captcha_id:
            if (
                captcha_id
                == "ERROR_TODAY_NO_SLOT_AVAILABLE_UPGRAGE_PACKAGE_OR_CHANGE_TO_USE_BALANCE"
            ):
                logger.error(f"captcha error: {captcha_id}")
                os._exit(1)
            time.sleep(5)
            return azcaptcha_solver_get(captcha_id)
        return None
    except requests.exceptions.RequestException as e:
        logger.error(e)
        raise SystemExit(e)
