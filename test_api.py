#!/usr/bin/env python3
"""Test script for the Dominion Energy integration library with TFA support."""

import asyncio
import getpass
import json
import logging
import sys
from pathlib import Path

# Add the custom_components/dominion_energy directory to the path
# Import directly from api.py to avoid __init__.py which requires homeassistant
sys.path.insert(0, str(Path(__file__).parent / "custom_components" / "dominion_energy"))

# Now import from the actual integration library
from api import (
    DominionEnergyApi,
    DominionEnergyApiError,
    DominionEnergyAuthError,
    DominionEnergyData,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
_LOGGER = logging.getLogger(__name__)


def get_tfa_code() -> str:
    """Callback function to get TFA code from user."""
    print("\n" + "=" * 40)
    print("TFA CODE REQUIRED")
    print("=" * 40)
    print("A verification code has been sent.")
    code = input("Enter the 6-digit verification code: ").strip()
    return code


def choose_tfa_option(options: list[dict]) -> int:
    """Callback function to let user choose a TFA option."""
    print("\n" + "=" * 40)
    print("TFA OPTIONS AVAILABLE")
    print("=" * 40)
    for i, opt in enumerate(options):
        print(f"  [{i}] {opt['name']}")
    print("-" * 40)
    while True:
        try:
            choice = input(f"Choose an option (0-{len(options)-1}): ").strip()
            idx = int(choice)
            if 0 <= idx < len(options):
                return idx
            print(f"Please enter a number between 0 and {len(options)-1}")
        except ValueError:
            print("Please enter a valid number")


async def test_full_api():
    """Test the full API flow using the integration library."""
    print("\n" + "=" * 60)
    print("DOMINION ENERGY API TEST (with TFA Support)")
    print("=" * 60)
    print("\nThis tests the actual integration library code.\n")

    # Credentials
    username = "jason@walljm.com"
    account_number = "8750822515"
    password = getpass.getpass("Enter your password: ")
    
    if not password:
        print("ERROR: Password is required")
        return

    # Create API client using the integration library
    api = DominionEnergyApi(username, password, account_number)
    
    # Set the TFA callbacks
    api.set_tfa_callback(get_tfa_code, choose_tfa_option)
    
    print("\n" + "-" * 40)
    print("Step 1: Authentication")
    print("-" * 40)
    
    try:
        _LOGGER.info("Starting authentication via library...")
        result = await api.authenticate()
        
        if result:
            print("✅ Authentication successful!")
            if api._uuid:
                print(f"   UUID: {api._uuid}")
            if api._cookies:
                print(f"   Cookies captured: {len(api._cookies)}")
        else:
            print("❌ Authentication failed - no auth data obtained")
            return
            
    except DominionEnergyAuthError as e:
        print(f"❌ Authentication error: {e}")
        return
    except DominionEnergyApiError as e:
        print(f"❌ API error: {e}")
        return
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        _LOGGER.exception("Authentication failed")
        return
    
    print("\n" + "-" * 40)
    print("Step 2: Fetch Energy Data")
    print("-" * 40)
    
    try:
        _LOGGER.info("Fetching energy data via library...")
        data: DominionEnergyData = await api.get_all_data()
        
        print("✅ Energy data retrieved successfully!\n")
        
        # Display the data
        print("CURRENT USAGE:")
        if data.monthly_usage is not None:
            print(f"   Monthly Usage: {data.monthly_usage} kWh")
        else:
            print("   Monthly Usage: Not available")
            
        if data.grid_consumption is not None:
            print(f"   Grid Consumption: {data.grid_consumption} kWh")
        else:
            print("   Grid Consumption: Not available")
            
        if data.grid_return is not None:
            print(f"   Grid Return (Solar): {data.grid_return} kWh")
        else:
            print("   Grid Return: Not available")
        
        print("\nSOLAR DATA:")
        if data.solar_generation is not None:
            print(f"   Solar Generation (Current Month): {data.solar_generation} kWh")
        else:
            print("   Solar Generation: Not available (may not have solar)")
        
        if data.monthly_generation:
            print(f"   Monthly Generation Records: {len(data.monthly_generation)}")
        
        if data.daily_generation:
            print(f"   Daily Generation Records: {len(data.daily_generation)}")
        
        if data.daily_consumption:
            print(f"   Daily Consumption Records: {len(data.daily_consumption)}")
        
        print("\nBILLING:")
        if data.current_bill is not None:
            print(f"   Current Bill: ${data.current_bill:.2f}")
        else:
            print("   Current Bill: Not available")
        if data.billing_period_start:
            print(f"   Billing Period Start: {data.billing_period_start}")
        if data.billing_period_end:
            print(f"   Billing Period End: {data.billing_period_end}")
        if data.bill_due_date:
            print(f"   Bill Due Date: {data.bill_due_date}")
        if data.previous_balance is not None:
            print(f"   Previous Balance: ${data.previous_balance:.2f}")
        if data.payment_received is not None:
            print(f"   Payment Received: ${data.payment_received:.2f}")
        if data.remaining_balance is not None:
            print(f"   Remaining Balance: ${data.remaining_balance:.2f}")
        
        print("\nRATE INFO:")
        if data.current_rate is not None:
            print(f"   Current Rate: ${data.current_rate:.4f}/kWh")
        else:
            print("   Current Rate: Not available")
        if data.daily_cost is not None:
            print(f"   Daily Cost Estimate: ${data.daily_cost:.2f}")
        else:
            print("   Daily Cost: Not available")
        if data.rate_category:
            print(f"   Rate Category: {data.rate_category}")
        
        print("\nTODAY'S DATA:")
        if data.today_consumption is not None:
            print(f"   Today's Consumption: {data.today_consumption} kWh")
        if data.today_generation is not None:
            print(f"   Today's Generation: {data.today_generation} kWh")
        if data.today_net_usage is not None:
            print(f"   Today's Net Usage: {data.today_net_usage} kWh")
        
        print("\nYESTERDAY'S DATA:")
        if data.yesterday_consumption is not None:
            print(f"   Yesterday's Consumption: {data.yesterday_consumption} kWh")
        else:
            print("   Yesterday's Consumption: Not available")
        if data.yesterday_generation is not None:
            print(f"   Yesterday's Generation: {data.yesterday_generation} kWh")
        if data.yesterday_net_usage is not None:
            print(f"   Yesterday's Net Usage: {data.yesterday_net_usage} kWh")
        
        print("\nBILL COMPARISON:")
        if data.last_bill_amount is not None:
            print(f"   Last Bill Amount: ${data.last_bill_amount:.2f}")
        if data.last_bill_usage is not None:
            print(f"   Last Bill Usage: {data.last_bill_usage} kWh")
        if data.last_year_bill_amount is not None:
            print(f"   Same Month Last Year: ${data.last_year_bill_amount:.2f}")
        if data.last_year_usage is not None:
            print(f"   Same Month Last Year Usage: {data.last_year_usage} kWh")
        # Show differences between current and last year
        if data.current_bill is not None and data.last_year_bill_amount is not None:
            bill_diff = data.current_bill - data.last_year_bill_amount
            bill_pct = (bill_diff / data.last_year_bill_amount * 100) if data.last_year_bill_amount else 0
            sign = "+" if bill_diff >= 0 else ""
            print(f"   Year-over-Year Bill Diff: {sign}${bill_diff:.2f} ({sign}{bill_pct:.1f}%)")
        if data.monthly_usage is not None and data.last_year_usage is not None:
            usage_diff = data.monthly_usage - data.last_year_usage
            usage_pct = (usage_diff / data.last_year_usage * 100) if data.last_year_usage else 0
            sign = "+" if usage_diff >= 0 else ""
            print(f"   Year-over-Year Usage Diff: {sign}{usage_diff:.1f} kWh ({sign}{usage_pct:.1f}%)")
        
        print("\nPAYMENT INFO:")
        if data.last_payment_date:
            print(f"   Last Payment Date: {data.last_payment_date}")
        if data.last_payment_amount is not None:
            print(f"   Last Payment Amount: ${data.last_payment_amount:.2f}")
        if data.total_amount_due is not None:
            print(f"   Total Amount Due: ${data.total_amount_due:.2f}")
        if data.bill_due_date:
            print(f"   Bill Due Date: {data.bill_due_date}")
        
        print("\nACCOUNT STATUS:")
        if data.auto_pay_enabled is not None:
            print(f"   Auto Pay: {'Enabled' if data.auto_pay_enabled else 'Disabled'}")
        if data.is_net_metering is not None:
            print(f"   Net Metering: {'Yes' if data.is_net_metering else 'No'}")
        if data.is_ami_meter is not None:
            print(f"   Smart Meter (AMI): {'Yes' if data.is_ami_meter else 'No'}")
        if data.next_meter_read_date:
            print(f"   Next Meter Read: {data.next_meter_read_date}")
        
        print("\nMETER INFO:")
        if data.meter_number:
            print(f"   Meter Number: {data.meter_number}")
        if data.meter_id:
            print(f"   Meter ID: {data.meter_id}")
        if data.meter_type:
            print(f"   Meter Type: {data.meter_type}")
        if data.account_number:
            print(f"   Account Number: {data.account_number}")
        
        print("\nWEATHER DATA:")
        if data.daily_high_temp is not None:
            print(f"   Daily High: {data.daily_high_temp}°F")
        else:
            print("   Daily High: Not available")
        if data.daily_low_temp is not None:
            print(f"   Daily Low: {data.daily_low_temp}°F")
        else:
            print("   Daily Low: Not available")
        if data.heating_degree_days is not None:
            print(f"   Heating Degree Days: {data.heating_degree_days}")
        else:
            print("   Heating Degree Days: Not available")
        if data.cooling_degree_days is not None:
            print(f"   Cooling Degree Days: {data.cooling_degree_days}")
        else:
            print(f"   Cooling Degree Days: Not available")
        if data.monthly_avg_temp is not None:
            print(f"   Monthly Average: {data.monthly_avg_temp}°F")
        else:
            print("   Monthly Average: Not available")
        
        print("\nHISTORICAL DATA:")
        if data.daily_usage:
            print(f"   Daily Usage Records: {len(data.daily_usage)} days")
            # Show last 5 days
            recent = data.daily_usage[-5:] if len(data.daily_usage) > 5 else data.daily_usage
            for record in recent:
                date = record.get("date", "Unknown")
                kwh = record.get("kwh", record.get("usage", record.get("consumption", "N/A")))
                print(f"      {date}: {kwh} kWh")
        else:
            print("   No daily usage data available")
        
        if data.bill_history and isinstance(data.bill_history, list):
            print(f"\n   Bill History: {len(data.bill_history)} bills")
            recent_bills = data.bill_history[:3] if len(data.bill_history) > 3 else data.bill_history
            for bill in recent_bills:
                if isinstance(bill, dict):
                    print(f"      {bill.get('billDate')}: ${bill.get('currentCharges')} (Due: {str(bill.get('dueDate', 'N/A'))[:10]})")
        
        # Save session AFTER fetching data (includes contract/customer_number)
        session_file = Path(__file__).parent / ".session_cache.json"
        session_data = api.get_session_data()
        with open(session_file, "w") as f:
            json.dump(session_data, f, indent=2)
        print(f"\n✅ Session saved to {session_file}")
            
    except DominionEnergyAuthError as e:
        print(f"❌ Auth error while fetching data: {e}")
    except DominionEnergyApiError as e:
        print(f"❌ API error while fetching data: {e}")
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        _LOGGER.exception("Data fetch failed")
    
    # Clean up
    await api.close()
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


async def test_auth_only():
    """Test only the authentication portion."""
    print("\n" + "=" * 60)
    print("AUTHENTICATION-ONLY TEST (with TFA Support)")
    print("=" * 60)
    
    username = input("Enter your Dominion Energy email: ").strip()
    password = getpass.getpass("Enter your password: ")
    account_number = input("Enter your account number: ").strip()
    
    api = DominionEnergyApi(username, password, account_number)
    
    # Set the TFA callbacks
    api.set_tfa_callback(get_tfa_code, choose_tfa_option)
    
    try:
        result = await api.authenticate()
        if result:
            print(f"\n✅ Authentication successful!")
            if api._uuid:
                print(f"   UUID: {api._uuid}")
            if api._cookies:
                print(f"   Cookies captured: {len(api._cookies)}")
        else:
            print("\n❌ Authentication failed")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        _LOGGER.exception("Auth test failed")
    finally:
        await api.close()


async def test_individual_endpoints():
    """Test individual API endpoints after authentication."""
    print("\n" + "=" * 60)
    print("INDIVIDUAL ENDPOINT TEST")
    print("=" * 60)
    
    username = "jason@walljm.com"
    account_number = "8750822515"
    password = getpass.getpass("Enter your password: ")
    
    api = DominionEnergyApi(username, password, account_number)
    api.set_tfa_callback(get_tfa_code, choose_tfa_option)
    
    try:
        print("\n1. Authenticating...")
        await api.authenticate()
        print("   ✅ Authenticated")
        
        print("\n2. Getting Bill Forecast...")
        try:
            forecast = await api.get_bill_forecast()
            print(f"   ✅ Bill forecast retrieved")
            print(f"   Response keys: {list(forecast.keys())}")
            if "data" in forecast:
                print(f"   Data keys: {list(forecast['data'].keys())}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        print("\n3. Getting Usage History...")
        try:
            usage = await api.get_usage_history()
            print(f"   ✅ Usage history retrieved")
            print(f"   Response keys: {list(usage.keys())}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        print("\n4. Getting Bill History...")
        try:
            bills = await api.get_bill_history()
            print(f"   ✅ Bill history retrieved")
            print(f"   Response keys: {list(bills.keys())}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        print("\n5. Getting Meter Info...")
        meter_number = None
        try:
            meters = await api.get_meter_info()
            print(f"   ✅ Meter info retrieved")
            meter_data = meters.get("data", [])
            if meter_data:
                meter_number = meter_data[0].get("meterNumber")
                print(f"   Meter Number: {meter_number}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        if meter_number:
            print("\n6. Getting Electric Usage (Monthly)...")
            try:
                electric = await api.get_electric_usage(meter_number)
                print(f"   ✅ Electric usage retrieved")
                usages = electric.get("Result", {}).get("electricUsages", [])
                print(f"   Monthly records: {len(usages)}")
                if usages:
                    latest = usages[-1]
                    print(f"   Latest: {latest.get('usageAttribute2')} - {latest.get('consumption')} kWh")
            except Exception as e:
                print(f"   ❌ Error: {e}")
            
            print("\n7. Getting Generation Data (Solar)...")
            try:
                generation = await api.get_generation_data(meter_number)
                print(f"   ✅ Generation data retrieved")
                gen_usages = generation.get("Result", {}).get("generationUsages", [])
                print(f"   Monthly generation records: {len(gen_usages)}")
                if gen_usages:
                    latest = gen_usages[-1]
                    print(f"   Latest: {latest.get('usageAttribute2')} - {latest.get('generation')} kWh")
            except Exception as e:
                print(f"   ❌ Error (may not have solar): {e}")
        
        print("\n8. Getting Daily Usage Data...")
        try:
            daily = await api.get_daily_usage_data()
            print(f"   ✅ Daily usage data retrieved")
            usage_data = daily.get("data", {}).get("usageData", [])
            print(f"   Daily records: {len(usage_data)}")
            if usage_data:
                latest = usage_data[0]
                print(f"   Latest: {latest.get('readDate')} - consumption: {latest.get('consumption')} kWh, generation: {latest.get('unitGenerated')} kWh")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        print("\n9. Getting Current Bill (Billing API)...")
        try:
            current = await api.get_current_bill()
            print(f"   ✅ Current bill retrieved")
            bills_data = current.get("data", [])
            if bills_data:
                bill = bills_data[0]
                print(f"   Total Due: ${bill.get('totalAmountDue')}")
                print(f"   Due Date: {bill.get('billDueDate')}")
                ext = bill.get("extension", {})
                print(f"   Rate Category: {ext.get('CurrentRateCat')}")
                print(f"   Next Meter Read: {ext.get('NextMeterReadDate')}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        print("\n10. Getting Billing History...")
        try:
            billing_history = await api.get_billing_history()
            print(f"   ✅ Billing history retrieved")
            bills_data = billing_history.get("data", [])
            print(f"   Total bills: {len(bills_data)}")
            if bills_data:
                latest = bills_data[0]
                print(f"   Latest: {latest.get('billDate')} - ${latest.get('currentCharges')}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
            
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        _LOGGER.exception("Test failed")
    finally:
        await api.close()


SESSION_FILE = Path(__file__).parent / ".session_cache.json"


async def test_session_persistence():
    """Test session persistence - runs full auth once, then uses saved session."""
    print("\n" + "=" * 60)
    print("SESSION PERSISTENCE TEST")
    print("=" * 60)
    
    username = "jason@walljm.com"
    account_number = "8750822515"
    
    # Check for saved session
    saved_session = None
    if SESSION_FILE.exists():
        try:
            with open(SESSION_FILE) as f:
                saved_session = json.load(f)
            print(f"✅ Found saved session file")
            print(f"   UUID: {saved_session.get('uuid', 'N/A')}")
            print(f"   Has refresh token: {bool(saved_session.get('refresh_token'))}")
        except Exception as e:
            print(f"⚠️ Could not load saved session: {e}")
    else:
        print("ℹ️ No saved session found - will do full authentication")
    
    # Create API with a dummy password (we may not need it if session restore works)
    password = None
    if saved_session:
        print("\n🔄 Attempting to restore session (no password needed)...")
        password = "dummy"  # Won't be used if session restore works
    else:
        password = getpass.getpass("Enter your password: ")
        if not password:
            print("ERROR: Password is required for initial setup")
            return
    
    api = DominionEnergyApi(username, password, account_number)
    api.set_tfa_callback(get_tfa_code, choose_tfa_option)
    
    # Restore saved session if available
    if saved_session:
        restored = api.restore_session_data(saved_session)
        if restored:
            print("✅ Session data restored to API")
        else:
            print("⚠️ Session data could not be restored - will do full auth")
    
    try:
        print("\n" + "-" * 40)
        print("Step 1: Authentication (may use saved session)")
        print("-" * 40)
        
        result = await api.authenticate()
        
        if result:
            print("✅ Authentication successful!")
            print(f"   UUID: {api._uuid}")
            print(f"   Has token: {bool(api._token)}")
            print(f"   Has refresh token: {bool(api._refresh_token)}")
        else:
            print("❌ Authentication failed")
            return
        
        print("\n" + "-" * 40)
        print("Step 2: Fetch Energy Data")
        print("-" * 40)
        
        data = await api.get_all_data()
        
        print("✅ Energy data retrieved!")
        if data.monthly_usage is not None:
            print(f"   Monthly Usage: {data.monthly_usage} kWh")
        if data.grid_consumption is not None:
            print(f"   Grid Consumption: {data.grid_consumption} kWh")
        if data.current_bill is not None:
            print(f"   Current Bill: ${data.current_bill:.2f}")
        
        # Save session AFTER fetching data (includes contract/customer_number)
        session_data = api.get_session_data()
        with open(SESSION_FILE, "w") as f:
            json.dump(session_data, f, indent=2)
        print(f"✅ Session saved to {SESSION_FILE}")
        
        print("\n" + "=" * 60)
        print("TEST COMPLETE")
        print("=" * 60)
        print("\nRun this test again to verify session persistence works.")
        print("If it works, you should NOT be prompted for TFA on the second run.")
        
    except DominionEnergyAuthError as e:
        print(f"❌ Authentication error: {e}")
        # Clear the saved session if auth failed
        if SESSION_FILE.exists():
            SESSION_FILE.unlink()
            print("   Cleared invalid session file")
    except Exception as e:
        print(f"❌ Error: {e}")
        _LOGGER.exception("Test failed")
    finally:
        await api.close()


def main():
    """Main entry point."""
    print("\nAvailable tests:")
    print("  1. Full API test (requires TFA)")
    print("  2. Session persistence test (saves/restores session)")
    print("  3. Individual endpoints test")
    print("")
    choice = input("Choose test (1-3) [default: 2]: ").strip() or "2"
    
    if choice == "1":
        asyncio.run(test_full_api())
    elif choice == "2":
        asyncio.run(test_session_persistence())
    elif choice == "3":
        asyncio.run(test_individual_endpoints())
    else:
        print(f"Invalid choice: {choice}")


if __name__ == "__main__":
    main()
