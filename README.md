# Bulk Download LE

This Python script automates the downloading of submitted Limited Engagement (LE) forms across multiple semesters from the Acado Informatics portal. 

## How to Use

1. **Install Dependencies**: 
   ```bash
   pip install selenium webdriver-manager
   ```
2. **Setup Credentials**: Create or update the `config.py` file.
3. **Run the Script**:
   ```bash
   python LE_download.py
   ```
4. The script will automatically create a `downloads/` directory within this project and organize files into `downloads/<Semester>/<Course>/`.

## Passing Credentials

Create a `config.py` file in the root directory and define your login credentials:

```python
USERNAME = "your_username"
PASSWORD = "your_password"
```

## Logging

The logging mechanism is built via a custom `Logger` class that overwrites standard output and standard error:
- Console prints and error traces are simultaneously written to the terminal and appended to `run.log`.
- This ensures a complete execution history is kept in the text log for debugging and verification.

## Error Handling

- **Session Management**: A helper function `ensure_logged_in()` constantly guards against session timeouts by logging back in automatically.
- **Download Retries**: Downloads use a **3-attempt retry loop**. If a download fails (e.g., due to network interruptions), it waits 2 seconds before retrying.
- **Missing Forms Report**: If any form fails to download entirely, or if rows cannot be located, the failure is tracked in memory. Upon script completion, a markdown report named `missing_le_report.md` is generated outlining the Semester, Course, Student, and exact failure reason.
- **State Recovery**: The script dynamically handles `StaleElementReferenceException` by re-scanning the DOM to regain context without crashing.
