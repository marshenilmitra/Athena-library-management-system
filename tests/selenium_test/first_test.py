"""Simple Selenium smoke test for the current LMS frontend login UI."""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "http://127.0.0.1:5000"

options = Options()
options.add_argument("--headless=new")
options.add_argument("--window-size=1400,1200")

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 15)

try:
    driver.get(BASE_URL)

    login_modal = wait.until(EC.visibility_of_element_located((By.ID, "loginModal")))
    username_input = wait.until(EC.visibility_of_element_located((By.ID, "loginUsername")))
    password_input = driver.find_element(By.ID, "loginPassword")

    assert "show" in login_modal.get_attribute("class")
    assert username_input.is_displayed()
    assert password_input.is_displayed()

    admin_chip = driver.find_element(By.XPATH, "//button[contains(., 'Admin') and contains(@class, 'chip')]")
    admin_chip.click()

    wait.until(lambda d: d.find_element(By.ID, "loginUsername").get_attribute("value") == "admin")
    wait.until(lambda d: d.find_element(By.ID, "loginPassword").get_attribute("value") == "Admin@123")

    assert driver.title == "Athena Enterprise LMS - Executive Portal"
    print(f"PASS: login modal and quick-login UI loaded successfully at {driver.current_url}")

finally:
    driver.quit()