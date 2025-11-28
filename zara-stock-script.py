from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, NoSuchElementException
import time
import os
import random
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication

# -----------------------------
# 1) Profil & ChromeDriver
# -----------------------------
profile_path = "PATH/TO/YOUR/SELENIUM/PROFILE"
os.makedirs(profile_path, exist_ok=True)

chrome_driver_path = "PATH/TO/YOUR/CHROMEDRIVER"

chrome_options = Options()
chrome_options.add_argument(f"--user-data-dir={profile_path}")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--start-maximized")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--log-level=3")
chrome_options.add_argument("--enable-unsafe-swiftshader")

service = Service(chrome_driver_path)
driver = webdriver.Chrome(service=service, options=chrome_options)

# -----------------------------
# 2) Product list
# -----------------------------
products = {
    "LINK_TO_PRODUCT_1": ["SIZE1", "SIZE2"],
    "LINK_TO_PRODUCT_2": ["SIZE1", "SIZE2", "SIZE3"],
}

# -----------------------------
# 3) State dictionary
# -----------------------------
previous_stock = {url: {size: "YOK" for size in sizes} for url, sizes in products.items()}

# -----------------------------
# 4) Screenshot + Save HTML
# -----------------------------
def save_snapshot_with_stock(driver, product_name):
    screenshot_path = f"{product_name.replace(' ', '_')}.png"
    driver.save_screenshot(screenshot_path)
    return screenshot_path

# -----------------------------
# 5) Send Email
# -----------------------------
def send_email(subject, stock_result, screenshot_file, product_url):
    sender_email = "YOUR SENDER EMAIL ADDRESS"
    sender_pass = "YOUR APP PASSWORD"  # App password
    receiver_email = "YOUR RECEIVER EMAIL ADDRESS"

    # HTML tablosu oluştur
    table_html = "<table border='1' cellpadding='5' cellspacing='0' style='border-collapse: collapse;'>"
    table_html += "<tr><th>Beden</th><th>Durum</th></tr>"
    for size, status in stock_result.items():
        table_html += f"<tr><td>{size}</td><td>{status}</td></tr>"
    table_html += "</table>"

    # Mail gövdesi HTML
    html_body = f"""
    <html>
        <body>
            <p>Stok durumu değişti:</p>
            <p>Ürün linki: <a href="{product_url}">{product_url}</a></p>
            {table_html}
        </body>
    </html>
    """

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject
    msg.attach(MIMEText(html_body, 'html'))

    # Screenshot attachment
    with open(screenshot_file, "rb") as f:
        img_part = MIMEApplication(f.read(), Name=os.path.basename(screenshot_file))
        img_part['Content-Disposition'] = f'attachment; filename="{os.path.basename(screenshot_file)}"'
        msg.attach(img_part)

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_pass)
        server.send_message(msg)
        server.quit()
        print("Email sent successfully.")
    except Exception as e:
        print(f"Failed to send email: {e}")


# -----------------------------
# 6) Check stock function
# -----------------------------
def check_stock_zara(driver, sizes_to_check):
    try:
        wait = WebDriverWait(driver, 10)

        # Close cookie alert
        try:
            accept_cookies_button = wait.until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler")))
            accept_cookies_button.click()
        except TimeoutException:
            pass

        # Wait for Add to Cart
        try:
            add_to_cart_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-qa-action='add-to-cart']")))
            overlays = driver.find_elements(By.CLASS_NAME, "zds-backdrop")
            if overlays:
                driver.execute_script("arguments[0].remove();", overlays[0])
            driver.execute_script("arguments[0].click();", add_to_cart_button)
        except (TimeoutException, ElementClickInterceptedException):
            print("Failed to click 'Add to Cart'.")
            return {}

        # Size selector
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "size-selector-sizes")))
        size_elements = driver.find_elements(By.CLASS_NAME, "size-selector-sizes-size")
        result = {size: "YOK" for size in sizes_to_check}

        for li in size_elements:
            try:
                size_label = li.find_element(By.CSS_SELECTOR, "div[data-qa-qualifier='size-selector-sizes-size-label']").text.strip()
                if size_label in sizes_to_check:
                    button = li.find_element(By.CLASS_NAME, "size-selector-sizes-size__button")
                    try:
                        similar_text = button.find_element(By.CLASS_NAME, "size-selector-sizes-size__action").text.strip()
                        if "Benzer ürünler" in similar_text:
                            result[size_label] = "YOK"
                            continue
                    except NoSuchElementException:
                        pass
                    action = button.get_attribute("data-qa-action")
                    if action == "size-in-stock":
                        result[size_label] = "VAR"
                    elif action == "size-low-on-stock":
                        result[size_label] = "AZ"
                    else:
                        result[size_label] = "YOK"
            except:
                continue
        return result
    except Exception as e:
        print(f"Error in check_stock_zara: {e}")
        return {}

# -----------------------------
# 7) Infinite check loop
# -----------------------------
try:
    while True:
        for url, size_list in products.items():
            driver.get(url)
            time.sleep(random.uniform(2,4))
            stock_result = check_stock_zara(driver, size_list)
            product_name = driver.find_element(By.TAG_NAME, "h1").text.strip()

            # Daha önceki state ile karşılaştır
            state_changed = any(previous_stock[url][size] != stock_result[size] for size in size_list)

            if state_changed:
                save_snapshot_with_stock(driver, product_name)
                previous_stock[url] = stock_result.copy()
                # Mail gönder
                screenshot_file = f"{product_name.replace(' ', '_')}.png"
                driver.save_screenshot(screenshot_file)
                send_email(f"Stock Alert: {product_name}", stock_result, screenshot_file, url)

            for size, status in stock_result.items():
                print(f"[{status}] {size} beden → {url}")

        wait_time = random.randint(60, 180)
        print(f"\nYeni kontrol için {wait_time} saniye bekleniyor...\n")
        time.sleep(wait_time)

except KeyboardInterrupt:
    print("Bot durduruldu.")
finally:
    driver.quit()
