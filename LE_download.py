import os
import time
import re
import urllib.request
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import Select

# === CONFIG ===
LOGIN_URL = "https://app.acadoinformatics.com/syllabus/department/login/"
from config import USERNAME, PASSWORD
DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

def sanitize_filename(name):
    """Sanitizes strings to be safe for filenames."""
    # Replace slashes and other illegal characters
    return re.sub(r'[<>:"/\\|?*]', '_', name)


# === HELPER: NAVIGATE TO LE FORMS ===
def navigate_to_le_forms():
    print("🔄 Navigating to View LE forms...")
    try:
        driver.get("https://app.acadoinformatics.com/syllabus/department/tools/ListLimitedEngagement")
    except Exception as e2:
        print(f"❌ Could not navigate to LE forms link: {e2}")
    time.sleep(3)

# === HELPER: CHECK LOGIN ===
def ensure_logged_in(driver):
    """Checks if we are on the login page; if logged out, logs back in."""
    try:
        if len(driver.find_elements(By.NAME, "username")) > 0:
            print("⚠️ Session expired. Logging in again...")
            driver.find_element(By.NAME, "username").send_keys(USERNAME)
            driver.find_element(By.NAME, "password").send_keys(PASSWORD)
            try:
                driver.find_element(By.XPATH, "//button[contains(text(), 'Log In')]").click()
            except:
                driver.find_element(By.NAME, "password").send_keys(Keys.ENTER)
            time.sleep(3)
            navigate_to_le_forms()
    except Exception as e:
        print(f"❌ Error in session check: {e}")

# === SETUP DRIVER ===
options = webdriver.ChromeOptions()
prefs = {
    "download.default_directory": DOWNLOAD_DIR,
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "safebrowsing.enabled": True,
    "plugins.always_open_pdf_externally": True
}
options.add_experimental_option("prefs", prefs)

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
driver.get(LOGIN_URL)
time.sleep(2)

# === INITIAL LOGIN STEP ===
ensure_logged_in(driver)
# Fallback login click
if "login" in driver.current_url.lower():
    driver.find_element(By.NAME, "username").send_keys(USERNAME)
    driver.find_element(By.NAME, "password").send_keys(PASSWORD)
    driver.find_element(By.XPATH, "//button[contains(text(), 'Log In')]").click()
    time.sleep(3)
    navigate_to_le_forms()

# === GET SEMESTERS FROM DROPDOWN ===
print("Fetching semester list...")
ensure_logged_in(driver)

try:
    semester_select_elem = driver.find_element(By.ID, "select-semester")
    select = Select(semester_select_elem)
    semester_options_count = len(select.options)
    print(f"Found {semester_options_count} semesters.")
except Exception as e:
    print(f"❌ Could not find semester dropdown: {e}")
    driver.quit()
    exit(1)

# === BUILD TARGET ENTRIES DICT ===
# Structure: (semester_text, course_text, first_name, last_name) -> form_status_text
print("\nScanning all semesters to build a download list...")
latest_entries = {}

for i in range(semester_options_count):
    try:
        ensure_logged_in(driver)
        
        # Re-find select to prevent stale element reference
        semester_select_elem = driver.find_element(By.ID, "select-semester")
        select = Select(semester_select_elem)
        
        if i >= len(select.options):
            break
            
        option = select.options[i]
        semester_text = option.text.strip()
        
        if "Select" in semester_text:
            continue

        print(f"[{i+1}/{semester_options_count}] Scanning: {semester_text}")
        select.select_by_index(i)
        time.sleep(6)  # Increased wait for table to load

        # Scan tables and track the course, name, and column 6 link
        tables = driver.find_elements(By.TAG_NAME, "table")
        count_for_sem = 0
        
        for table in tables:
            try:
                rows = table.find_elements(By.TAG_NAME, "tr")
                # Ensure it's not strictly a header-only table
                if len(rows) <= 1: continue

                for row in rows:
                    if row.find_elements(By.TAG_NAME, "th"):
                        continue  # Skip header row

                    cells = row.find_elements(By.TAG_NAME, "td")
                    # Current expected format:
                    # ['Course', 'Last Name', 'First Name', 'Hours', 'Payment', 'Due Date', 'Form Status']
                    if len(cells) < 7:
                        continue
                    
                    course_name = cells[0].text.strip()
                    last_name = cells[1].text.strip().lower()
                    first_name = cells[2].text.strip().lower()
                    
                    # Target the 'Form Status' column for the link (index 6)
                    try:
                        # Ensure there is an '<a>' tag and the form text says "submitted"
                        links = cells[6].find_elements(By.TAG_NAME, "a")
                        if links and "submitted" in cells[6].text.lower():
                            key = (semester_text, course_name, first_name, last_name)
                            # Overwrite to get the latest row if a duplicate appears
                            latest_entries[key] = (semester_text, course_name, first_name, last_name)
                            count_for_sem += 1
                    except Exception:
                        pass
                        
            except Exception:
                pass
                
        if count_for_sem > 0:
            print(f"   -> Found {count_for_sem} LE forms.")

    except Exception as e:
        print(f"⚠️ Error processing semester index {i}: {e}")
        navigate_to_le_forms()  # Force recovery on complete failure


# === PRINT SUMMARY BEFORE DOWNLOADING ===
print(f"\nTotal unique entries to download across all semesters: {len(latest_entries)}\n")
# xyx = input("Hit enter to start downloading")


# === BATCH DOWNLOAD PROCESS ===
# Group by semester to minimize dropdown switching
entries_by_semester = {}
for (sem_text, course_text, fname, lname) in latest_entries.values():
    if sem_text not in entries_by_semester:
        entries_by_semester[sem_text] = []
    entries_by_semester[sem_text].append((course_text, fname, lname))

