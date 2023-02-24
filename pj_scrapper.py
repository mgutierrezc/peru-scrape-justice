from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import shutil
from random import uniform
import threading
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException
import numpy as np
import scipy.interpolate as si
from dotenv import load_dotenv
from captcha_solver import azcaptcha_recaptchav2_solver_post
from judges_names import judges_names
from utils import (
    download_wait,
    is_element_present,
    kill_os_process,
    setup_browser_driver,
    logger,
)

load_dotenv()


default_temp_download_folder = os.path.join(
    os.path.realpath(os.path.dirname(__file__)), "casillero_digital_temp_downloads"
)

final_data_folder = os.path.join(
    os.path.realpath(os.path.dirname(__file__)), "data", "casillero_digital_web_data"
)


class PjScrapper:
    def __init__(self, judge_name) -> None:

        # Randomization Related
        self.MIN_RAND = 0.64
        self.MAX_RAND = 1.27
        self.LONG_MIN_RAND = 4.78
        self.LONG_MAX_RAND = 11.1
        self.run_attempts = 0
        self.judge_name = judge_name

    # Using B-spline for simulate humane like mouse movments
    def human_like_mouse_move(self, action, start_element):
        points = [[6, 2], [3, 2], [0, 0], [0, 2]]
        points = np.array(points)
        x = points[:, 0]
        y = points[:, 1]

        t = range(len(points))
        ipl_t = np.linspace(0.0, len(points) - 1, 100)

        x_tup = si.splrep(t, x, k=1)
        y_tup = si.splrep(t, y, k=1)

        x_list = list(x_tup)
        xl = x.tolist()
        x_list[1] = xl + [0.0, 0.0, 0.0, 0.0]

        y_list = list(y_tup)
        yl = y.tolist()
        y_list[1] = yl + [0.0, 0.0, 0.0, 0.0]

        x_i = si.splev(ipl_t, x_list)
        y_i = si.splev(ipl_t, y_list)

        startElement = start_element

        action.move_to_element(startElement)
        action.perform()

        c = 5
        i = 0
        for mouse_x, mouse_y in zip(x_i, y_i):
            action.move_by_offset(mouse_x, mouse_y)
            action.perform()
            i += 1
            if i == c:
                break

    def wait_between(self):
        a = self.MIN_RAND
        b = self.MAX_RAND
        rand = uniform(a, b)
        time.sleep(rand)

    def cleat_temp_folder(self, temp_folder_path):
        # delete all the files in the folder
        for filename in os.listdir(temp_folder_path):
            file_path = os.path.join(temp_folder_path, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
            except Exception as e:
                print(f"Failed to delete {file_path}. Reason: {e}")

        # delete all the subfolders in the folder
        for subfolder_name in os.listdir(temp_folder_path):
            subfolder_path = os.path.join(temp_folder_path, subfolder_name)
            try:
                if os.path.isdir(subfolder_path):
                    shutil.rmtree(subfolder_path)
            except Exception as e:
                print(f"Failed to delete {subfolder_path}. Reason: {e}")

    def is_loading_element_visible(self, driver):
        try:
            element = driver.find_element(
                By.ID,
                "cargando",
            )
            return element.is_displayed()
        except NoSuchElementException:
            logger.error("Loader element not found.")
            return False

    def is_captcha_image_pop_up_visible(self, driver):
        try:
            element = driver.find_element(
                By.XPATH,
                "//body/div[2]",
            )
            visibility = element.value_of_css_property("visibility")
            return visibility == "visible"
        except NoSuchElementException:
            logger.error("element not found.")
            return True  # so as to retry

    def is_next_btn_enabled(self, driver):
        try:
            next_btn = driver.find_element(
                By.XPATH,
                '//div[@class="p-card-content"]/'
                'div[@class="p-grid cord-paginacion p-shadow-2"][1]'
                '/div/div[@class="paginacion item-block"]/div/'
                "p-paginator/div/button[3]",
            )
            return next_btn.is_enabled()
        except NoSuchElementException:
            logger.error("pagination next button not found.")
            return False

    def navigate_next_page(self, driver, btn_index=2):
        try:
            page_btn = driver.find_element(
                By.XPATH,
                f'//div[@class="p-card-content"]/ \
                div[@class="p-grid cord-paginacion p-shadow-2"][1] \
                /div/div[@class="paginacion item-block"]/div/ \
                p-paginator/div/span/button[{btn_index}]',
            )
            page_btn.click()
            time.sleep(3)
        except NoSuchElementException:
            logger.error(f"pagination button {btn_index} not found.")
            exit()

    def download_resolutions(self, driver, buttons=[]):
        for button_index in range(len(buttons)):
            while True:
                if not self.is_loading_element_visible(driver):
                    break
            buttons[button_index].click()
            temp_folder = os.path.join(default_temp_download_folder)
            download_wait(temp_folder, 10, driver)

    def scrap_resolution_download_btns(self, driver):
        try:
            pagination_dropdown = driver.find_element(
                By.XPATH,
                '//div[@class="p-card-content"] \
                /div[@class="p-grid cord-paginacion p-shadow-2"][1] \
                /div/div[@class="paginacion item-block"] \
                /div[2]/p-dropdown',
            )
            pagination_dropdown.click()
            time.sleep(1)
            max_pagination_item = driver.find_element(
                By.XPATH,
                '//div[@class="p-card-content"]/div[@class="p-grid'
                ' cord-paginacion p-shadow-2"][1]/div/div[@class="paginacion'
                ' item-block"]/div[@class="item-paginacion"]/p-dropdown/'
                "div/div/div/ul/p-dropdownitem[last()]/li",
            )
            max_pagination_item.click()
        except NoSuchElementException:
            logger.error("pagination not found.")
            exit()

        time.sleep(3)

        # clear temp folder before downloading start
        self.cleat_temp_folder(
            os.path.join(default_temp_download_folder, self.judge_name)
        )

        page_index = 1
        btn_index = 2
        while self.is_next_btn_enabled(driver):
            # while btn_index < 3:
            if btn_index < 5:
                pass
            else:
                btn_index = 4

            resolution_btns = driver.find_elements(
                By.XPATH,
                '//div[@class="p-dataview-content"]' "/div/div/div/div[2]/button",
            )
            print(f"resolution_btns: {len(resolution_btns)}")
            self.download_resolutions(driver, resolution_btns)
            self.navigate_next_page(driver, btn_index)
            btn_index += 1
            logger.info(
                f"current page: {page_index}, \
                current judge: {self.judge_name}"
            )
            page_index += 1

    def solve_captcha_manually(self, action_chains, driver):
        try:
            # Switch to the iframe that contains the reCAPTCHA widget
            frame = driver.find_element(By.XPATH, "//iframe[@title='reCAPTCHA']")
            # self.human_like_mouse_move(action_chains, frame)
            driver.switch_to.frame(frame)

            # Click the reCAPTCHA checkbox
            checkbox = driver.find_element(By.XPATH, "//span[@aria-checked='false']")

            self.human_like_mouse_move(action_chains, checkbox)
            checkbox.click()
            self.wait_between()

            self.human_like_mouse_move(action_chains, checkbox)

            # Switch back to the main frame
            driver.switch_to.default_content()
        except NoSuchElementException:
            logger.warning(
                f"Captcha element not found. Restarting...Attempt: {self.run_attempts+1}"
            )
            logger.info(f"current judge: {self.judge_name}")
            driver.quit()
            return self.run()

    def run(self):

        driver = setup_browser_driver(
            os.path.join(default_temp_download_folder, self.judge_name), is_headless=False
        )

        if self.run_attempts > 2:
            logger.error("Could not solve captcha. Try again later.")
            driver.quit()
            exit()

        self.run_attempts += 1

        driver.get("https://sap.pj.gob.pe/casillero-digital-web/#/busqueda")
        self.wait_between()
        action_chains = ActionChains(driver)

        autocomplete = driver.find_elements(By.CLASS_NAME, "p-autocomplete-input")[0]
        self.human_like_mouse_move(action_chains, autocomplete)

        autocomplete.send_keys(self.judge_name)
        time.sleep(3)

        try:
            # Select the first option from the autocomplete list
            autocomplete_list = driver.find_element(By.ID, "pr_id_2_list")
            self.human_like_mouse_move(action_chains, autocomplete_list)
            autocomplete_list_items = autocomplete_list.find_elements(By.TAG_NAME, "li")
            self.human_like_mouse_move(action_chains, autocomplete_list_items[0])
            autocomplete_list_items[0].click()
        except NoSuchElementException:
            logger.error(f"judge; {self.judge_name} not found. Exiting...")
            driver.quit()
            exit()

        self.wait_between()

        if self.run_attempts > 0: # to change to 1
            logger.info("Attempting to use captcha solver API...")
            # token_answer = azcaptcha_recaptchav2_solver_post()
            token_answer = "OafEX5kjR3VRxphf8d4YsV6xfibTl9qJDEk2I5D7cIAPNF9rdSuWDLMNreXe9PBUo39-Sik9x8kxrtVPbAMOq6s2EFiUCStDE4SnH9HU8BW9Ks9Qt1FBbdC79qnxKk4SzggQ2WhQRbUt_WRe3Kf3t-yfg"
            try:
                driver.execute_script(
                    f"return document.evaluate(\"//div[@class='aling-catcha']/re-captcha/div/textarea[@id='g-recaptcha-response-1']\", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue.style.display = 'block'"
                )
                g_response = driver.execute_script(
                    f"return document.evaluate(\"//div[@class='aling-catcha']/re-captcha/div/textarea[@id='g-recaptcha-response-1']\", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue.innerHTML ='{token_answer}'"
                )                
            
                print(f"g_response: {g_response}")
                driver.execute_script(
                    f'___grecaptcha_cfg.clients[0].X.X.callback("{token_answer}")'
                )
            except Exception as e:
                logger.error(f"driver exceute script error -> {e}")
        else:
            self.solve_captcha_manually(action_chains, driver)

        if self.is_captcha_image_pop_up_visible(driver):
            logger.error(
                f"Could not solve captcha. Restarting...Attempt: {self.run_attempts+1}"
            )
            logger.info(f"current judge: {self.judge_name}")
            driver.quit()
            return self.run()

        # Wait for the autocomplete list to appear
        self.wait_between()

        buttons = driver.find_elements(By.CLASS_NAME, "p-button-raised")
        if len(buttons) > 0:
            submit_btn = buttons[0]
            self.human_like_mouse_move(action_chains, submit_btn)
            submit_btn.click()
            time.sleep(3)
            if not is_element_present("class name", "swal2-container", driver):
                self.scrap_resolution_download_btns(driver)
            else:
                logger.error("Could not solve captcha. Try again later.")
                time.sleep(3600)  # to remove this
                driver.quit()
                exit()
        else:
            logger.error("Submit button not found.")
            driver.quit()
            exit()


if __name__ == "__main__":

    for judge in judges_names:
        try:
            pj_scrapper = PjScrapper(judge)
            pj_scrapper.run()
        except Exception as e:
            logger.error(e)
            kill_os_process("firefox")
            kill_os_process("geckodriver")
