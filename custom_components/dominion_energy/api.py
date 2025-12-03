"""API client for Dominion Energy."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

import aiohttp

# Support both relative imports (when used as HA integration) and absolute imports (for testing)
try:
    from .const import (
        ACTION_CODE,
        API_BASE_URL,
        ACCOUNT_MGMT_API_BASE_URL,
        USAGE_API_BASE_URL,
        BILLING_API_BASE_URL,
        BILL_FORECAST_ENDPOINT,
        BILL_HISTORY_ENDPOINT,
        DEFAULT_HEADERS,
        LOGIN_URL,
        USAGE_HISTORY_ENDPOINT,
        USAGE_HISTORY_DETAIL_ENDPOINT,
        USAGE_DATA_ENDPOINT,
        METERS_ENDPOINT,
        ELECTRIC_USAGE_ENDPOINT,
        GENERATION_ENDPOINT,
        BILL_CURRENT_ENDPOINT,
        BILL_HISTORY_BILLING_ENDPOINT,
        GET_BP_NUMBER_ENDPOINT,
        GET_BUSINESS_MASTER_ENDPOINT,
    )
except ImportError:
    from const import (
        ACTION_CODE,
        API_BASE_URL,
        ACCOUNT_MGMT_API_BASE_URL,
        USAGE_API_BASE_URL,
        BILLING_API_BASE_URL,
        BILL_FORECAST_ENDPOINT,
        BILL_HISTORY_ENDPOINT,
        DEFAULT_HEADERS,
        LOGIN_URL,
        USAGE_HISTORY_ENDPOINT,
        USAGE_HISTORY_DETAIL_ENDPOINT,
        USAGE_DATA_ENDPOINT,
        METERS_ENDPOINT,
        ELECTRIC_USAGE_ENDPOINT,
        GENERATION_ENDPOINT,
        BILL_CURRENT_ENDPOINT,
        BILL_HISTORY_BILLING_ENDPOINT,
        GET_BP_NUMBER_ENDPOINT,
        GET_BUSINESS_MASTER_ENDPOINT,
    )

_LOGGER = logging.getLogger(__name__)

# Thread pool for running Selenium in async context
_executor = ThreadPoolExecutor(max_workers=1)

# Type alias for TFA callbacks
# TfaCallback for verification code: takes no arguments, returns the code
TfaCodeCallback = Callable[[], str]
# TfaChoiceCallback for choosing options: takes list of options, returns selected index
TfaChoiceCallback = Callable[[list[dict[str, Any]]], int]


@dataclass
class DominionEnergyData:
    """Data class for Dominion Energy usage data."""

    # Energy data (kWh)
    grid_consumption: float | None = None
    grid_return: float | None = None
    monthly_usage: float | None = None

    # Solar generation data (kWh)
    solar_generation: float | None = None  # Current month generation
    monthly_generation: list[dict[str, Any]] | None = None  # Monthly generation history

    # Daily data (from UsageData API - great for HA energy dashboard)
    daily_consumption: list[dict[str, Any]] | None = None  # Daily consumption history
    daily_generation: list[dict[str, Any]] | None = None  # Daily solar generation history
    
    # Today's data (most recent day from UsageData API)
    today_consumption: float | None = None  # Today's grid consumption (kWh)
    today_generation: float | None = None  # Today's solar generation (kWh)
    today_net_usage: float | None = None  # Today's net usage (consumption - generation)
    
    # Yesterday's data (second most recent day from UsageData API)
    yesterday_consumption: float | None = None  # Yesterday's grid consumption (kWh)
    yesterday_generation: float | None = None  # Yesterday's solar generation (kWh)
    yesterday_net_usage: float | None = None  # Yesterday's net usage (consumption - generation)
    
    # Hourly data (from UsageData API with ActionCode=4)
    hourly_consumption: list[dict[str, Any]] | None = None  # Hourly consumption
    hourly_generation: list[dict[str, Any]] | None = None  # Hourly solar generation

    # Billing data
    current_bill: float | None = None
    billing_period_start: datetime | None = None
    billing_period_end: datetime | None = None
    bill_due_date: datetime | None = None
    previous_balance: float | None = None
    payment_received: float | None = None
    remaining_balance: float | None = None
    total_amount_due: float | None = None  # Total amount due on account
    
    # Last bill comparison
    last_bill_amount: float | None = None  # Previous month's bill amount
    last_bill_usage: float | None = None  # Previous month's usage (kWh)
    last_year_bill_amount: float | None = None  # Same month last year bill
    last_year_usage: float | None = None  # Same month last year usage (kWh)
    
    # Payment info
    last_payment_date: datetime | None = None
    last_payment_amount: float | None = None

    # Rate data
    current_rate: float | None = None
    daily_cost: float | None = None
    rate_category: str | None = None  # e.g., "VR-1"

    # Usage history for statistics
    daily_usage: list[dict[str, Any]] | None = None
    daily_return: list[dict[str, Any]] | None = None
    
    # Bill history
    bill_history: list[dict[str, Any]] | None = None
    
    # Account flags and dates
    next_meter_read_date: datetime | None = None  # Next scheduled meter read
    auto_pay_enabled: bool | None = None  # Whether auto-pay is enabled
    is_net_metering: bool | None = None  # Whether account has net metering (solar)
    is_ami_meter: bool | None = None  # Whether account has smart meter (AMI)
    
    # Weather data (from GetUsageHistoryDetail API)
    daily_high_temp: int | None = None  # Most recent day's high temp (°F)
    daily_low_temp: int | None = None  # Most recent day's low temp (°F)
    heating_degree_days: int | None = None  # Most recent day's heating degree days
    cooling_degree_days: int | None = None  # Most recent day's cooling degree days
    monthly_avg_temp: int | None = None  # Current month's average temperature
    
    # Meter info (from Meters API)
    meter_number: str | None = None  # Full meter number
    meter_id: int | None = None  # Internal meter ID
    meter_type: str | None = None  # Meter type code
    account_number: str | None = None  # Full account number


class DominionEnergyApiError(Exception):
    """Exception for Dominion Energy API errors."""


class DominionEnergyAuthError(DominionEnergyApiError):
    """Exception for authentication errors."""


class DominionEnergyApi:
    """API client for Dominion Energy."""

    def __init__(
        self,
        username: str,
        password: str,
        account_number: str,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize the API client."""
        self._username = username
        self._password = password
        # Account number should be 12 digits with leading zeros
        self._account_number = account_number.zfill(12)
        self._session = session
        self._token: str | None = None
        self._refresh_token: str | None = None
        self._token_expires: float = 0  # Unix timestamp when token expires
        self._uuid: str | None = None
        self._cookies: dict[str, str] = {}
        self._own_session = False
        self._tfa_code_callback: TfaCodeCallback | None = None
        self._tfa_choice_callback: TfaChoiceCallback | None = None
        self._customer_number: str | None = None  # Business partner number
        self._contract: str | None = None  # Contract number for weather data

    def get_session_data(self) -> dict[str, Any]:
        """Get session data for persistence.
        
        Returns a dict containing tokens and session info that can be saved
        and later restored with restore_session_data() to avoid re-authentication.
        
        This allows the integration to run autonomously after initial TFA setup.
        """
        return {
            "token": self._token,
            "refresh_token": self._refresh_token,
            "token_expires": self._token_expires,
            "uuid": self._uuid,
            "cookies": self._cookies,
            "customer_number": self._customer_number,
            "contract": self._contract,
        }

    def restore_session_data(self, data: dict[str, Any]) -> bool:
        """Restore session data from persistence.
        
        Args:
            data: Session data dict from get_session_data()
            
        Returns:
            True if session was restored and appears valid, False otherwise.
        """
        if not data:
            return False
            
        self._token = data.get("token")
        self._refresh_token = data.get("refresh_token")
        self._token_expires = data.get("token_expires", 0)
        self._uuid = data.get("uuid")
        self._cookies = data.get("cookies", {})
        self._customer_number = data.get("customer_number")
        self._contract = data.get("contract")
        
        # Check if we have minimum required data
        if self._refresh_token and self._uuid:
            _LOGGER.info("Session data restored - will use refresh token for authentication")
            return True
        elif self._token and self._uuid:
            _LOGGER.info("Session data restored - will try existing token")
            return True
            
        return False

    def is_authenticated(self) -> bool:
        """Check if we have valid authentication data."""
        return bool(self._uuid and (self._token or self._refresh_token))

    def set_tfa_callback(self, code_callback: TfaCodeCallback, choice_callback: TfaChoiceCallback | None = None) -> None:
        """Set the callback functions for TFA.
        
        Args:
            code_callback: Function that takes no arguments and returns the TFA verification code.
            choice_callback: Function that takes a list of options (dicts with 'name' and 'id' keys)
                           and returns the index of the selected option. If not provided,
                           the first option will always be selected.
        
        Example:
            def get_code():
                return input("Enter TFA code: ")
            
            def choose_option(options):
                for i, opt in enumerate(options):
                    print(f"{i}: {opt['name']}")
                return int(input("Choose option: "))
            
            api.set_tfa_callback(get_code, choose_option)
        """
        self._tfa_code_callback = code_callback
        self._tfa_choice_callback = choice_callback

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._own_session = True
        return self._session

    async def close(self) -> None:
        """Close the session if we own it."""
        if self._own_session and self._session:
            await self._session.close()
            self._session = None

    async def authenticate(self, force_full_auth: bool = False) -> bool:
        """Authenticate with Dominion Energy and get auth data.
        
        This method will:
        1. First try to use existing refresh token (if available) - no TFA needed
        2. If that fails, perform full authentication with Selenium + TFA
        
        The device is registered as "trusted" so subsequent logins from the same
        device should not require TFA.
        
        Args:
            force_full_auth: If True, skip refresh token and do full auth with TFA
            
        Returns:
            True if successful, raises DominionEnergyAuthError on failure.
        """
        _LOGGER.info("Authenticating with Dominion Energy...")
        
        # Option 1: Try refresh token first (if we have one and not forcing full auth)
        if not force_full_auth and self._refresh_token and self._uuid:
            _LOGGER.info("Attempting authentication via refresh token...")
            if await self._refresh_access_token():
                _LOGGER.info("Successfully authenticated via refresh token (no TFA needed)")
                return True
            else:
                _LOGGER.warning("Refresh token failed, falling back to full authentication")
        
        # Option 2: Full authentication with Selenium (may require TFA on first login)
        _LOGGER.info("Performing full authentication...")
        
        # Run Selenium in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        auth_data = await loop.run_in_executor(
            _executor,
            self._selenium_login_with_tfa,
        )
        
        if auth_data:
            # If we have an id_token from Gigya, call Dominion Energy Login/auth API
            id_token = auth_data.get("id_token")
            if id_token:
                _LOGGER.info("Calling Dominion Energy Login/auth API...")
                dominion_auth = await self._dominion_login_auth(id_token)
                if dominion_auth:
                    self._uuid = dominion_auth.get("uuid")
                    self._cookies = auth_data.get("cookies", {})
                    # Store the access token for API calls
                    access_token = dominion_auth.get("access_token")
                    if access_token:
                        self._token = f"Bearer {access_token}"
                        _LOGGER.info("Stored bearer token for API calls")
                    # Store refresh token for token renewal
                    self._refresh_token = dominion_auth.get("refresh_token")
                    if self._refresh_token:
                        _LOGGER.info("Stored refresh token for future autonomous authentication")
                    # Token expires in 30 seconds - give 5 second buffer
                    self._token_expires = time.time() + 25
                    _LOGGER.info("Successfully authenticated with Dominion Energy")
                    return True
                else:
                    _LOGGER.warning("Dominion Energy Login/auth failed, falling back to Gigya UID")
            
            # Fallback to using Gigya UID directly
            self._uuid = auth_data.get("uuid")
            self._cookies = auth_data.get("cookies", {})
            _LOGGER.info("Successfully authenticated with Dominion Energy")
            return True
        
        raise DominionEnergyAuthError(
            "Failed to authenticate - could not capture auth data"
        )

    async def _dominion_login_auth(self, id_token: str) -> dict[str, Any] | None:
        """Call Dominion Energy Login/auth API with Gigya id_token."""
        import aiohttp
        import uuid
        
        login_auth_url = "https://prodsvc-dominioncip.smartcmobile.com/UsermanagementAPI/api/1/Login/auth"
        
        # Generate a correlation ID
        e2e_id = str(uuid.uuid4())
        
        headers = {
            "Authorization": f"Bearer {id_token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://myaccount.dominionenergy.com",
            "Referer": "https://myaccount.dominionenergy.com/",
            "e2eid": e2e_id,
            "st": "PL",
            "uid": "1",
            "pt": "",
            "cache-control": "no-cache",
            "pragma": "no-cache",
        }
        
        payload = {
            "username": "",
            "password": "",
            "guestToken": id_token,
            "customattributes": {
                "client": "",
                "version": "",
                "deviceId": "",
                "deviceName": "",
                "os": ""
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                _LOGGER.debug("Making Login/auth request...")
                async with session.post(login_auth_url, headers=headers, json=payload) as resp:
                    _LOGGER.debug("Dominion Login/auth status: %d", resp.status)
                    if resp.status == 200:
                        data = await resp.json()
                        _LOGGER.debug("Dominion Login/auth response: %s", data)
                        
                        # Check for success status
                        if data.get("status", {}).get("code") != 200:
                            _LOGGER.error("Login/auth returned error: %s", data.get("status", {}).get("message"))
                            return None
                        
                        # Extract data from the response
                        response_data = data.get("data", {})
                        user_info = response_data.get("user", {})
                        uuid_val = user_info.get("uuid")
                        access_token = response_data.get("accessToken")
                        refresh_token = response_data.get("refreshToken")
                        
                        if uuid_val:
                            _LOGGER.debug("Got Dominion Energy UUID: %s", uuid_val)
                            _LOGGER.debug("Got access token: %s...", access_token[:50] if access_token else "None")
                            return {
                                "uuid": uuid_val,
                                "access_token": access_token,
                                "refresh_token": refresh_token,
                                "user": user_info,
                                "data": data
                            }
                        
                        # Fall back to check userInteractionData format (older API?)
                        user_data = data.get("userInteractionData", [])
                        if user_data and len(user_data) > 0:
                            uuid_val = user_data[0].get("uuid")
                            if uuid_val:
                                _LOGGER.info("Got Dominion Energy UUID (legacy): %s", uuid_val)
                                return {"uuid": uuid_val, "data": data}
                    else:
                        _LOGGER.error("Dominion Login/auth returned status %d", resp.status)
                        text = await resp.text()
                        _LOGGER.error("Response: %s", text[:500])
        except Exception as e:
            _LOGGER.error("Dominion Login/auth failed: %s", e)
            import traceback
            traceback.print_exc()
        
        return None

    async def _refresh_access_token(self) -> bool:
        """Refresh the access token using the refresh token."""
        if not self._refresh_token:
            _LOGGER.warning("No refresh token available")
            return False
        
        refresh_url = "https://prodsvc-dominioncip.smartcmobile.com/UsermanagementAPI/api/1/login/auth/refresh"
        
        headers = {
            "Authorization": self._token,  # Current bearer token
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://myaccount.dominionenergy.com",
            "Referer": "https://myaccount.dominionenergy.com/",
            "uid": "1",
        }
        
        payload = {
            "refreshToken": self._refresh_token,
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                _LOGGER.info("Refreshing access token...")
                async with session.post(refresh_url, headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        _LOGGER.debug("Token refresh response: %s", data)
                        
                        # Check for success
                        if data.get("status", {}).get("code") == 200:
                            response_data = data.get("data", {})
                            new_access_token = response_data.get("accessToken")
                            new_refresh_token = response_data.get("refreshToken")
                            
                            if new_access_token:
                                self._token = f"Bearer {new_access_token}"
                                self._token_expires = time.time() + 25  # 30 second expiry with 5 sec buffer
                                _LOGGER.info("Access token refreshed successfully")
                                
                            if new_refresh_token:
                                self._refresh_token = new_refresh_token
                                
                            return True
                        else:
                            _LOGGER.error("Token refresh failed: %s", data.get("status", {}).get("message"))
                    else:
                        _LOGGER.error("Token refresh returned status %d", resp.status)
                        text = await resp.text()
                        _LOGGER.error("Response: %s", text[:500])
        except Exception as e:
            _LOGGER.error("Token refresh failed: %s", e)
        
        return False

    async def _ensure_token_valid(self) -> None:
        """Ensure the access token is valid, refreshing if needed."""
        if self._token_expires and time.time() > self._token_expires:
            _LOGGER.info("Access token expired, refreshing...")
            if not await self._refresh_access_token():
                _LOGGER.warning("Token refresh failed")

    def _selenium_login_with_tfa(self) -> dict[str, Any] | None:
        """Synchronously perform login with TFA using Selenium.
        
        This runs in a separate thread to not block the event loop.
        """
        from seleniumwire import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.common.exceptions import TimeoutException, NoSuchElementException
        from seleniumwire.utils import decode
        
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            use_webdriver_manager = True
        except ImportError:
            use_webdriver_manager = False

        # Suppress noisy loggers
        logging.getLogger("seleniumwire").setLevel(logging.WARNING)
        logging.getLogger("hpack").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("selenium").setLevel(logging.WARNING)
        logging.getLogger("WDM").setLevel(logging.WARNING)

        _LOGGER.info("Starting Selenium authentication for user: %s", self._username)

        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        driver = None
        try:
            if use_webdriver_manager:
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=options)
            else:
                driver = webdriver.Chrome(options=options)

            # Set webdriver flags to avoid detection
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                '''
            })

            # Navigate to login page
            login_url = f"{LOGIN_URL}?SelectedAppName=Electric"
            _LOGGER.debug("Navigating to: %s", login_url)
            driver.get(login_url)

            wait = WebDriverWait(driver, 30)
            
            _LOGGER.debug("Page title: %s", driver.title)

            # Wait for email field and enter credentials
            _LOGGER.info("Waiting for login form...")
            email_field = wait.until(
                EC.presence_of_element_located((By.XPATH, "//input[contains(@placeholder, 'Email')]"))
            )
            email_field.send_keys(self._username)
            _LOGGER.info("Email entered")

            # Wait for password field
            password_field = wait.until(
                EC.presence_of_element_located((By.XPATH, "//input[contains(@placeholder, 'Password')]"))
            )
            password_field.send_keys(self._password)
            _LOGGER.info("Password entered")

            # Find and click submit button
            submit_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//input[@type='submit' and @value='Submit']"))
            )
            submit_button.click()
            _LOGGER.info("Submit button clicked, waiting for response...")

            # Wait for either TFA screen or successful login
            time.sleep(3)
            
            # Check if TFA is required by looking for TFA-related elements
            tfa_required = self._check_for_tfa(driver)
            
            if tfa_required:
                _LOGGER.info("TFA verification required")
                if not self._tfa_code_callback:
                    raise DominionEnergyAuthError(
                        "TFA is required but no TFA callback is set. "
                        "Use set_tfa_callback() to provide a function that returns the TFA code."
                    )
                
                # Handle the TFA flow using Gigya API - returns auth data directly
                auth_data = self._handle_tfa_via_api(driver)
                if auth_data:
                    _LOGGER.info("TFA authentication successful!")
                    return auth_data
                else:
                    raise DominionEnergyAuthError("TFA verification failed")
            
            # No TFA required - wait for authentication to complete
            _LOGGER.info("Waiting for authentication to complete...")
            time.sleep(5)

            # Extract auth data from intercepted requests
            auth_data = self._extract_auth_data(driver)
            
            if auth_data:
                return auth_data
            
            _LOGGER.error("No auth data found after authentication")
            return None

        except Exception as err:
            _LOGGER.error("Selenium authentication failed: %s", err)
            raise DominionEnergyAuthError(f"Authentication failed: {err}")
        finally:
            if driver:
                driver.quit()

    def _check_for_tfa(self, driver) -> bool:
        """Check if TFA verification screen is displayed."""
        from selenium.webdriver.common.by import By
        from selenium.common.exceptions import NoSuchElementException
        from seleniumwire.utils import decode
        
        # First check if we got a 403101 error code (TFA required) in the API responses
        for request in driver.requests:
            if not request.response:
                continue
            if 'accounts.login' in request.url:
                try:
                    body = decode(request.response.body, request.response.headers.get('Content-Encoding', 'identity'))
                    data = json.loads(body.decode('utf-8'))
                    error_code = data.get('errorCode', 0)
                    if error_code == 403101:
                        _LOGGER.info("TFA required (error code 403101)")
                        return True
                except Exception as e:
                    _LOGGER.debug("Error checking login response: %s", e)
        
        try:
            # Look for TFA-related elements
            # Check for phone verification option
            phone_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'Text Message')]")
            if phone_elements:
                return True
            
            # Check for verification code input
            code_inputs = driver.find_elements(By.XPATH, "//input[contains(@placeholder, 'Code') or contains(@name, 'code')]")
            if code_inputs:
                return True
            
            # Check for "Send Code" or "Verify" buttons
            send_code_buttons = driver.find_elements(By.XPATH, "//*[contains(text(), 'Send Code') or contains(text(), 'Send code')]")
            if send_code_buttons:
                return True
                
            return False
        except Exception:
            return False

    def _handle_tfa_via_api(self, driver) -> dict[str, Any] | None:
        """Handle the TFA verification flow using direct Gigya API calls.
        
        This method:
        1. Extracts cookies (especially gmid) from the browser
        2. Uses those cookies to make direct API calls for TFA
        3. Presents options to the user for provider and phone selection
        4. Returns the final auth data (UID, cookies) or None on failure
        """
        import requests
        from seleniumwire.utils import decode
        
        GIGYA_API_KEY = "4_6zEg-HY_0eqpgdSONYkJkQ"
        GIGYA_AUTH_URL = "https://auth.dominionenergy.com"
        
        # Step 1: Get regToken from the login response
        reg_token = None
        login_requests_found = 0
        for request in driver.requests:
            if not request.response:
                continue
            if 'accounts.login' in request.url:
                login_requests_found += 1
                try:
                    body = decode(request.response.body, request.response.headers.get('Content-Encoding', 'identity'))
                    data = json.loads(body.decode('utf-8'))
                    reg_token = data.get('regToken')
                    if reg_token:
                        _LOGGER.info("Found regToken from login response")
                        break
                    else:
                        # Log the full response to understand the structure
                        _LOGGER.info("accounts.login response has no regToken, errorCode: %s, errorMessage: %s", 
                                    data.get('errorCode'), data.get('errorMessage'))
                        _LOGGER.debug("Full login response keys: %s", list(data.keys()))
                except Exception as e:
                    _LOGGER.debug("Error parsing login response: %s", e)
        
        if not reg_token:
            _LOGGER.error("Could not find regToken for TFA (found %d accounts.login requests)", login_requests_found)
            # Log all intercepted request URLs for debugging
            _LOGGER.debug("Intercepted requests: %s", [r.url for r in driver.requests if r.response][:20])
            return None
        
        # Step 2: Extract cookies - need to get gmid from the accounts.login request
        # The gmid cookie is set on auth.dominionenergy.com domain, so we need to
        # extract it from the intercepted request headers
        browser_cookies = {}
        
        # First get cookies from the browser (for login.dominionenergy.com domain)
        for cookie in driver.get_cookies():
            browser_cookies[cookie['name']] = cookie['value']
        
        _LOGGER.info("Extracted %d cookies from browser domain", len(browser_cookies))
        
        # Now extract cookies from the intercepted accounts.login request
        # These cookies were sent to auth.dominionenergy.com
        for request in driver.requests:
            if 'accounts.login' in request.url and request.headers:
                cookie_header = request.headers.get('Cookie', '')
                if cookie_header:
                    _LOGGER.info("Found Cookie header in accounts.login request")
                    # Parse the cookie header
                    for cookie_pair in cookie_header.split('; '):
                        if '=' in cookie_pair:
                            name, value = cookie_pair.split('=', 1)
                            browser_cookies[name] = value
                    break
        
        _LOGGER.info("Total cookies after extraction: %d", len(browser_cookies))
        
        # Check for required cookies
        gmid = browser_cookies.get('gmid')
        if gmid:
            _LOGGER.info("Found gmid cookie: %s...", gmid[:30])
        else:
            _LOGGER.warning("gmid cookie not found - TFA API calls may fail")
        
        # Build cookie string for requests
        cookie_str = "; ".join([f"{k}={v}" for k, v in browser_cookies.items()])
        
        # Common parameters
        common_params = {
            "APIKey": GIGYA_API_KEY,
            "sdk": "js_next",
            "pageURL": "https://login.dominionenergy.com/CommonLogin?SelectedAppName=Electric",
            "sdkBuild": "18148",
            "format": "json",
        }
        
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
            "Origin": "https://login.dominionenergy.com",
            "Referer": "https://login.dominionenergy.com/",
            "Cookie": cookie_str,
        })
        
        try:
            # Step 3: Get available TFA providers
            _LOGGER.info("Getting TFA providers...")
            providers_resp = session.get(
                f"{GIGYA_AUTH_URL}/accounts.tfa.getProviders",
                params={**common_params, "regToken": reg_token}
            )
            providers_data = providers_resp.json()
            _LOGGER.debug("TFA providers response: %s", providers_data)
            
            if providers_data.get('errorCode', 0) != 0:
                _LOGGER.error("Failed to get TFA providers: %s", providers_data.get('errorMessage'))
                return None
            
            active_providers = providers_data.get('activeProviders', [])
            _LOGGER.info("Available TFA providers: %s", active_providers)
            
            if not active_providers:
                _LOGGER.error("No TFA providers available")
                return None
            
            # Normalize provider format - can be strings or dicts with 'name' key
            provider_names = []
            for p in active_providers:
                if isinstance(p, dict):
                    provider_names.append(p.get('name', str(p)))
                else:
                    provider_names.append(str(p))
            
            _LOGGER.info("Normalized provider names: %s", provider_names)
            
            # Step 4: Let user choose provider
            provider_display_names = {
                'gigyaPhone': 'Phone/SMS (Text Message)',
                'gigyaEmail': 'Email',
            }
            provider_options = [{"name": provider_display_names.get(p, p), "id": p} for p in provider_names]
            
            if len(provider_names) > 1 and self._tfa_choice_callback:
                _LOGGER.info("Multiple TFA providers available, asking user to choose...")
                chosen_idx = self._tfa_choice_callback(provider_options)
                chosen_provider = provider_names[chosen_idx]
            else:
                # Default to gigyaPhone if available, otherwise first option
                if 'gigyaPhone' in provider_names:
                    chosen_provider = 'gigyaPhone'
                else:
                    chosen_provider = provider_names[0]
            
            _LOGGER.info("Using TFA provider: %s", chosen_provider)
            
            # Step 5: Initialize TFA with chosen provider
            _LOGGER.info("Initializing TFA with provider: %s", chosen_provider)
            init_resp = session.get(
                f"{GIGYA_AUTH_URL}/accounts.tfa.initTFA",
                params={**common_params, "provider": chosen_provider, "mode": "verify", "regToken": reg_token}
            )
            init_data = init_resp.json()
            _LOGGER.debug("TFA init response: %s", init_data)
            
            if init_data.get('errorCode', 0) != 0:
                _LOGGER.error("Failed to init TFA: %s (code: %s)", init_data.get('errorMessage'), init_data.get('errorCode'))
                return None
            
            gigya_assertion = init_data.get('gigyaAssertion')
            if not gigya_assertion:
                _LOGGER.error("No gigyaAssertion in TFA init response")
                return None
            
            # Handle based on provider type
            if chosen_provider == 'gigyaPhone':
                success = self._handle_phone_tfa(session, gigya_assertion, reg_token, common_params, GIGYA_AUTH_URL)
            elif chosen_provider == 'gigyaEmail':
                success = self._handle_email_tfa(session, gigya_assertion, reg_token, common_params, GIGYA_AUTH_URL)
            else:
                _LOGGER.error("Unsupported TFA provider: %s", chosen_provider)
                return None
            
            if not success:
                return None
            
            _LOGGER.info("TFA verification complete! Finalizing registration...")
            
            # Step 6: Finalize registration to get UID
            finalize_resp = session.get(
                f"{GIGYA_AUTH_URL}/accounts.finalizeRegistration",
                params={
                    **common_params,
                    "regToken": reg_token,
                    "include": "profile,data,emails,subscriptions,preferences,id_token,groups,loginIDs,",
                    "includeUserInfo": "true",
                }
            )
            finalize_data = finalize_resp.json()
            _LOGGER.debug("Finalize registration response keys: %s", list(finalize_data.keys()))
            
            if finalize_data.get('errorCode', 0) != 0:
                _LOGGER.error("Failed to finalize registration: %s", finalize_data.get('errorMessage'))
                return None
            
            uid = finalize_data.get('UID')
            if not uid:
                _LOGGER.error("No UID in finalize response")
                return None
            
            _LOGGER.debug("Got UID: %s", uid[:30] if len(uid) > 30 else uid)
            
            # Return the auth data
            return {
                "uuid": uid,
                "cookies": browser_cookies,
                "id_token": finalize_data.get("id_token"),
            }
            
        except Exception as e:
            _LOGGER.error("TFA API flow failed: %s", e)
            import traceback
            traceback.print_exc()
            return None

    def _handle_phone_tfa(self, session, gigya_assertion: str, reg_token: str, common_params: dict, auth_url: str) -> bool:
        """Handle phone-based TFA."""
        try:
            # Get registered phone numbers
            _LOGGER.info("Getting registered phone numbers...")
            phones_resp = session.get(
                f"{auth_url}/accounts.tfa.phone.getRegisteredPhoneNumbers",
                params={**common_params, "gigyaAssertion": gigya_assertion}
            )
            phones_data = phones_resp.json()
            _LOGGER.debug("Phones response: %s", phones_data)
            
            if phones_data.get('errorCode', 0) != 0:
                _LOGGER.error("Failed to get phone numbers: %s", phones_data.get('errorMessage'))
                return False
            
            phones = phones_data.get('phones', [])
            if not phones:
                _LOGGER.error("No registered phone numbers found")
                return False
            
            _LOGGER.info("Found %d registered phone number(s)", len(phones))
            
            # Let user choose phone if multiple exist
            phone_options = [{"name": p.get('obfuscated', p.get('id', 'Unknown')), "id": p.get('id')} for p in phones]
            if len(phones) > 1 and self._tfa_choice_callback:
                _LOGGER.info("Multiple phone numbers available, asking user to choose...")
                chosen_idx = self._tfa_choice_callback(phone_options)
                chosen_phone = phones[chosen_idx]
            else:
                chosen_phone = phones[0]
            
            phone_id = chosen_phone.get('id')
            _LOGGER.info("Using phone: %s (ID: %s)", chosen_phone.get('obfuscated', '***'), phone_id)
            
            # Need to re-init TFA to get fresh assertion for sending code
            _LOGGER.info("Re-initializing TFA for code sending...")
            init_resp = session.get(
                f"{auth_url}/accounts.tfa.initTFA",
                params={**common_params, "provider": "gigyaPhone", "mode": "verify", "regToken": reg_token}
            )
            init_data = init_resp.json()
            if init_data.get('errorCode', 0) != 0:
                _LOGGER.error("Failed to re-init TFA: %s", init_data.get('errorMessage'))
                return False
            gigya_assertion = init_data.get('gigyaAssertion')
            
            # Send verification code
            _LOGGER.info("Sending verification code via SMS...")
            send_resp = session.get(
                f"{auth_url}/accounts.tfa.phone.sendVerificationCode",
                params={
                    **common_params,
                    "gigyaAssertion": gigya_assertion,
                    "lang": "en",
                    "phoneID": phone_id,
                    "method": "sms",
                    "regToken": reg_token,
                }
            )
            send_data = send_resp.json()
            _LOGGER.debug("Send code response: %s", send_data)
            
            if send_data.get('errorCode', 0) != 0:
                _LOGGER.error("Failed to send verification code: %s", send_data.get('errorMessage'))
                return False
            
            # Get the new assertion and phvToken from send response
            phone_assertion = send_data.get('gigyaAssertion')
            if not phone_assertion:
                phone_assertion = gigya_assertion
            
            phv_token = send_data.get('phvToken')
            _LOGGER.info("Got phvToken: %s", phv_token[:20] if phv_token else "None")
            
            _LOGGER.info("Verification code sent! Waiting for user input...")
            
            # Get code from user
            tfa_code = self._tfa_code_callback()
            if not tfa_code:
                _LOGGER.error("No TFA code provided")
                return False
            
            _LOGGER.info("Completing phone verification...")
            
            # Complete verification - requires phvToken from sendVerificationCode response
            complete_params = {
                **common_params,
                "gigyaAssertion": phone_assertion,
                "code": tfa_code,
                "regToken": reg_token,
            }
            if phv_token:
                complete_params["phvToken"] = phv_token
            
            complete_resp = session.get(
                f"{auth_url}/accounts.tfa.phone.completeVerification",
                params=complete_params
            )
            complete_data = complete_resp.json()
            _LOGGER.info("Complete verification response: %s", json.dumps(complete_data, indent=2))
            
            if complete_data.get('errorCode', 0) != 0:
                _LOGGER.error("Verification failed: %s", complete_data.get('errorMessage'))
                return False
            
            # Get the provider assertion for finalization
            provider_assertion = complete_data.get('providerAssertion')
            _LOGGER.info("Provider assertion: %s", provider_assertion[:50] if provider_assertion else "None")
            if not provider_assertion:
                _LOGGER.error("No provider assertion in completion response")
                return False
            
            # Finalize TFA - use gigyaAssertion instead of providerAssertion based on Gigya API docs
            # tempDevice=false registers this device as trusted, so future logins won't require TFA
            _LOGGER.info("Finalizing TFA and registering device as trusted...")
            finalize_params = {
                **common_params,
                "gigyaAssertion": gigya_assertion,
                "providerAssertion": provider_assertion,
                "regToken": reg_token,
                "tempDevice": "false",
            }
            _LOGGER.info("Finalize params: %s", {k: v[:30] + '...' if isinstance(v, str) and len(v) > 30 else v for k, v in finalize_params.items()})
            
            finalize_resp = session.get(
                f"{auth_url}/accounts.tfa.finalizeTFA",
                params=finalize_params
            )
            finalize_data = finalize_resp.json()
            _LOGGER.info("Finalize TFA response: %s", json.dumps(finalize_data, indent=2))
            
            if finalize_data.get('errorCode', 0) != 0:
                _LOGGER.error("Failed to finalize TFA: %s", finalize_data.get('errorMessage'))
                return False
            
            _LOGGER.info("Phone TFA completed successfully")
            return True
            
        except Exception as e:
            _LOGGER.error("Phone TFA failed: %s", e)
            import traceback
            traceback.print_exc()
            return False

    def _handle_email_tfa(self, session, gigya_assertion: str, reg_token: str, common_params: dict, auth_url: str) -> bool:
        """Handle email-based TFA."""
        try:
            # Get registered emails
            _LOGGER.info("Getting registered email addresses...")
            emails_resp = session.get(
                f"{auth_url}/accounts.tfa.email.getEmails",
                params={**common_params, "gigyaAssertion": gigya_assertion}
            )
            emails_data = emails_resp.json()
            _LOGGER.debug("Emails response: %s", emails_data)
            
            if emails_data.get('errorCode', 0) != 0:
                _LOGGER.error("Failed to get emails: %s", emails_data.get('errorMessage'))
                return False
            
            emails = emails_data.get('emails', [])
            if not emails:
                _LOGGER.error("No registered email addresses found")
                return False
            
            _LOGGER.info("Found %d registered email(s)", len(emails))
            
            # Let user choose email if multiple exist
            email_options = [{"name": e.get('obfuscated', e.get('id', 'Unknown')), "id": e.get('id')} for e in emails]
            if len(emails) > 1 and self._tfa_choice_callback:
                _LOGGER.info("Multiple emails available, asking user to choose...")
                chosen_idx = self._tfa_choice_callback(email_options)
                chosen_email = emails[chosen_idx]
            else:
                chosen_email = emails[0]
            
            email_id = chosen_email.get('id')
            _LOGGER.info("Using email: %s (ID: %s)", chosen_email.get('obfuscated', '***'), email_id)
            
            # Need to re-init TFA to get fresh assertion for sending code
            _LOGGER.info("Re-initializing TFA for code sending...")
            init_resp = session.get(
                f"{auth_url}/accounts.tfa.initTFA",
                params={**common_params, "provider": "gigyaEmail", "mode": "verify", "regToken": reg_token}
            )
            init_data = init_resp.json()
            if init_data.get('errorCode', 0) != 0:
                _LOGGER.error("Failed to re-init TFA: %s", init_data.get('errorMessage'))
                return False
            gigya_assertion = init_data.get('gigyaAssertion')
            
            # Send verification code
            _LOGGER.info("Sending verification code via email...")
            send_resp = session.get(
                f"{auth_url}/accounts.tfa.email.sendVerificationCode",
                params={
                    **common_params,
                    "gigyaAssertion": gigya_assertion,
                    "lang": "en",
                    "emailID": email_id,
                    "regToken": reg_token,
                }
            )
            send_data = send_resp.json()
            _LOGGER.debug("Send code response: %s", send_data)
            
            if send_data.get('errorCode', 0) != 0:
                _LOGGER.error("Failed to send verification code: %s", send_data.get('errorMessage'))
                return False
            
            # Get the new assertion and phvToken from send response
            email_assertion = send_data.get('gigyaAssertion')
            if not email_assertion:
                email_assertion = gigya_assertion
            
            phv_token = send_data.get('phvToken')
            _LOGGER.info("Got phvToken: %s", phv_token[:20] if phv_token else "None")
            
            _LOGGER.info("Verification code sent! Waiting for user input...")
            
            # Get code from user
            tfa_code = self._tfa_code_callback()
            if not tfa_code:
                _LOGGER.error("No TFA code provided")
                return False
            
            _LOGGER.info("Completing email verification...")
            
            # Complete verification - requires phvToken from sendVerificationCode response
            complete_params = {
                **common_params,
                "gigyaAssertion": email_assertion,
                "code": tfa_code,
                "regToken": reg_token,
            }
            if phv_token:
                complete_params["phvToken"] = phv_token
            
            complete_resp = session.get(
                f"{auth_url}/accounts.tfa.email.completeVerification",
                params=complete_params
            )
            complete_data = complete_resp.json()
            _LOGGER.debug("Complete verification response: %s", complete_data)
            
            if complete_data.get('errorCode', 0) != 0:
                _LOGGER.error("Verification failed: %s", complete_data.get('errorMessage'))
                return False
            
            # Get the provider assertion for finalization
            provider_assertion = complete_data.get('providerAssertion')
            if not provider_assertion:
                _LOGGER.error("No provider assertion in completion response")
                return False
            
            # Finalize TFA
            # tempDevice=false registers this device as trusted, so future logins won't require TFA
            _LOGGER.info("Finalizing TFA and registering device as trusted...")
            finalize_resp = session.get(
                f"{auth_url}/accounts.tfa.finalizeTFA",
                params={
                    **common_params,
                    "providerAssertion": provider_assertion,
                    "regToken": reg_token,
                    "tempDevice": "false",
                }
            )
            finalize_data = finalize_resp.json()
            _LOGGER.debug("Finalize TFA response: %s", finalize_data)
            
            if finalize_data.get('errorCode', 0) != 0:
                _LOGGER.error("Failed to finalize TFA: %s", finalize_data.get('errorMessage'))
                return False
            
            _LOGGER.info("Email TFA completed successfully")
            return True
            
        except Exception as e:
            _LOGGER.error("Email TFA failed: %s", e)
            import traceback
            traceback.print_exc()
            return False

    def _handle_selenium_tfa(self, driver, wait) -> bool:
        """Handle the TFA verification flow in Selenium (legacy method)."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException
        
        try:
            # First, try to click on the phone/SMS option if multiple options are available
            try:
                phone_option = wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Text Message') or contains(text(), 'SMS') or contains(text(), 'Phone')]"))
                )
                phone_option.click()
                _LOGGER.info("Selected phone/SMS verification option")
                time.sleep(1)
            except TimeoutException:
                _LOGGER.debug("No phone option selector found, might already be on phone verification")
            
            # Try to find and click "Send Code" button
            try:
                send_code_button = driver.find_element(By.XPATH, "//input[@value='Send Code'] | //button[contains(text(), 'Send Code')] | //*[contains(text(), 'Send code')]")
                send_code_button.click()
                _LOGGER.info("Clicked Send Code button")
                time.sleep(2)
            except NoSuchElementException:
                _LOGGER.debug("No Send Code button found, code might be sent automatically")
            
            # Get the TFA code from the callback
            _LOGGER.info("Requesting TFA code from callback...")
            tfa_code = self._tfa_code_callback()
            
            if not tfa_code:
                _LOGGER.error("No TFA code provided")
                return False
            
            _LOGGER.info("Received TFA code, entering verification code...")
            
            # Find the code input field and enter the code
            code_input = wait.until(
                EC.presence_of_element_located((
                    By.XPATH, 
                    "//input[contains(@placeholder, 'Code') or contains(@placeholder, 'code') or contains(@name, 'code') or contains(@id, 'code') or @type='tel']"
                ))
            )
            code_input.clear()
            code_input.send_keys(tfa_code)
            _LOGGER.info("TFA code entered")
            
            # Find and click the verify/submit button
            time.sleep(1)
            try:
                verify_button = driver.find_element(By.XPATH, 
                    "//input[@type='submit'] | //button[contains(text(), 'Verify')] | //button[contains(text(), 'Submit')] | //input[@value='Verify']"
                )
                verify_button.click()
                _LOGGER.info("Clicked verify button")
            except NoSuchElementException:
                # Try pressing Enter
                code_input.send_keys("\n")
                _LOGGER.info("Pressed Enter to submit")
            
            # Wait for verification to complete
            time.sleep(5)
            
            # Check if we're now logged in (no more TFA elements)
            if not self._check_for_tfa(driver):
                _LOGGER.info("TFA verification successful")
                return True
            
            _LOGGER.warning("TFA elements still present after verification")
            return False
            
        except Exception as err:
            _LOGGER.error("TFA handling failed: %s", err)
            return False

    def _extract_auth_data(self, driver) -> dict[str, Any] | None:
        """Extract authentication data from Selenium driver."""
        from seleniumwire.utils import decode
        
        uuid = None
        cookies = {}
        
        # Search for auth data in API requests
        login_auth_url = "/UsermanagementAPI/api/1/Login/auth"
        finalize_url = "accounts.finalizeRegistration"
        
        _LOGGER.info("Scanning %d captured requests...", len(driver.requests))
        
        for request in driver.requests:
            if not request.response:
                continue
                
            # Look for Login/auth response
            if login_auth_url in request.url:
                try:
                    body = decode(request.response.body, request.response.headers.get('Content-Encoding', 'identity'))
                    data = json.loads(body.decode('utf-8'))
                    
                    if "userInteractionData" in data and len(data["userInteractionData"]) > 0:
                        uuid = data["userInteractionData"][0].get("uuid")
                        if uuid:
                            _LOGGER.info("Found UUID from Login/auth response")
                except Exception as e:
                    _LOGGER.debug("Error parsing Login/auth response: %s", e)
            
            # Look for finalize registration response (contains UID after TFA)
            if finalize_url in request.url:
                try:
                    body = decode(request.response.body, request.response.headers.get('Content-Encoding', 'identity'))
                    data = json.loads(body.decode('utf-8'))
                    
                    if "UID" in data:
                        uuid = data.get("UID")
                        _LOGGER.info("Found UID from finalizeRegistration response")
                except Exception as e:
                    _LOGGER.debug("Error parsing finalizeRegistration response: %s", e)
        
        # Get cookies from driver
        for cookie in driver.get_cookies():
            cookies[cookie['name']] = cookie['value']
        
        _LOGGER.info("Captured %d cookies", len(cookies))
        
        if uuid:
            return {
                "uuid": uuid,
                "cookies": cookies
            }
        
        # If no UUID found in requests, try to get it from cookies or page
        _LOGGER.warning("UUID not found in intercepted requests")
        return None

    def set_token(self, token: str) -> None:
        """Set the bearer token directly (for long-lived tokens)."""
        if not token.startswith("Bearer "):
            token = f"Bearer {token}"
        self._token = token

    def _get_headers(self) -> dict[str, str]:
        """Get headers for API requests."""
        headers = DEFAULT_HEADERS.copy()
        # Add Referer which is required for the API
        headers["Referer"] = "https://myaccount.dominionenergy.com/"
        # Note: Don't include uuid as a header - it's not used in API calls
        if self._token:
            headers["Authorization"] = self._token
        return headers

    async def _api_request(
        self, endpoint: str, params: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Make an API request."""
        if not self._uuid and not self._token:
            raise DominionEnergyApiError("Not authenticated - call authenticate() first")

        # Ensure token is valid before making request
        await self._ensure_token_valid()

        session = await self._get_session()
        url = f"{API_BASE_URL}{endpoint}"
        
        default_params = {
            "accountNumber": self._account_number,
            "actionCode": ACTION_CODE,
        }
        if params:
            default_params.update(params)

        headers = self._get_headers()
        _LOGGER.debug("Making API request to: %s", url)
        _LOGGER.debug("Request params: %s", default_params)
        
        try:
            async with session.get(
                url, headers=headers, params=default_params, cookies=self._cookies
            ) as response:
                _LOGGER.debug("Response status: %d", response.status)
                if response.status == 401:
                    _LOGGER.warning("401 Unauthorized - attempting token refresh")
                    if await self._refresh_access_token():
                        # Retry with new token
                        headers = self._get_headers()
                        async with session.get(
                            url, headers=headers, params=default_params, cookies=self._cookies
                        ) as retry_response:
                            if retry_response.status == 401:
                                raise DominionEnergyAuthError("Token expired or invalid")
                            if retry_response.status != 200:
                                raise DominionEnergyApiError(
                                    f"API request failed with status {retry_response.status}"
                                )
                            return await retry_response.json()
                    raise DominionEnergyAuthError("Token expired or invalid")
                if response.status != 200:
                    raise DominionEnergyApiError(
                        f"API request failed with status {response.status}"
                    )
                
                data = await response.json()
                
                # Check for API-level errors
                status = data.get("status", {})
                status_code = status.get("code")
                if status_code and int(status_code) != 200:
                    raise DominionEnergyApiError(
                        f"API error: {status.get('message', 'Unknown error')}"
                    )
                
                return data

        except aiohttp.ClientError as err:
            raise DominionEnergyApiError(f"Network error: {err}")

    async def get_bill_forecast(self) -> dict[str, Any]:
        """Get bill forecast data including current usage."""
        return await self._api_request(BILL_FORECAST_ENDPOINT)

    async def get_usage_history(
        self, start_date: str | None = None, end_date: str | None = None
    ) -> dict[str, Any]:
        """Get usage history data.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
        """
        params = {}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        return await self._api_request(USAGE_HISTORY_ENDPOINT, params)

    async def get_bill_history(self) -> dict[str, Any]:
        """Get billing history data."""
        return await self._api_request(BILL_HISTORY_ENDPOINT)

    async def get_customer_number(self) -> str | None:
        """Get customer number (business partner number) from UUID.
        
        This calls the GetBpNumber endpoint to retrieve the customer number
        which is needed for the GetBusinessMaster call.
        
        Returns:
            Customer number string, or None if not found.
        """
        if not self._uuid:
            _LOGGER.warning("Cannot get customer number without UUID")
            return None
        
        # Return cached value if available
        if self._customer_number:
            return self._customer_number
        
        await self._ensure_token_valid()
        
        url = f"{API_BASE_URL}{GET_BP_NUMBER_ENDPOINT}"
        params = {"Uuid": self._uuid}
        
        headers = {
            **DEFAULT_HEADERS,
            "Authorization": self._token,
            "Referer": "https://myaccount.dominionenergy.com/",
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as resp:
                    data = await resp.json()
                    _LOGGER.debug("GetBpNumber response: %s", data)
                    
                    if data.get("status", {}).get("code") == 200:
                        customer_number = data.get("data", {}).get("customerNumber")
                        if customer_number:
                            self._customer_number = customer_number
                            _LOGGER.info("Retrieved customer number: %s", customer_number)
                            return customer_number
                    
                    _LOGGER.warning("Failed to get customer number: %s", data)
                    return None
                    
        except aiohttp.ClientError as err:
            _LOGGER.error("Network error getting customer number: %s", err)
            return None

    async def get_business_master(self) -> dict[str, Any] | None:
        """Get business master data including contract numbers.
        
        This calls the GetBusinessMaster endpoint to retrieve account details
        including the contract number needed for weather data.
        
        Returns:
            Business master data dict, or None if not found.
        """
        if not self._uuid:
            _LOGGER.warning("Cannot get business master without UUID")
            return None
        
        # Ensure we have customer number
        customer_number = await self.get_customer_number()
        if not customer_number:
            _LOGGER.warning("Cannot get business master without customer number")
            return None
        
        await self._ensure_token_valid()
        
        url = f"{API_BASE_URL}{GET_BUSINESS_MASTER_ENDPOINT}"
        params = {
            "customerNumber": customer_number,
            "uuid": self._uuid,
        }
        
        headers = {
            **DEFAULT_HEADERS,
            "Authorization": self._token,
            "Referer": "https://myaccount.dominionenergy.com/",
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as resp:
                    data = await resp.json()
                    _LOGGER.debug("GetBusinessMaster response status: %s", resp.status)
                    
                    if data.get("status", {}).get("code") == 200:
                        return data
                    
                    _LOGGER.warning("Failed to get business master: %s", data.get("status"))
                    return None
                    
        except aiohttp.ClientError as err:
            _LOGGER.error("Network error getting business master: %s", err)
            return None

    async def get_contract_number(self) -> str | None:
        """Get the contract number for the account.
        
        This extracts the contract number from the BusinessMaster data,
        which is needed for weather data API calls.
        
        Returns:
            Contract number string, or None if not found.
        """
        # Return cached value if available
        if self._contract:
            return self._contract
        
        business_master = await self.get_business_master()
        if not business_master:
            return None
        
        try:
            # Navigate to the contract in the response
            # data[0].zbpMaintRegEnroll_nav.results[0].conDev[0].contract
            accounts = business_master.get("data", [])
            if accounts and isinstance(accounts, list) and len(accounts) > 0:
                account = accounts[0]
                nav = account.get("zbpMaintRegEnroll_nav", {})
                results = nav.get("results", [])
                
                # Find the matching account
                for result in results:
                    if result.get("account") == self._account_number:
                        con_devs = result.get("conDev", [])
                        if con_devs and isinstance(con_devs, list) and len(con_devs) > 0:
                            contract = con_devs[0].get("contract")
                            if contract:
                                self._contract = contract
                                _LOGGER.info("Retrieved contract number: %s", contract)
                                return contract
                
                # If no exact account match, use the first result
                if results:
                    con_devs = results[0].get("conDev", [])
                    if con_devs and isinstance(con_devs, list) and len(con_devs) > 0:
                        contract = con_devs[0].get("contract")
                        if contract:
                            self._contract = contract
                            _LOGGER.info("Retrieved contract number (first result): %s", contract)
                            return contract
                            
        except (KeyError, IndexError, TypeError) as e:
            _LOGGER.debug("Error extracting contract number: %s", e)
        
        _LOGGER.warning("Could not find contract number in business master data")
        return None

    async def get_meter_info(self) -> dict[str, Any]:
        """Get meter information including meter number.
        
        Returns meter data including:
        - accountNumber
        - meterNumber (padded to 18 digits)
        - amiMeter (boolean - if it's a smart meter)
        """
        url = f"{ACCOUNT_MGMT_API_BASE_URL}{METERS_ENDPOINT}/{self._account_number}"
        
        await self._ensure_token_valid()
        
        headers = {
            **DEFAULT_HEADERS,
            "Authorization": self._token,
            "accountnumber": f"*****{self._account_number[-7:]}",
            "Referer": "https://myaccount.dominionenergy.com/",
        }
        
        if hasattr(self, "_customer_number") and self._customer_number:
            headers["customernumber"] = f"*****{self._customer_number[-5:]}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    data = await resp.json()
                    _LOGGER.debug("Meter info response: %s", data)
                    return data
        except aiohttp.ClientError as err:
            raise DominionEnergyApiError(f"Network error: {err}")

    async def get_electric_usage(
        self,
        meter_number: str,
        from_date: str | None = None,
        to_date: str | None = None,
        uom: str = "kWh",
        periodicity: str = "MO",
    ) -> dict[str, Any]:
        """Get electric usage data from the Usageapi.
        
        Args:
            meter_number: The meter number (18 digits with leading zeros)
            from_date: Start date in YYYY-MM-DD format (defaults to 13 months ago)
            to_date: End date in YYYY-MM-DD format (defaults to next month)
            uom: Unit of measure - 'kWh' for consumption, 'ALT' for alternative (solar return)
            periodicity: 'MO' for monthly, 'DA' for daily
            
        Returns:
            Electric usage data with monthly consumption and billing amounts
        """
        from datetime import datetime, timedelta
        
        # Default date range: 13 months back to next month
        if not from_date:
            from_date = (datetime.now() - timedelta(days=395)).strftime("%Y-%m-%d")
        if not to_date:
            to_date = (datetime.now() + timedelta(days=32)).strftime("%Y-%m-%d")
        
        # Pad meter number to 18 digits
        padded_meter = meter_number.zfill(18)
        
        url = f"{USAGE_API_BASE_URL}{ELECTRIC_USAGE_ENDPOINT}"
        params = {
            "AccountNumber": self._account_number,
            "MeterNumber": padded_meter,
            "From": from_date,
            "To": to_date,
            "Uom": uom,
            "Periodicity": periodicity,
        }
        
        await self._ensure_token_valid()
        
        headers = {
            **DEFAULT_HEADERS,
            "Authorization": self._token,
            "accountnumber": f"*****{self._account_number[-7:]}",
            "Referer": "https://myaccount.dominionenergy.com/",
        }
        
        if hasattr(self, "_customer_number") and self._customer_number:
            headers["customernumber"] = f"*****{self._customer_number[-5:]}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as resp:
                    data = await resp.json()
                    _LOGGER.debug("Electric usage response (uom=%s): %s", uom, data)
                    return data
        except aiohttp.ClientError as err:
            raise DominionEnergyApiError(f"Network error: {err}")

    async def get_usage_history_detail(
        self,
        contract: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """Get detailed usage history including daily weather data.
        
        Args:
            contract: Contract number (optional, will try to get from meter info)
            start_date: Start date in MM/DD/YYYY format
            end_date: End date in MM/DD/YYYY format
            
        Returns:
            Detailed usage data including:
            - zDailyWeather: daily high/low temps, heating/cooling degree days
            - zAveTemperature: monthly average temperatures
        """
        from datetime import datetime
        
        # Default date range: start of year to today
        if not start_date:
            start_date = f"01/01/{datetime.now().year}"
        if not end_date:
            end_date = datetime.now().strftime("%m/%d/%Y")
        
        # Contract number is optional - the API may work without it
        params = {
            "AccountNumber": self._account_number,
            "StartDate": start_date,
            "EndDate": end_date,
            "ActionCode": "3",
        }
        if contract:
            params["Contract"] = contract
        
        await self._ensure_token_valid()
        
        headers = {
            **DEFAULT_HEADERS,
            "Authorization": self._token,
            "accountnumber": f"*****{self._account_number[-7:]}",
            "Referer": "https://myaccount.dominionenergy.com/",
        }
        
        if hasattr(self, "_customer_number") and self._customer_number:
            headers["customernumber"] = f"*****{self._customer_number[-5:]}"
        
        url = f"{API_BASE_URL}{USAGE_HISTORY_DETAIL_ENDPOINT}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as resp:
                    data = await resp.json()
                    _LOGGER.debug("Usage history detail response status: %s", resp.status)
                    return data
        except aiohttp.ClientError as err:
            raise DominionEnergyApiError(f"Network error: {err}")

    async def get_generation_data(
        self,
        meter_number: str,
        from_date: str | None = None,
        to_date: str | None = None,
        uom: str = "kWh",
        periodicity: str = "MO",
    ) -> dict[str, Any]:
        """Get solar generation data from the Usageapi/Generation endpoint.
        
        This endpoint returns monthly solar/PV generation data for net metering customers.
        
        Args:
            meter_number: The meter number (18 digits with leading zeros)
            from_date: Start date in YYYY-MM-DD format (defaults to 13 months ago)
            to_date: End date in YYYY-MM-DD format (defaults to next month)
            uom: Unit of measure - typically 'kWh'
            periodicity: 'MO' for monthly data
            
        Returns:
            Generation data with monthly solar production values:
            {
                "Result": {
                    "generationUsages": [
                        {
                            "usageAttribute2": "2025-01-01",  # Date
                            "generation": 28,  # kWh generated
                            "uom": "kWh",
                            ...
                        },
                        ...
                    ]
                }
            }
        """
        from datetime import datetime, timedelta
        
        # Default date range: 13 months back to next month
        if not from_date:
            from_date = (datetime.now() - timedelta(days=395)).strftime("%Y-%m-%d")
        if not to_date:
            to_date = (datetime.now() + timedelta(days=32)).strftime("%Y-%m-%d")
        
        # Pad meter number to 18 digits
        padded_meter = meter_number.zfill(18)
        
        url = f"{USAGE_API_BASE_URL}{GENERATION_ENDPOINT}"
        params = {
            "AccountNumber": self._account_number,
            "MeterNumber": padded_meter,
            "From": from_date,
            "To": to_date,
            "Uom": uom,
            "Periodicity": periodicity,
        }
        
        await self._ensure_token_valid()
        
        headers = {
            **DEFAULT_HEADERS,
            "Authorization": self._token,
            "accountnumber": f"*****{self._account_number[-7:]}",
            "Referer": "https://myaccount.dominionenergy.com/",
        }
        
        if hasattr(self, "_customer_number") and self._customer_number:
            headers["customernumber"] = f"*****{self._customer_number[-5:]}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as resp:
                    data = await resp.json()
                    _LOGGER.debug("Generation data response: %s", data)
                    return data
        except aiohttp.ClientError as err:
            raise DominionEnergyApiError(f"Network error: {err}")

    async def get_daily_usage_data(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        action_code: str = "3",
    ) -> dict[str, Any]:
        """Get daily usage data including consumption AND generation.
        
        This endpoint (/Service/api/1/Usage/UsageData) returns daily data that's
        perfect for Home Assistant's energy dashboard. It includes:
        - Daily consumption (grid usage)
        - Daily generation (solar production)
        - Net usage for net metering customers
        
        Args:
            start_date: Start date in YYYY-MM-DD format (defaults to 30 days ago)
            end_date: End date in YYYY-MM-DD format (defaults to today)
            action_code: API action code - "3" for daily, "4" for hourly
            
        Returns:
            Daily usage data:
            {
                "data": {
                    "nemFlag": "X",  # Net metering indicator
                    "electricUsages": [
                        {
                            "readDate": "11/01/2025 00:00:00",
                            "consumption": "17.08",  # kWh consumed from grid
                            "unitGenerated": "0.368",  # kWh solar generated
                            "netUnit": "0",  # net usage
                            "demandKW": "0",
                            ...
                        },
                        ...
                    ]
                }
            }
        """
        from datetime import datetime, timedelta
        
        # Default date range: 30 days back to today
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        
        url = f"{API_BASE_URL}{USAGE_DATA_ENDPOINT}"
        params = {
            "accountNumber": self._account_number,
            "ActionCode": action_code,
            "StartDate": start_date,
            "EndDate": end_date,
        }
        
        await self._ensure_token_valid()
        
        headers = {
            **DEFAULT_HEADERS,
            "Authorization": self._token,
            "accountnumber": f"*****{self._account_number[-7:]}",
            "Referer": "https://myaccount.dominionenergy.com/",
        }
        
        if hasattr(self, "_customer_number") and self._customer_number:
            headers["customernumber"] = f"*****{self._customer_number[-5:]}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as resp:
                    data = await resp.json()
                    _LOGGER.debug("Daily usage data response status: %s", resp.status)
                    return data
        except aiohttp.ClientError as err:
            raise DominionEnergyApiError(f"Network error: {err}")

    async def get_hourly_usage_data(
        self,
        date: str | None = None,
    ) -> dict[str, Any]:
        """Get hourly usage data including consumption AND generation.
        
        This uses the same endpoint as get_daily_usage_data but with ActionCode=4
        and a single day date range to get hourly data.
        
        Args:
            date: Date in YYYY-MM-DD format (defaults to today)
            
        Returns:
            Hourly usage data:
            {
                "data": {
                    "nemFlag": "X",  # Net metering indicator
                    "electricUsages": [
                        {
                            "readDate": "12/1/2025 12:00:00 AM",
                            "consumption": "1.103",  # kWh consumed
                            "unitGenerated": "0",  # kWh solar generated
                            "netUnit": "0",
                            "demandKW": "0",
                            ...
                        },
                        ...  # 24 records for each hour
                    ]
                }
            }
        """
        from datetime import datetime, timedelta
        
        # Default to yesterday (today's data may be incomplete)
        if not date:
            date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        # For hourly data, we need a 1-day range
        start_date = date
        end_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Use ActionCode=4 for hourly data
        return await self.get_daily_usage_data(
            start_date=start_date,
            end_date=end_date,
            action_code="4"
        )

    async def get_weather_data(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        contract: str | None = None,
    ) -> dict[str, Any]:
        """Get weather data from GetUsageHistoryDetail API.
        
        This endpoint provides:
        - Daily high/low temperatures
        - Heating degree days
        - Cooling degree days  
        - Monthly average temperatures
        
        Args:
            start_date: Start date in MM/DD/YYYY format (defaults to 30 days ago)
            end_date: End date in MM/DD/YYYY format (defaults to today)
            contract: Contract number (defaults to stored contract if available)
            
        Returns:
            Weather data:
            {
                "data": {
                    "zDailyWeather": {
                        "results": [
                            {
                                "tempVal_High": "073",
                                "tempVal_Low": "059", 
                                "heatDegDays": "00",
                                "coolDegDays": "01",
                                "date": "04/04/2025 00:00:00"
                            },
                            ...
                        ]
                    },
                    "zAveTemperature": {
                        "results": [
                            {"monthName": "January", "avgTempVal": "031"},
                            ...
                        ]
                    }
                }
            }
        """
        from datetime import datetime, timedelta
        
        # Default date range: 30 days back to today
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%m/%d/%Y")
        if not end_date:
            end_date = datetime.now().strftime("%m/%d/%Y")
        
        # Get contract number if not provided
        if not contract:
            contract = await self.get_contract_number()
            if not contract:
                _LOGGER.warning("Could not retrieve contract number for weather data")
        
        return await self.get_usage_history_detail(
            start_date=start_date,
            end_date=end_date,
            contract=contract,
        )

    async def get_current_bill(self) -> dict[str, Any]:
        """Get current bill details from the Billing API.
        
        This provides detailed current bill information including:
        - Previous balance
        - Payment received
        - Current charges
        - Due date
        - Auto-pay status
        - Next meter read date
        - Rate category
        
        Returns:
            Current bill data:
            {
                "data": [{
                    "accountNumber": "8750822515",
                    "invoiceId": "800180948964",
                    "previousBalance": "0.00",
                    "paymentReceivedDate": "11-10-2025",
                    "paymentReceived": "37.68",
                    "remainingBalance": "70.74",
                    "currentCharges": "70.74",
                    "totalAmountDue": "70.74",
                    "billDueDate": "12-12-2025",
                    "pastDueAmount": "0.00",
                    "extension": {
                        "AutoPayInd": "X",
                        "CurrentRateCat": "VR-1",
                        "NextMeterReadDate": "12-15-2025",
                        ...
                    }
                }]
            }
        """
        await self._ensure_token_valid()
        
        url = f"{BILLING_API_BASE_URL}{BILL_CURRENT_ENDPOINT}"
        
        headers = {
            **DEFAULT_HEADERS,
            "Authorization": self._token,
            "accountnumber": f"*****{self._account_number[-7:]}",
            "Content-Type": "application/json;charset=UTF-8",
            "Referer": "https://myaccount.dominionenergy.com/",
        }
        
        if hasattr(self, "_customer_number") and self._customer_number:
            headers["customernumber"] = f"*****{self._customer_number[-5:]}"
        
        payload = {
            "accountNumbers": [self._account_number],
            "extension": {}
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    data = await resp.json()
                    _LOGGER.debug("Current bill response status: %s", resp.status)
                    return data
        except aiohttp.ClientError as err:
            raise DominionEnergyApiError(f"Network error: {err}")

    async def get_billing_history(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """Get billing history from the Billing API.
        
        This provides historical bill data including:
        - Bill dates
        - Due dates
        - Invoice IDs
        - Billing days
        - Current charges
        - Amount due
        
        Args:
            start_date: Start date in YYYY-MM-DD format (defaults to 3 years ago)
            end_date: End date in YYYY-MM-DD format (defaults to today)
            
        Returns:
            Bill history data:
            {
                "data": [
                    {
                        "accountNumber": "8750822515",
                        "billDate": "11-14-2025",
                        "dueDate": "12/12/2025 00:00:00",
                        "invoiceId": "800180948964",
                        "billingDays": 30,
                        "currentCharges": "70.74",
                        "amountDue": "70.74",
                        "status": "Posted",
                        ...
                    },
                    ...
                ]
            }
        """
        from datetime import datetime, timedelta
        
        # Default date range: 3 years back to today
        if not start_date:
            start_date = (datetime.now() - timedelta(days=1095)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        
        await self._ensure_token_valid()
        
        url = f"{BILLING_API_BASE_URL}{BILL_HISTORY_BILLING_ENDPOINT}"
        
        headers = {
            **DEFAULT_HEADERS,
            "Authorization": self._token,
            "accountnumber": f"*****{self._account_number[-7:]}",
            "Content-Type": "application/json;charset=UTF-8",
            "Referer": "https://myaccount.dominionenergy.com/",
        }
        
        if hasattr(self, "_customer_number") and self._customer_number:
            headers["customernumber"] = f"*****{self._customer_number[-5:]}"
        
        payload = {
            "accountNumbers": [self._account_number],
            "startDate": start_date,
            "endDate": end_date,
            "extension": {}
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    data = await resp.json()
                    _LOGGER.debug("Billing history response status: %s, records: %s", 
                                 resp.status, len(data.get("data", [])))
                    return data
        except aiohttp.ClientError as err:
            raise DominionEnergyApiError(f"Network error: {err}")

    async def get_all_data(self) -> DominionEnergyData:
        """Fetch all available data from the API.
        
        This method gathers comprehensive data from multiple Dominion Energy APIs:
        - Bill forecast (current usage, billing period)
        - Electric usage (monthly consumption history)
        - Generation data (monthly solar generation for net metering customers)
        - Daily usage data (daily consumption and generation)
        - Current bill details (due date, payments, balances, auto-pay status)
        - Billing history (historical bills)
        - Meter info (AMI status)
        - Weather data (temperatures, heating/cooling degree days)
        """
        data = DominionEnergyData()

        try:
            # Get bill forecast (main source of current data)
            bill_forecast = await self.get_bill_forecast()
            forecast_data = bill_forecast.get("data", {})
            
            # Current usage from forecast
            current_kwh = forecast_data.get("currentUsageKwh")
            if current_kwh:
                try:
                    data.monthly_usage = float(current_kwh)
                    data.grid_consumption = data.monthly_usage  # Alias for energy dashboard
                except (ValueError, TypeError):
                    pass
            
            # Last bill data from forecast
            last_bill = forecast_data.get("lastBill", {})
            if last_bill:
                try:
                    charges = last_bill.get("charges")
                    if charges:
                        data.last_bill_amount = float(charges)
                    usage = last_bill.get("usage")
                    if usage:
                        data.last_bill_usage = float(usage)
                except (ValueError, TypeError):
                    pass
            
            # Last year comparison data
            last_year = forecast_data.get("lastYear", {})
            if last_year:
                try:
                    charges = last_year.get("charges")
                    if charges:
                        data.last_year_bill_amount = float(charges)
                    usage = last_year.get("usage")
                    if usage:
                        data.last_year_usage = float(usage)
                except (ValueError, TypeError):
                    pass
            
            # Current bill amount from totalChange
            total_change = forecast_data.get("totalChange")
            if total_change:
                try:
                    data.current_bill = float(total_change)
                except (ValueError, TypeError):
                    pass
            
            # Billing period dates - try multiple formats
            billing_start = forecast_data.get("billperdstdate") or forecast_data.get("billingPeriodStartDate")
            billing_end = forecast_data.get("billperdeddate") or forecast_data.get("billingPeriodEndDate")
            
            if billing_start:
                try:
                    # Try format "11/14/2025 00:00:00"
                    if " " in billing_start:
                        data.billing_period_start = datetime.strptime(billing_start.split(" ")[0], "%m/%d/%Y")
                    else:
                        data.billing_period_start = datetime.fromisoformat(billing_start.replace("Z", "+00:00"))
                except ValueError:
                    _LOGGER.debug("Could not parse billing start date: %s", billing_start)
            
            if billing_end:
                try:
                    if " " in billing_end:
                        data.billing_period_end = datetime.strptime(billing_end.split(" ")[0], "%m/%d/%Y")
                    else:
                        data.billing_period_end = datetime.fromisoformat(billing_end.replace("Z", "+00:00"))
                except ValueError:
                    _LOGGER.debug("Could not parse billing end date: %s", billing_end)

            # Calculate rate if we have usage and cost
            if data.current_bill and data.monthly_usage and data.monthly_usage > 0:
                data.current_rate = round(data.current_bill / data.monthly_usage, 4)

            # Calculate daily cost estimate
            if data.billing_period_start and data.current_bill:
                days_elapsed = (datetime.now() - data.billing_period_start.replace(tzinfo=None)).days
                if days_elapsed > 0:
                    data.daily_cost = round(data.current_bill / days_elapsed, 2)

        except DominionEnergyApiError as err:
            _LOGGER.error("Error fetching bill forecast: %s", err)

        try:
            # Get meter info to retrieve meter number and AMI status
            meter_info = await self.get_meter_info()
            meters = meter_info.get("data", [])
            
            if meters:
                meter = meters[0]  # Use first meter
                meter_number = meter.get("meterNumber", "")
                
                # Store meter info in data object
                data.meter_number = meter_number
                data.meter_id = meter.get("meterId")
                data.meter_type = meter.get("meterType")
                data.account_number = meter.get("accountNumber")
                data.is_ami_meter = meter.get("amiMeter", False)
                
                if meter_number:
                    # Store meter number for future use
                    self._meter_number = meter_number
                    
                    # Get monthly electric usage data
                    try:
                        electric_data = await self.get_electric_usage(meter_number)
                        usages = electric_data.get("Result", {}).get("electricUsages", [])
                        
                        if usages:
                            # Get the most recent usage if bill forecast didn't provide it
                            if not data.monthly_usage:
                                for usage in reversed(usages):
                                    consumption = usage.get("consumption", 0)
                                    if consumption and consumption > 0:
                                        data.monthly_usage = float(consumption)
                                        data.grid_consumption = float(consumption)
                                        break
                            
                            # Get current bill amount from latest usage if not set
                            if not data.current_bill:
                                for usage in reversed(usages):
                                    amount = usage.get("amount", 0)
                                    if amount and amount > 0:
                                        data.current_bill = float(amount)
                                        break
                            
                            _LOGGER.debug("Retrieved %d monthly usage records from Electric API", len(usages))
                    except Exception as e:
                        _LOGGER.debug("Error fetching electric usage: %s", e)
                    
                    # Get solar generation data (for solar/net metering customers)
                    try:
                        generation_data = await self.get_generation_data(meter_number)
                        gen_usages = generation_data.get("Result", {}).get("generationUsages", [])
                        
                        if gen_usages:
                            # Build monthly generation history
                            monthly_gen = []
                            for gen in gen_usages:
                                monthly_gen.append({
                                    "date": gen.get("usageAttribute2"),
                                    "generation": gen.get("generation"),
                                    "uom": gen.get("uom"),
                                })
                            data.monthly_generation = monthly_gen
                            
                            # Get current month's generation
                            for gen in reversed(gen_usages):
                                generation = gen.get("generation", 0)
                                if generation and generation > 0:
                                    data.solar_generation = float(generation)
                                    break
                            
                            _LOGGER.debug("Retrieved %d monthly generation records", len(gen_usages))
                    except Exception as gen_err:
                        _LOGGER.debug("Error fetching generation data (may not have solar): %s", gen_err)

        except Exception as err:
            _LOGGER.debug("Error fetching meter/electric data: %s", err)

        try:
            # Get daily usage data - consumption AND generation per day
            daily_data = await self.get_daily_usage_data()
            usage_response = daily_data.get("data", {})
            usage_data = usage_response.get("electricUsages", [])
            
            # Check for net metering flag
            nem_flag = usage_response.get("nemFlag", "")
            data.is_net_metering = nem_flag == "X"
            
            if usage_data:
                # Build daily consumption and generation lists
                daily_consumption = []
                daily_generation = []
                
                for day in usage_data:
                    read_date = day.get("readDate", "")
                    
                    # Parse consumption (may be string)
                    consumption = 0
                    try:
                        consumption = float(day.get("consumption", 0))
                    except (ValueError, TypeError):
                        pass
                    
                    # Parse generation (may be string)
                    generated = 0
                    try:
                        generated = float(day.get("unitGenerated", 0))
                    except (ValueError, TypeError):
                        pass
                    
                    daily_consumption.append({
                        "date": read_date,
                        "consumption": consumption,
                        "net_unit": day.get("netUnit"),
                        "demand_kw": day.get("demandKW"),
                    })
                    
                    if generated > 0:
                        daily_generation.append({
                            "date": read_date,
                            "generation": generated,
                        })
                
                data.daily_consumption = daily_consumption
                if daily_generation:
                    data.daily_generation = daily_generation
                
                # Get today's values from the most recent day
                if daily_consumption:
                    latest = daily_consumption[-1]
                    data.today_consumption = latest.get("consumption")
                
                if daily_generation:
                    latest = daily_generation[-1]
                    data.today_generation = latest.get("generation")
                
                # Calculate today's net usage
                if data.today_consumption is not None:
                    gen = data.today_generation or 0
                    data.today_net_usage = round(data.today_consumption - gen, 2)
                
                # Get yesterday's values from the second most recent day
                if len(daily_consumption) >= 2:
                    yesterday = daily_consumption[-2]
                    data.yesterday_consumption = yesterday.get("consumption")
                
                if len(daily_generation) >= 2:
                    yesterday_gen = daily_generation[-2]
                    data.yesterday_generation = yesterday_gen.get("generation")
                
                # Calculate yesterday's net usage
                if data.yesterday_consumption is not None:
                    gen = data.yesterday_generation or 0
                    data.yesterday_net_usage = round(data.yesterday_consumption - gen, 2)
                
                # Calculate grid return from daily generation
                if daily_generation:
                    total_generated = sum(d.get("generation", 0) for d in daily_generation)
                    if total_generated > 0:
                        data.grid_return = total_generated
                
                _LOGGER.debug("Retrieved %d daily usage records, today: %.2f kWh", 
                             len(usage_data), data.today_consumption or 0)
                
        except Exception as err:
            _LOGGER.debug("Error fetching daily usage data: %s", err)

        try:
            # Get current bill details from Billing API
            current_bill_data = await self.get_current_bill()
            
            # Ensure we have a dict response
            if not isinstance(current_bill_data, dict):
                _LOGGER.debug("Unexpected current bill response type: %s", type(current_bill_data))
                current_bill_data = {}
            
            bills = current_bill_data.get("data", [])
            
            # Ensure bills is a list
            if not isinstance(bills, list):
                _LOGGER.debug("Unexpected bills data type: %s", type(bills))
                bills = []
            
            if bills and isinstance(bills[0], dict):
                bill = bills[0]
                
                # Update bill-related fields
                if not data.current_bill:
                    charges = bill.get("currentCharges")
                    if charges:
                        try:
                            data.current_bill = float(charges)
                        except (ValueError, TypeError):
                            pass
                
                # Total amount due
                total_due = bill.get("totalAmountDue")
                if total_due:
                    try:
                        data.total_amount_due = float(total_due)
                    except (ValueError, TypeError):
                        pass
                
                # Balance details
                try:
                    data.previous_balance = float(bill.get("previousBalance", 0))
                    data.payment_received = float(bill.get("paymentReceived", 0))
                    data.remaining_balance = float(bill.get("remainingBalance", 0))
                except (ValueError, TypeError):
                    pass
                
                # Due date - format: "12-12-2025"
                due_date_str = bill.get("billDueDate")
                if due_date_str:
                    try:
                        data.bill_due_date = datetime.strptime(due_date_str, "%m-%d-%Y")
                    except ValueError:
                        _LOGGER.debug("Could not parse due date: %s", due_date_str)
                
                # Extension fields
                extension = bill.get("extension", {})
                data.rate_category = extension.get("CurrentRateCat")
                
                # Auto-pay indicator - "X" means enabled
                auto_pay = extension.get("AutoPayInd", "")
                data.auto_pay_enabled = auto_pay == "X"
                
                # Next meter read date - format: "12-15-2025"
                next_read = extension.get("NextMeterReadDate")
                if next_read:
                    try:
                        data.next_meter_read_date = datetime.strptime(next_read, "%m-%d-%Y")
                    except ValueError:
                        _LOGGER.debug("Could not parse next meter read date: %s", next_read)
                
                # Last payment info
                last_pay_date = extension.get("LastPaymentDate")
                if last_pay_date:
                    try:
                        # Format: "11/10/2025 00:00:00"
                        data.last_payment_date = datetime.strptime(last_pay_date.split(" ")[0], "%m/%d/%Y")
                    except ValueError:
                        _LOGGER.debug("Could not parse last payment date: %s", last_pay_date)
                
                last_pay_amount = extension.get("LastPaymentAmount")
                if last_pay_amount:
                    try:
                        data.last_payment_amount = float(last_pay_amount)
                    except (ValueError, TypeError):
                        pass
                
                _LOGGER.debug("Retrieved current bill: due %s, rate %s, auto-pay: %s", 
                             due_date_str, data.rate_category, data.auto_pay_enabled)
                
        except Exception as err:
            _LOGGER.debug("Error fetching current bill: %s", err)

        try:
            # Get bill history
            billing_history = await self.get_billing_history()
            
            # Ensure we have a dict response
            if not isinstance(billing_history, dict):
                _LOGGER.debug("Unexpected billing history response type: %s", type(billing_history))
                billing_history = {}
            
            bills = billing_history.get("data", [])
            
            # Ensure bills is a list of dicts
            if isinstance(bills, list) and bills and isinstance(bills[0], dict):
                data.bill_history = bills
                _LOGGER.debug("Retrieved %d bills from billing history", len(bills))
            else:
                _LOGGER.debug("Billing history data is not a list of dicts: %s", type(bills))

        except Exception as err:
            _LOGGER.debug("Error fetching billing history: %s", err)

        try:
            # Get weather data from GetUsageHistoryDetail
            weather_data = await self.get_weather_data()
            
            # Ensure we have a dict response
            if not isinstance(weather_data, dict):
                _LOGGER.debug("Unexpected weather data response type: %s", type(weather_data))
                weather_data = {}
            
            weather_response = weather_data.get("data", {})
            
            # Ensure weather_response is a dict
            if not isinstance(weather_response, dict):
                _LOGGER.debug("Unexpected weather response data type: %s, value: %s", 
                             type(weather_response), str(weather_response)[:200])
                weather_response = {}
            
            # Daily weather
            daily_weather_container = weather_response.get("zDailyWeather", {})
            if isinstance(daily_weather_container, dict):
                daily_weather = daily_weather_container.get("results", [])
            else:
                daily_weather = []
                _LOGGER.debug("zDailyWeather is not a dict: %s", type(daily_weather_container))
            
            if daily_weather and isinstance(daily_weather, list) and len(daily_weather) > 0:
                # Get most recent day's weather
                latest = daily_weather[-1]
                if isinstance(latest, dict):
                    try:
                        high = latest.get("tempVal_High", "")
                        if high:
                            data.daily_high_temp = int(high)
                        low = latest.get("tempVal_Low", "")
                        if low:
                            data.daily_low_temp = int(low)
                        hdd = latest.get("heatDegDays", "")
                        if hdd:
                            data.heating_degree_days = int(hdd)
                        cdd = latest.get("coolDegDays", "")
                        if cdd:
                            data.cooling_degree_days = int(cdd)
                    except (ValueError, TypeError) as e:
                        _LOGGER.debug("Error parsing weather data: %s", e)
            else:
                _LOGGER.debug("No daily weather data available in response")
            
            # Monthly average temperature
            avg_temps_container = weather_response.get("zAveTemperature", {})
            if isinstance(avg_temps_container, dict):
                avg_temps = avg_temps_container.get("results", [])
            else:
                avg_temps = []
                
            if avg_temps and isinstance(avg_temps, list):
                # Get current month's average (last in list typically)
                current_month = datetime.now().strftime("%B")  # e.g., "December"
                for temp in avg_temps:
                    if isinstance(temp, dict) and temp.get("monthName") == current_month:
                        try:
                            data.monthly_avg_temp = int(temp.get("avgTempVal", "0"))
                        except (ValueError, TypeError):
                            pass
                        break
                # If no match, use the last available month
                if data.monthly_avg_temp is None and avg_temps:
                    last_temp = avg_temps[-1]
                    if isinstance(last_temp, dict):
                        try:
                            data.monthly_avg_temp = int(last_temp.get("avgTempVal", "0"))
                        except (ValueError, TypeError):
                            pass
            
            _LOGGER.debug("Retrieved weather data: high %s, low %s, HDD %s, CDD %s",
                         data.daily_high_temp, data.daily_low_temp,
                         data.heating_degree_days, data.cooling_degree_days)
                
        except Exception as err:
            _LOGGER.debug("Error fetching weather data: %s", err)

        return data

    async def validate_credentials(self) -> bool:
        """Validate credentials by attempting to fetch data.
        
        Returns True if credentials are valid, False otherwise.
        """
        try:
            await self.authenticate()
            # Try to make a simple API call to verify the token works
            await self.get_bill_forecast()
            return True
        except DominionEnergyAuthError:
            return False
        except DominionEnergyApiError:
            # Auth worked but API call failed - credentials are still valid
            return True