print("\nStarting download process (grouped by semester)...")
failed_entries = []

for semester_text, forms in entries_by_semester.items():
    try:
        print(f"\n📂 Processing Semester: {semester_text}")
        ensure_logged_in(driver)
        
        # Select target semester
        semester_select_elem = driver.find_element(By.ID, "select-semester")
        Select(semester_select_elem).select_by_visible_text(semester_text)
        time.sleep(6)  # Increased wait for table to load
        
        # Re-fetch table rows specifically in this semester context
        def get_current_semester_map():
            m = {}
            for t in driver.find_elements(By.TAG_NAME, "table"):
                for r in t.find_elements(By.TAG_NAME, "tr"):
                    try:
                        c = r.find_elements(By.TAG_NAME, "td")
                        if len(c) >= 7:
                            c_name = c[0].text.strip()
                            l_name = c[1].text.strip().lower()
                            f_name = c[2].text.strip().lower()
                            m[(c_name, f_name, l_name)] = r
                    except:
                        pass
            return m
            
        current_semester_map = get_current_semester_map()

        for course_name, fname, lname in forms:
            # Map dictionary key
            target_key = (course_name, fname, lname)
            
            # Sub-directory Path Setup
            safe_semester = sanitize_filename(semester_text)
            safe_course = sanitize_filename(course_name)
            target_dir = os.path.join(DOWNLOAD_DIR, safe_semester, safe_course)
            
            # Clean filename
            safe_fname = sanitize_filename(fname.title())
            safe_lname = sanitize_filename(lname.title())
            file_prefix = f"{safe_fname}_{safe_lname}"
            
            # Ensure folder exists
            os.makedirs(target_dir, exist_ok=True)
            
            # Quick check if it already exists (to save time finding the row)
            already_exists = any(f.startswith(file_prefix) for f in os.listdir(target_dir))
            if already_exists:
                print(f"⏩ Skipping {course_name} / {safe_fname}_{safe_lname} (already exists)")
                continue
                
            if target_key not in current_semester_map:
                print(f"⚠️ Could not find LE form row during execution for {safe_fname} {safe_lname} in {course_name}.")
                failed_entries.append(f"| {semester_text} | {course_name} | {safe_fname} {safe_lname} | Row not found in re-scan |")
                continue
                
            try:
                row_elem = current_semester_map[target_key]
                cells = row_elem.find_elements(By.TAG_NAME, "td")
                
                if "submitted" not in cells[6].text.lower():
                    print(f"⚠️ {safe_fname} {safe_lname} in {course_name} is not marked as submitted. Skipping.")
                    continue
                    
                download_link = cells[6].find_element(By.TAG_NAME, "a")
                
                download_url = download_link.get_attribute('href')
                
                # Fetch extension (assume PDF if unknown depending on URL)
                ext = ".pdf"
                if "." in download_url.split("/")[-1]:
                     ext = "." + download_url.split("/")[-1].split(".")[-1]
                     
                new_name = f"{file_prefix}{ext}"
                new_path = os.path.join(target_dir, new_name)
                
                # Download File payload securely straight into its final folder
                # The browser subagent confirmed these S3 urls are public and require no cookies
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        urllib.request.urlretrieve(download_url, new_path)
                        print(f"✅ Downloaded to {safe_semester}/{safe_course}/: {new_name}")
                        break
                    except Exception as download_err:
                        if attempt < max_retries - 1:
                            print(f"   ⚠️ Download failed ({download_err}). Retrying {attempt + 1}/{max_retries}...")
                            time.sleep(2)
                        else:
                            raise download_err

            except TimeoutError:
                print(f"❌ Timeout/Missing File for {safe_fname} {safe_lname}. Checking for Error Page...")
                failed_entries.append(f"| {semester_text} | {course_name} | {safe_fname} {safe_lname} | Timeout/Missing File |")
                
                if "department" not in driver.current_url.lower():
                    print("   ↩️ Error Page detected. Going back...")
                    driver.back()
                    time.sleep(3)
                    print("   🔄 Re-scanning DOM to fix stale references...")
                    current_semester_map = get_current_semester_map()

            except Exception as e:
                print(f"❌ Failed download {safe_fname} {safe_lname} in {course_name}: {e}")
                failed_entries.append(f"| {semester_text} | {course_name} | {safe_fname} {safe_lname} | Error: {str(e)} |")
                
                needs_rescan = False
                if "stale element reference" in str(e).lower():
                    needs_rescan = True
                    print("   ⚠️ Stale Element detected.")

                if "login" in driver.current_url.lower():
                     print("   ⚠️ Redirected to login. Will re-login on next loop.")
                     needs_rescan = True 
                else:
                     if "department" not in driver.current_url.lower():
                         print("   ↩️ Navigated away. Going back...")
                         driver.back()
                         time.sleep(3)
                         needs_rescan = True
                
                if needs_rescan:
                    print("   🔄 Re-scanning DOM to fix stale references...")
                    current_semester_map = get_current_semester_map()

    except Exception as e:
         print(f"❌ Error handling semester {semester_text}: {e}")
         navigate_to_le_forms()  # Force recovery on complete failure

print("\nDone downloading.")

# === GENERATE REPORT ===
if failed_entries:
    report_path = os.path.join(os.getcwd(), "missing_le_report.md")
    with open(report_path, "w") as f:
        f.write("# Missing LE Form Report\n\n")
        f.write(f"Total Missing: {len(failed_entries)}\n\n")
        f.write("| Semester | Course | Student | Reason |\n")
        f.write("|---|---|---|---|\n")
        for entry in failed_entries:
            f.write(entry + "\n")
    print(f"\n📄 Report generated: {report_path}")
else:
    print("\n✅ All LE forms downloaded successfully!")
