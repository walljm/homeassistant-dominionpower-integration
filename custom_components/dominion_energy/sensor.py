"""Sensor platform for Dominion Energy integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import DominionEnergyData
from .const import (
    ATTRIBUTION,
    CONF_ACCOUNT_NUMBER,
    DOMAIN,
    SENSOR_BILLING_PERIOD_END,
    SENSOR_BILLING_PERIOD_START,
    SENSOR_CURRENT_BILL,
    SENSOR_CURRENT_RATE,
    SENSOR_DAILY_COST,
    SENSOR_GRID_CONSUMPTION,
    SENSOR_GRID_RETURN,
    SENSOR_MONTHLY_USAGE,
    SENSOR_SOLAR_GENERATION,
    SENSOR_BILL_DUE_DATE,
    SENSOR_PREVIOUS_BALANCE,
    SENSOR_PAYMENT_RECEIVED,
    SENSOR_REMAINING_BALANCE,
    SENSOR_RATE_CATEGORY,
    # New sensor constants
    SENSOR_TODAY_CONSUMPTION,
    SENSOR_TODAY_GENERATION,
    SENSOR_TODAY_NET_USAGE,
    SENSOR_TOTAL_AMOUNT_DUE,
    SENSOR_LAST_BILL_AMOUNT,
    SENSOR_LAST_BILL_USAGE,
    SENSOR_LAST_YEAR_BILL_AMOUNT,
    SENSOR_LAST_YEAR_USAGE,
    SENSOR_LAST_PAYMENT_DATE,
    SENSOR_LAST_PAYMENT_AMOUNT,
    SENSOR_NEXT_METER_READ_DATE,
    SENSOR_AUTO_PAY_ENABLED,
    SENSOR_IS_NET_METERING,
    SENSOR_IS_AMI_METER,
    SENSOR_DAILY_HIGH_TEMP,
    SENSOR_DAILY_LOW_TEMP,
    SENSOR_HEATING_DEGREE_DAYS,
    SENSOR_COOLING_DEGREE_DAYS,
    SENSOR_MONTHLY_AVG_TEMP,
    # Meter info sensors
    SENSOR_METER_NUMBER,
    SENSOR_METER_ID,
    SENSOR_METER_TYPE,
    SENSOR_ACCOUNT_NUMBER,
)
from .coordinator import DominionEnergyCoordinator


@dataclass(frozen=True, kw_only=True)
class DominionEnergySensorEntityDescription(SensorEntityDescription):
    """Describe Dominion Energy sensor entity."""

    value_fn: Callable[[DominionEnergyData], Any]


SENSOR_DESCRIPTIONS: tuple[DominionEnergySensorEntityDescription, ...] = (
    DominionEnergySensorEntityDescription(
        key=SENSOR_GRID_CONSUMPTION,
        translation_key="grid_consumption",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        icon="mdi:transmission-tower",
        value_fn=lambda data: data.grid_consumption,
    ),
    DominionEnergySensorEntityDescription(
        key=SENSOR_GRID_RETURN,
        translation_key="grid_return",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        icon="mdi:solar-power",
        value_fn=lambda data: data.grid_return,
    ),
    DominionEnergySensorEntityDescription(
        key=SENSOR_MONTHLY_USAGE,
        translation_key="monthly_usage",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=1,
        icon="mdi:chart-histogram",
        value_fn=lambda data: data.monthly_usage,
    ),
    DominionEnergySensorEntityDescription(
        key=SENSOR_CURRENT_BILL,
        translation_key="current_bill",
        native_unit_of_measurement="USD",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        icon="mdi:currency-usd",
        value_fn=lambda data: data.current_bill,
    ),
    DominionEnergySensorEntityDescription(
        key=SENSOR_DAILY_COST,
        translation_key="daily_cost",
        native_unit_of_measurement="USD",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:cash-clock",
        value_fn=lambda data: data.daily_cost,
    ),
    DominionEnergySensorEntityDescription(
        key=SENSOR_CURRENT_RATE,
        translation_key="current_rate",
        native_unit_of_measurement="USD/kWh",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        icon="mdi:cash-multiple",
        value_fn=lambda data: data.current_rate,
    ),
    DominionEnergySensorEntityDescription(
        key=SENSOR_BILLING_PERIOD_START,
        translation_key="billing_period_start",
        device_class=SensorDeviceClass.DATE,
        icon="mdi:calendar-start",
        value_fn=lambda data: data.billing_period_start.date() if data.billing_period_start else None,
    ),
    DominionEnergySensorEntityDescription(
        key=SENSOR_BILLING_PERIOD_END,
        translation_key="billing_period_end",
        device_class=SensorDeviceClass.DATE,
        icon="mdi:calendar-end",
        value_fn=lambda data: data.billing_period_end.date() if data.billing_period_end else None,
    ),
    DominionEnergySensorEntityDescription(
        key=SENSOR_SOLAR_GENERATION,
        translation_key="solar_generation",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=1,
        icon="mdi:solar-power-variant",
        value_fn=lambda data: data.solar_generation,
    ),
    DominionEnergySensorEntityDescription(
        key=SENSOR_BILL_DUE_DATE,
        translation_key="bill_due_date",
        device_class=SensorDeviceClass.DATE,
        icon="mdi:calendar-alert",
        value_fn=lambda data: data.bill_due_date.date() if data.bill_due_date else None,
    ),
    DominionEnergySensorEntityDescription(
        key=SENSOR_PREVIOUS_BALANCE,
        translation_key="previous_balance",
        native_unit_of_measurement="USD",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        icon="mdi:history",
        value_fn=lambda data: data.previous_balance,
    ),
    DominionEnergySensorEntityDescription(
        key=SENSOR_PAYMENT_RECEIVED,
        translation_key="payment_received",
        native_unit_of_measurement="USD",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        icon="mdi:cash-check",
        value_fn=lambda data: data.payment_received,
    ),
    DominionEnergySensorEntityDescription(
        key=SENSOR_REMAINING_BALANCE,
        translation_key="remaining_balance",
        native_unit_of_measurement="USD",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        icon="mdi:cash-minus",
        value_fn=lambda data: data.remaining_balance,
    ),
    DominionEnergySensorEntityDescription(
        key=SENSOR_RATE_CATEGORY,
        translation_key="rate_category",
        icon="mdi:tag-text",
        value_fn=lambda data: data.rate_category,
    ),
    # Today's usage sensors
    DominionEnergySensorEntityDescription(
        key=SENSOR_TODAY_CONSUMPTION,
        translation_key="today_consumption",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        icon="mdi:lightning-bolt",
        value_fn=lambda data: data.today_consumption,
    ),
    DominionEnergySensorEntityDescription(
        key=SENSOR_TODAY_GENERATION,
        translation_key="today_generation",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        icon="mdi:solar-power",
        value_fn=lambda data: data.today_generation,
    ),
    DominionEnergySensorEntityDescription(
        key=SENSOR_TODAY_NET_USAGE,
        translation_key="today_net_usage",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        icon="mdi:home-lightning-bolt",
        value_fn=lambda data: data.today_net_usage,
    ),
    # Billing comparison sensors
    DominionEnergySensorEntityDescription(
        key=SENSOR_TOTAL_AMOUNT_DUE,
        translation_key="total_amount_due",
        native_unit_of_measurement="USD",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        icon="mdi:cash",
        value_fn=lambda data: data.total_amount_due,
    ),
    DominionEnergySensorEntityDescription(
        key=SENSOR_LAST_BILL_AMOUNT,
        translation_key="last_bill_amount",
        native_unit_of_measurement="USD",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        icon="mdi:receipt-text",
        value_fn=lambda data: data.last_bill_amount,
    ),
    DominionEnergySensorEntityDescription(
        key=SENSOR_LAST_BILL_USAGE,
        translation_key="last_bill_usage",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=1,
        icon="mdi:chart-bar",
        value_fn=lambda data: data.last_bill_usage,
    ),
    DominionEnergySensorEntityDescription(
        key=SENSOR_LAST_YEAR_BILL_AMOUNT,
        translation_key="last_year_bill_amount",
        native_unit_of_measurement="USD",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        icon="mdi:calendar-clock",
        value_fn=lambda data: data.last_year_bill_amount,
    ),
    DominionEnergySensorEntityDescription(
        key=SENSOR_LAST_YEAR_USAGE,
        translation_key="last_year_usage",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=1,
        icon="mdi:chart-timeline-variant",
        value_fn=lambda data: data.last_year_usage,
    ),
    # Payment sensors
    DominionEnergySensorEntityDescription(
        key=SENSOR_LAST_PAYMENT_DATE,
        translation_key="last_payment_date",
        device_class=SensorDeviceClass.DATE,
        icon="mdi:calendar-check",
        value_fn=lambda data: data.last_payment_date.date() if data.last_payment_date else None,
    ),
    DominionEnergySensorEntityDescription(
        key=SENSOR_LAST_PAYMENT_AMOUNT,
        translation_key="last_payment_amount",
        native_unit_of_measurement="USD",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        icon="mdi:cash-check",
        value_fn=lambda data: data.last_payment_amount,
    ),
    # Account status sensors
    DominionEnergySensorEntityDescription(
        key=SENSOR_NEXT_METER_READ_DATE,
        translation_key="next_meter_read_date",
        device_class=SensorDeviceClass.DATE,
        icon="mdi:calendar-clock",
        value_fn=lambda data: data.next_meter_read_date.date() if data.next_meter_read_date else None,
    ),
    DominionEnergySensorEntityDescription(
        key=SENSOR_AUTO_PAY_ENABLED,
        translation_key="auto_pay_enabled",
        icon="mdi:credit-card-check",
        value_fn=lambda data: "On" if data.auto_pay_enabled else "Off" if data.auto_pay_enabled is not None else None,
    ),
    DominionEnergySensorEntityDescription(
        key=SENSOR_IS_NET_METERING,
        translation_key="is_net_metering",
        icon="mdi:solar-panel-large",
        value_fn=lambda data: "Yes" if data.is_net_metering else "No" if data.is_net_metering is not None else None,
    ),
    DominionEnergySensorEntityDescription(
        key=SENSOR_IS_AMI_METER,
        translation_key="is_ami_meter",
        icon="mdi:meter-electric",
        value_fn=lambda data: "Yes" if data.is_ami_meter else "No" if data.is_ami_meter is not None else None,
    ),
    # Weather sensors
    DominionEnergySensorEntityDescription(
        key=SENSOR_DAILY_HIGH_TEMP,
        translation_key="daily_high_temp",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer-high",
        value_fn=lambda data: data.daily_high_temp,
    ),
    DominionEnergySensorEntityDescription(
        key=SENSOR_DAILY_LOW_TEMP,
        translation_key="daily_low_temp",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer-low",
        value_fn=lambda data: data.daily_low_temp,
    ),
    DominionEnergySensorEntityDescription(
        key=SENSOR_HEATING_DEGREE_DAYS,
        translation_key="heating_degree_days",
        native_unit_of_measurement="°F·day",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:snowflake-thermometer",
        value_fn=lambda data: data.heating_degree_days,
    ),
    DominionEnergySensorEntityDescription(
        key=SENSOR_COOLING_DEGREE_DAYS,
        translation_key="cooling_degree_days",
        native_unit_of_measurement="°F·day",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:sun-thermometer",
        value_fn=lambda data: data.cooling_degree_days,
    ),
    DominionEnergySensorEntityDescription(
        key=SENSOR_MONTHLY_AVG_TEMP,
        translation_key="monthly_avg_temp",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
        value_fn=lambda data: data.monthly_avg_temp,
    ),
    # Meter info sensors
    DominionEnergySensorEntityDescription(
        key=SENSOR_METER_NUMBER,
        translation_key="meter_number",
        icon="mdi:counter",
        value_fn=lambda data: data.meter_number,
    ),
    DominionEnergySensorEntityDescription(
        key=SENSOR_METER_ID,
        translation_key="meter_id",
        icon="mdi:identifier",
        value_fn=lambda data: data.meter_id,
    ),
    DominionEnergySensorEntityDescription(
        key=SENSOR_METER_TYPE,
        translation_key="meter_type",
        icon="mdi:meter-electric-outline",
        value_fn=lambda data: data.meter_type,
    ),
    DominionEnergySensorEntityDescription(
        key=SENSOR_ACCOUNT_NUMBER,
        translation_key="account_number_sensor",
        icon="mdi:account-details",
        value_fn=lambda data: data.account_number,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dominion Energy sensors based on a config entry."""
    coordinator: DominionEnergyCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        DominionEnergySensor(coordinator, description, entry)
        for description in SENSOR_DESCRIPTIONS
    )


class DominionEnergySensor(
    CoordinatorEntity[DominionEnergyCoordinator], SensorEntity
):
    """Representation of a Dominion Energy sensor."""

    entity_description: DominionEnergySensorEntityDescription
    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DominionEnergyCoordinator,
        description: DominionEnergySensorEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.data[CONF_ACCOUNT_NUMBER]}_{description.key}"
        
        account_number = entry.data[CONF_ACCOUNT_NUMBER]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, account_number)},
            name=f"Dominion Energy {account_number}",
            manufacturer="Dominion Energy",
            model="Utility Account",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not super().available:
            return False
        if self.coordinator.data is None:
            return False
        # Check if this specific value is available
        value = self.entity_description.value_fn(self.coordinator.data)
        return value is not None
