"""Portfolio-ready Selenium UI tests for the current LMS frontend."""

import os
import sys

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:5000")
TIMEOUT = 15


@pytest.fixture
def browser():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1400,1200")

    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(2)
    try:
        yield driver
    finally:
        driver.quit()


def _wait_for_login(browser, username, password):
    wait = WebDriverWait(browser, TIMEOUT)
    wait.until(EC.visibility_of_element_located((By.ID, "loginModal")))
    browser.find_element(By.ID, "loginUsername").clear()
    browser.find_element(By.ID, "loginUsername").send_keys(username)
    browser.find_element(By.ID, "loginPassword").clear()
    browser.find_element(By.ID, "loginPassword").send_keys(password)
    browser.find_element(By.CSS_SELECTOR, "#loginForm button[type='submit']").click()
    wait.until(lambda d: d.find_element(By.ID, "userName").text.lower() != "guest session")
    return wait


def test_login_modal_and_quick_login_work(browser):
    browser.get(BASE_URL)
    wait = WebDriverWait(browser, TIMEOUT)

    login_modal = wait.until(EC.visibility_of_element_located((By.ID, "loginModal")))
    assert "show" in login_modal.get_attribute("class")
    assert browser.find_element(By.ID, "loginUsername").is_displayed()
    assert browser.find_element(By.ID, "loginPassword").is_displayed()

    browser.find_element(By.XPATH, "//button[contains(., 'Admin') and contains(@class, 'chip')]").click()
    wait.until(lambda d: d.find_element(By.ID, "loginUsername").get_attribute("value") == "admin")
    wait.until(lambda d: d.find_element(By.ID, "loginPassword").get_attribute("value") == "Admin@123")

    browser.find_element(By.CSS_SELECTOR, "#loginForm button[type='submit']").click()
    wait.until(lambda d: d.find_element(By.ID, "userName").text == "admin")
    wait.until(lambda d: d.find_element(By.ID, "userRoleBadge").text == "Admin")

    assert "Catalog Directory" in browser.page_source


def test_catalog_controls_render_after_login(browser):
    _wait_for_login(browser, "admin", "Admin@123")

    wait = WebDriverWait(browser, TIMEOUT)
    search_input = wait.until(EC.visibility_of_element_located((By.ID, "catalogSearchInput")))
    category_filter = browser.find_element(By.ID, "catalogCategoryFilter")
    availability_filter = browser.find_element(By.ID, "catalogAvailabilityFilter")
    books_grid = browser.find_element(By.ID, "booksGrid")

    assert search_input.is_displayed()
    assert category_filter.is_displayed()
    assert availability_filter.is_displayed()
    assert books_grid.is_displayed()


def test_member_role_hides_staff_only_controls(browser):
    _wait_for_login(browser, "member1", "Mem@123")

    wait = WebDriverWait(browser, TIMEOUT)
    wait.until(lambda d: d.find_element(By.ID, "userRoleBadge").text == "Member")

    circulation_btn = browser.find_element(By.CSS_SELECTOR, "button[data-tab='circulation']")
    reports_btn = browser.find_element(By.CSS_SELECTOR, "button[data-tab='reports']")

    assert "hidden" in circulation_btn.get_attribute("class")
    assert "hidden" in reports_btn.get_attribute("class")


def test_logout_returns_user_to_login_modal(browser):
    _wait_for_login(browser, "librarian", "Lib@123")

    browser.find_element(By.ID, "logoutBtn").click()

    wait = WebDriverWait(browser, TIMEOUT)
    login_modal = wait.until(EC.visibility_of_element_located((By.ID, "loginModal")))
    assert "show" in login_modal.get_attribute("class")
    assert browser.find_element(By.ID, "userName").text == "Guest Session"