"""Constants for the Dominion Energy integration."""

DOMAIN = "dominion_energy"

# Configuration keys
CONF_ACCOUNT_NUMBER = "account_number"

# API URLs
LOGIN_URL = "https://login.dominionenergy.com/CommonLogin"
API_BASE_URL = "https://prodsvc-dominioncip.smartcmobile.com/Service/api/1"
ACCOUNT_MGMT_API_BASE_URL = "https://prodsvc-dominioncip.smartcmobile.com/AccountManagementapi/api/1"
USAGE_API_BASE_URL = "https://prodsvc-dominioncip.smartcmobile.com/Usageapi/api/V1"
BILLING_API_BASE_URL = "https://prodsvc-dominioncip.smartcmobile.com/BillingAPI/api/1"

# Endpoint paths - Service API
BILL_FORECAST_ENDPOINT = "/bill/billForecast"
USAGE_HISTORY_ENDPOINT = "/usage/usageHistory"
USAGE_HISTORY_DETAIL_ENDPOINT = "/Usage/GetUsageHistoryDetail"
BILL_HISTORY_ENDPOINT = "/bill/billHistory"
USAGE_DATA_ENDPOINT = "/Usage/UsageData"  # Daily consumption + generation data
GET_BP_NUMBER_ENDPOINT = "/FromDb/GetBpNumber"  # Get customer number from UUID
GET_BUSINESS_MASTER_ENDPOINT = "/BusinessMaster/GetBusinessMaster"  # Get account details including contract

# Account Management API endpoints
METERS_ENDPOINT = "/Meters/Meter/accountNumber"

# Usage API endpoints (for monthly electric data)
ELECTRIC_USAGE_ENDPOINT = "/Electric"
GENERATION_ENDPOINT = "/Generation"  # Monthly solar generation data

# Billing API endpoints
BILL_CURRENT_ENDPOINT = "/bill/current"
BILL_HISTORY_BILLING_ENDPOINT = "/bill/history"

# Gigya Authentication URLs and Constants
GIGYA_API_KEY = "4_6zEg-HY_0eqpgdSONYkJkQ"
GIGYA_AUTH_URL = "https://auth.dominionenergy.com"
GIGYA_LOGIN_ENDPOINT = "/accounts.login"
GIGYA_GET_ACCOUNT_INFO_ENDPOINT = "/accounts.getAccountInfo"
GIGYA_TFA_GET_PROVIDERS_ENDPOINT = "/accounts.tfa.getProviders"
GIGYA_TFA_INIT_ENDPOINT = "/accounts.tfa.initTFA"
GIGYA_TFA_PHONE_GET_NUMBERS_ENDPOINT = "/accounts.tfa.phone.getRegisteredPhoneNumbers"
GIGYA_TFA_PHONE_SEND_CODE_ENDPOINT = "/accounts.tfa.phone.sendVerificationCode"
GIGYA_TFA_PHONE_COMPLETE_ENDPOINT = "/accounts.tfa.phone.completeVerification"
GIGYA_TFA_FINALIZE_ENDPOINT = "/accounts.tfa.finalizeTFA"
GIGYA_FINALIZE_REGISTRATION_ENDPOINT = "/accounts.finalizeRegistration"

# Gigya error codes
GIGYA_ERROR_TFA_REQUIRED = 403101

# Submit login URL for final authentication
SUBMIT_LOGIN_URL = "https://login.dominionenergy.com/SubmitLogin"

# API Constants
ACTION_CODE = "4"
DEFAULT_HEADERS = {
    "uid": "1",
    "pt": "1",
    "channel": "WEB",
    "Origin": "https://myaccount.dominionenergy.com",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

# Gigya API headers
GIGYA_HEADERS = {
    "Accept": "*/*",
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": "https://login.dominionenergy.com",
    "Referer": "https://login.dominionenergy.com/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
}

# Update intervals (in seconds)
SCAN_INTERVAL = 43200  # 12 hours - Dominion updates data once daily

# Sensor types
SENSOR_GRID_CONSUMPTION = "grid_consumption"
SENSOR_GRID_RETURN = "grid_return"
SENSOR_CURRENT_BILL = "current_bill"
SENSOR_BILLING_PERIOD_START = "billing_period_start"
SENSOR_BILLING_PERIOD_END = "billing_period_end"
SENSOR_CURRENT_RATE = "current_rate"
SENSOR_DAILY_COST = "daily_cost"
SENSOR_MONTHLY_USAGE = "monthly_usage"

# New sensors for enhanced data
SENSOR_SOLAR_GENERATION = "solar_generation"
SENSOR_BILL_DUE_DATE = "bill_due_date"
SENSOR_PREVIOUS_BALANCE = "previous_balance"
SENSOR_PAYMENT_RECEIVED = "payment_received"
SENSOR_REMAINING_BALANCE = "remaining_balance"
SENSOR_RATE_CATEGORY = "rate_category"

# Today's usage sensors (most recent day)
SENSOR_TODAY_CONSUMPTION = "today_consumption"
SENSOR_TODAY_GENERATION = "today_generation"
SENSOR_TODAY_NET_USAGE = "today_net_usage"

# Billing comparison sensors
SENSOR_TOTAL_AMOUNT_DUE = "total_amount_due"
SENSOR_LAST_BILL_AMOUNT = "last_bill_amount"
SENSOR_LAST_BILL_USAGE = "last_bill_usage"
SENSOR_LAST_YEAR_BILL_AMOUNT = "last_year_bill_amount"
SENSOR_LAST_YEAR_USAGE = "last_year_usage"

# Payment sensors
SENSOR_LAST_PAYMENT_DATE = "last_payment_date"
SENSOR_LAST_PAYMENT_AMOUNT = "last_payment_amount"

# Account status sensors
SENSOR_NEXT_METER_READ_DATE = "next_meter_read_date"
SENSOR_AUTO_PAY_ENABLED = "auto_pay_enabled"
SENSOR_IS_NET_METERING = "is_net_metering"
SENSOR_IS_AMI_METER = "is_ami_meter"

# Weather sensors
SENSOR_DAILY_HIGH_TEMP = "daily_high_temp"
SENSOR_DAILY_LOW_TEMP = "daily_low_temp"
SENSOR_HEATING_DEGREE_DAYS = "heating_degree_days"
SENSOR_COOLING_DEGREE_DAYS = "cooling_degree_days"
SENSOR_MONTHLY_AVG_TEMP = "monthly_avg_temp"

# Meter info sensors
SENSOR_METER_NUMBER = "meter_number"
SENSOR_METER_ID = "meter_id"
SENSOR_METER_TYPE = "meter_type"
SENSOR_ACCOUNT_NUMBER = "account_number_sensor"

# Attribution
ATTRIBUTION = "Data provided by Dominion Energy"
