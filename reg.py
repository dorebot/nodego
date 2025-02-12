import sys
import json
import traceback
import random
import datetime
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from colorama import init, Fore, Style
import requests  # Standard requests library
from solve_turnstile import solve_turnstile

init(autoreset=True)

def banner():
    print(Fore.GREEN + r"""
██████╗  ██████╗ ██████╗ ███████╗ █████╗ ███╗   ███╗ ██████╗ ███╗   ██╗
██╔══██╗██╔═══██╗██╔══██╗██╔════╝██╔══██╗████╗ ████║██╔═══██╗████╗  ██║
██║  ██║██║   ██║██████╔╝█████╗  ███████║██╔████╔██║██║   ██║██╔██╗ ██║
██║  ██║██║   ██║██╔══██╗██╔══╝  ██╔══██║██║╚██╔╝██║██║   ██║██║╚██╗██║
██████╔╝╚██████╔╝██║  ██║███████╗██║  ██║██║ ╚═╝ ██║╚██████╔╝██║ ╚████║
╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═══╝                                                                      
              MADE BY :- Đôrêmon                               
    """ + Style.RESET_ALL)

REFERRAL_CODES = [
"REPLACE CODE",
"REPLACE CODE",
]

# Global locks for safe file writing across threads
access_token_lock = threading.Lock()
refer_lock = threading.Lock()

def get_timestamp():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log_info(message):
    print(f"{Fore.CYAN}{get_timestamp()} [INFO]{Style.RESET_ALL} {message}")

def log_warn(message):
    print(f"{Fore.YELLOW}{get_timestamp()} [WARN]{Style.RESET_ALL} {message}")

def log_error(message):
    print(f"{Fore.RED}{get_timestamp()} [ERROR]{Style.RESET_ALL} {message}")

def load_lines(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        log_error(f"'{filename}' not found. Please create it and add required data.")
        sys.exit(1)

def register_account(index, proxy_line, username, email, password):
    proxies = {
        "http": proxy_line,
        "https": proxy_line
    }
    log_info(f"Account #{index+1}: Attempting registration with proxy: {proxy_line}")

    try:
        # Solve captcha
        CAPTCHA_SITE_KEY = "0x4AAAAAAA4zgfgCoYChIZf4"
        PAGE_URL         = "https://app.nodego.ai"
        TWO_CAPTCHA_API  = "YOUR API KEY"
        captcha_solution = solve_turnstile(
            TWO_CAPTCHA_API,
            CAPTCHA_SITE_KEY,
            PAGE_URL
        )
        log_info(f"Account #{index+1}: Captcha solved! Token: {captcha_solution}")

        # Prepare registration data
        ref_code = random.choice(REFERRAL_CODES)
        url = "https://nodego.ai/api/auth/register"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " 
                          "(KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
        }
        payload = {
            "username": username,
            "email": email,
            "password": password,
            "refBy": ref_code,
            "captcha": captcha_solution
        }

        # Send registration request (SSL verification disabled)
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            proxies=proxies,
            timeout=30,
            verify=False  # Use with caution!
        )

        # Check response status
        if response.status_code not in [200, 201]:
            raise Exception(f"Registration failed: {response.status_code} - {response.text}")

        data = response.json()
        log_info(f"Account #{index+1}: Registration response: {data}")

        # Get access token from the response
        access_token = data.get("metadata", {}).get("accessToken")
        if not access_token:
            log_warn(f"Account #{index+1}: No access token found for {email}.")
            return

        log_info(f"Account #{index+1}: AccessToken for {email}: {access_token}")

        # Save the access token (use lock to avoid concurrent write issues)
        with access_token_lock:
            with open("accessToken.txt", "a", encoding="utf-8") as out_file:
                out_file.write(access_token + "\n")

        # Make an additional request to /me
        me_url = "https://nodego.ai/api/user/me"
        me_headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Authorization": f"Bearer {access_token}",
            "If-None-Match": 'W/"255-Jn4vhkHxPsnpjuk3W/ksa8vukGE"',
            "Priority": "u=1, i",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
        }

        me_response = requests.get(
            me_url,
            headers=me_headers,
            proxies=proxies,
            timeout=30,
            verify=False
        )

        if me_response.status_code not in [200, 304]:
            log_warn(f"Account #{index+1}: /me request returned status "
                     f"{me_response.status_code}: {me_response.text}")

        me_data = me_response.json()
        with refer_lock:
            with open("refer.txt", "a", encoding="utf-8") as ref_file:
                ref_file.write(json.dumps(me_data) + "\n")

        log_info(f"Account #{index+1}: refer code saved ✅")

    except Exception as ex:
        log_error(f"Account #{index+1} ({email}): Registration error: {ex}")
        traceback.print_exc()

def worker_register():
    banner()
    proxy_lines = load_lines("proxy.txt")
    username_lines = load_lines("username.txt")
    account_lines = load_lines("accounts.txt")

    if not proxy_lines:
        log_error("No proxies found in 'proxy.txt'.")
        return
    if not username_lines:
        log_error("No usernames found in 'username.txt'.")
        return
    if not account_lines:
        log_error("No accounts found in 'accounts.txt'.")
        return

    total = min(len(proxy_lines), len(username_lines), len(account_lines))
    if total == 0:
        log_error("Mismatch or no data in proxy/username/accounts. Exiting...")
        return

    log_info(f"Starting registration for {total} accounts using 1 threads...")

    # Use ThreadPoolExecutor to run registrations concurrently
    with ThreadPoolExecutor(max_workers=1) as executor:
        futures = []
        for i in range(total):
            proxy_line = proxy_lines[i]
            username = username_lines[i]
            account_parts = account_lines[i].split(":", 1)
            if len(account_parts) < 2:
                log_warn(f"Invalid account format at line {i+1} in 'accounts.txt'. Skipping...")
                continue

            email, password = account_parts[0], account_parts[1]
            futures.append(
                executor.submit(register_account, i, proxy_line, username, email, password)
            )

        # Wait for all threads to complete
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                log_error(f"Exception raised during registration: {exc}")

    log_info("Registration process completed.")

def main():
    worker_register()

if __name__ == "__main__":
    main()
