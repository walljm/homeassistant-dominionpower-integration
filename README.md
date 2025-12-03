# Dominion Energy Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

A custom Home Assistant integration to fetch energy usage, costs, billing data, and more from Dominion Energy. This integration provides **36 sensors** covering energy consumption, solar generation, billing, weather data, and meter information.

## Features

- **Energy Dashboard Compatible** - All energy sensors work with Home Assistant's Energy Dashboard
- **Solar/Net Metering Support** - Track solar generation and grid return for net metering customers
- **Comprehensive Billing Data** - Current bill, due dates, payment history, and bill comparisons
- **Weather Integration** - Temperature data and degree days from Dominion Energy's weather service
- **Daily & Monthly Usage** - Both granular daily data and monthly summaries
- **Meter Information** - Full meter details including AMI (smart meter) status
- **Autonomous Operation** - Uses refresh tokens for persistent authentication after initial setup

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click on the three dots in the top right corner
3. Select "Custom repositories"
4. Add this repository URL: `https://github.com/walljm/homeassistant-dominionpower-integration`
5. Select "Integration" as the category
6. Click "Add"
7. Search for "Dominion Energy" in HACS
8. Click "Download"
9. Restart Home Assistant

### Manual Installation

1. Download the `custom_components/dominion_energy` folder from this repository
2. Copy it to your Home Assistant's `custom_components` directory
3. Restart Home Assistant

## Configuration

### Prerequisites

You'll need the following information from your Dominion Energy account:

1. **Username** - Your Dominion Energy account email
2. **Password** - Your Dominion Energy account password
3. **Account Number** - Your Dominion Energy account number (found on your bill)

### Setup

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Dominion Energy"
4. Enter your credentials and account number
5. If two-factor authentication is enabled, enter the SMS verification code when prompted
6. Click **Submit**

### Two-Factor Authentication (TFA)

This integration supports Dominion Energy's two-factor authentication. On first setup:

1. You'll be prompted to select a phone number for SMS verification
2. Enter the verification code sent to your phone
3. The device will be registered as "trusted" for future autonomous operation

## Sensors

### Energy Sensors

| Sensor                 | Description                                      | Unit |
| ---------------------- | ------------------------------------------------ | ---- |
| Grid Consumption       | Total energy consumed from grid (billing period) | kWh  |
| Grid Return            | Total energy returned to grid (solar customers)  | kWh  |
| Monthly Usage          | Month-to-date energy usage                       | kWh  |
| Today's Consumption    | Most recent day's grid consumption               | kWh  |
| Today's Generation     | Most recent day's solar generation               | kWh  |
| Today's Net Usage      | Today's consumption minus generation             | kWh  |
| Yesterday's Consumption| Previous day's grid consumption                  | kWh  |
| Yesterday's Generation | Previous day's solar generation                  | kWh  |
| Yesterday's Net Usage  | Yesterday's consumption minus generation         | kWh  |
| Solar Generation       | Current month's solar generation                 | kWh  |

### Billing Sensors

| Sensor                | Description                    | Unit  |
| --------------------- | ------------------------------ | ----- |
| Current Bill          | Current billing period charges | USD   |
| Total Amount Due      | Full account balance           | USD   |
| Daily Cost            | Estimated average daily cost   | USD   |
| Current Rate          | Current electricity rate       | $/kWh |
| Previous Balance      | Balance carried forward        | USD   |
| Payment Received      | Last payment credited          | USD   |
| Remaining Balance     | Current account balance        | USD   |
| Last Bill Amount      | Previous month's bill          | USD   |
| Last Bill Usage       | Previous month's usage         | kWh   |
| Last Year Bill Amount | Same month last year's bill    | USD   |
| Last Year Usage       | Same month last year's usage   | kWh   |

### Date Sensors

| Sensor               | Description                     |
| -------------------- | ------------------------------- |
| Billing Period Start | Start of current billing period |
| Billing Period End   | End of current billing period   |
| Bill Due Date        | Next payment due date           |
| Last Payment Date    | Date of last payment            |
| Next Meter Read Date | Scheduled meter reading date    |

### Payment Sensors

| Sensor              | Description                   | Unit |
| ------------------- | ----------------------------- | ---- |
| Last Payment Amount | Amount of most recent payment | USD  |

### Account Status Sensors

| Sensor            | Description                      | Values |
| ----------------- | -------------------------------- | ------ |
| Auto Pay          | Auto-pay enrollment status       | On/Off |
| Net Metering      | Net metering account status      | Yes/No |
| Smart Meter (AMI) | Advanced metering infrastructure | Yes/No |
| Rate Category     | Rate plan code (e.g., VR-1)      | Text   |

### Weather Sensors

| Sensor                      | Description             | Unit   |
| --------------------------- | ----------------------- | ------ |
| Daily High Temperature      | Recent day's high temp  | °F     |
| Daily Low Temperature       | Recent day's low temp   | °F     |
| Heating Degree Days         | HDD for energy analysis | °F·day |
| Cooling Degree Days         | CDD for energy analysis | °F·day |
| Monthly Average Temperature | Month's average temp    | °F     |

### Meter Information Sensors

| Sensor         | Description               |
| -------------- | ------------------------- |
| Meter Number   | Full meter number         |
| Meter ID       | Internal meter identifier |
| Meter Type     | Meter type code           |
| Account Number | Full account number       |

## Energy Dashboard

To add this integration to your Energy Dashboard:

1. Go to **Settings** → **Dashboards** → **Energy**
2. Under "Grid consumption", click **Add consumption**
3. Select the "Dominion Energy Grid Consumption" sensor
4. Under "Return to grid" (for solar customers), click **Add return**
5. Select the "Dominion Energy Grid Return" sensor
6. Under "Solar panels" (for solar customers), click **Add production**
7. Select the "Dominion Energy Solar Generation" sensor

## API Endpoints Used

This integration uses multiple Dominion Energy API endpoints:

| API              | Base URL                      | Purpose                            |
| ---------------- | ----------------------------- | ---------------------------------- |
| Service API      | `/Service/api/1`              | Bill forecast, usage data, weather |
| Usage API        | `/Usageapi/api/V1`            | Monthly electric & generation data |
| Billing API      | `/BillingAPI/api/1`           | Current bill & billing history     |
| Account Mgmt API | `/AccountManagementapi/api/1` | Meter information                  |
| User Mgmt API    | `/UsermanagementAPI/api/1`    | Authentication & token refresh     |

## Troubleshooting

### Authentication Issues

- Ensure your username and password are correct
- Check that your account number matches what's on your bill (12 digits, with leading zeros)
- If TFA is enabled, make sure to complete the verification process
- The integration stores refresh tokens for autonomous operation after initial setup

### Data Not Updating

- Dominion Energy typically updates usage data once per day
- The integration polls for new data every 12 hours by default
- Check the Home Assistant logs for any error messages
- Daily data is usually available the next morning

### Missing Sensors

- Some sensors only appear for customers with specific features:
  - Solar generation sensors require a net metering account
  - Weather sensors require usage history data
- If sensors show "unavailable", the data may not be provided by your account type

### Rate Limiting

The integration is designed to poll infrequently to avoid rate limiting. If you experience issues, the integration will automatically retry with exponential backoff.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This integration is not affiliated with, endorsed by, or connected to Dominion Energy. Use at your own risk.
