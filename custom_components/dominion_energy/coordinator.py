"""DataUpdateCoordinator for Dominion Energy."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    DominionEnergyApi,
    DominionEnergyApiError,
    DominionEnergyAuthError,
    DominionEnergyData,
)
from .const import CONF_ACCOUNT_NUMBER, DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class DominionEnergyCoordinator(DataUpdateCoordinator[DominionEnergyData]):
    """Class to manage fetching Dominion Energy data."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        self.config_entry = entry
        self._api: DominionEnergyApi | None = None
        self._account_number = entry.data[CONF_ACCOUNT_NUMBER]
        self._statistic_id_consumption = f"{DOMAIN}:energy_consumption_{self._account_number}"
        self._statistic_id_return = f"{DOMAIN}:energy_return_{self._account_number}"
        self._session_restored = False

    @property
    def api(self) -> DominionEnergyApi:
        """Get the API client, creating it if necessary."""
        if self._api is None:
            session = async_get_clientsession(self.hass)
            self._api = DominionEnergyApi(
                username=self.config_entry.data[CONF_USERNAME],
                password=self.config_entry.data[CONF_PASSWORD],
                account_number=self.config_entry.data[CONF_ACCOUNT_NUMBER],
                session=session,
            )
            # Restore saved session data if available
            if not self._session_restored:
                self._restore_session()
        return self._api

    def _restore_session(self) -> None:
        """Restore session data from config entry."""
        self._session_restored = True
        session_data = self.config_entry.data.get("session_data")
        if session_data and self._api:
            _LOGGER.debug("Restoring saved session data")
            self._api.restore_session_data(session_data)

    async def _save_session(self) -> None:
        """Save session data to config entry."""
        if self._api is None:
            return
        
        session_data = self._api.get_session_data()
        if not session_data:
            return
        
        # Only update if session data changed
        current_session = self.config_entry.data.get("session_data", {})
        if session_data != current_session:
            _LOGGER.debug("Saving session data to config entry")
            new_data = {**self.config_entry.data, "session_data": session_data}
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=new_data,
            )

    async def _async_update_data(self) -> DominionEnergyData:
        """Fetch data from Dominion Energy API."""
        try:
            # Authenticate if we don't have a token
            await self.api.authenticate()
            
            # Save session data after successful authentication
            await self._save_session()
            
            # Fetch all data
            data = await self.api.get_all_data()
            
            _LOGGER.debug(
                "Fetched Dominion Energy data: consumption=%s kWh, return=%s kWh, bill=$%s",
                data.grid_consumption,
                data.grid_return,
                data.current_bill,
            )

            # Insert historical statistics
            await self._insert_statistics(data)
            
            return data

        except DominionEnergyAuthError as err:
            # Trigger reauth flow
            raise ConfigEntryAuthFailed(
                f"Authentication failed: {err}"
            ) from err
        except DominionEnergyApiError as err:
            raise UpdateFailed(f"Error communicating with Dominion Energy: {err}") from err

    async def _insert_statistics(self, data: DominionEnergyData) -> None:
        """Insert historical statistics."""
        if not data.daily_usage and not data.daily_return:
            return

        # Process consumption
        if data.daily_usage:
            await self._process_statistics(
                self._statistic_id_consumption,
                "Grid Consumption",
                data.daily_usage,
                "usage",  # Key for usage value
            )

        # Process return
        if data.daily_return:
            await self._process_statistics(
                self._statistic_id_return,
                "Grid Return",
                data.daily_return,
                "return",  # Key for return value (guess, will adjust if needed)
            )

    async def _process_statistics(
        self,
        statistic_id: str,
        name: str,
        daily_data: list[dict],
        value_key: str,
    ) -> None:
        """Process and insert statistics for a specific metric."""
        metadata = StatisticMetaData(
            has_mean=False,
            has_sum=True,
            name=name,
            source=DOMAIN,
            statistic_id=statistic_id,
            unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        )

        # Get last statistic to calculate cumulative sum
        last_stats = await get_instance(self.hass).async_add_executor_job(
            get_last_statistics, self.hass, 1, statistic_id, True, {"sum"}
        )
        
        last_sum = 0.0
        last_start = None
        
        if statistic_id in last_stats and last_stats[statistic_id]:
            last_stat = last_stats[statistic_id][0]
            last_sum = last_stat.get("sum") or 0.0
            last_start = datetime.fromtimestamp(last_stat["start"], tz=dt_util.UTC)

        statistics = []
        
        # Sort data by date to ensure correct order
        # We assume the API returns a 'date' field in YYYY-MM-DD format
        # If keys are different, we might need to adjust.
        # Based on typical APIs, we look for 'date' or 'usageDate'.
        
        sorted_data = []
        for item in daily_data:
            date_str = item.get("date") or item.get("usageDate")
            if not date_str:
                continue
            try:
                date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
                sorted_data.append((date, item))
            except ValueError:
                continue
        
        sorted_data.sort(key=lambda x: x[0])

        for date, item in sorted_data:
            # Skip if we already have this data point (based on start time)
            # Note: This is a simple check. Ideally we check if the date is > last_start
            if last_start and date <= last_start:
                continue

            # Get value
            # Try multiple common keys if the specific one fails
            value = item.get(value_key)
            if value is None:
                value = item.get("value") or item.get("kwh") or item.get("quantity")
            
            if value is None:
                continue
                
            try:
                value = float(value)
            except (ValueError, TypeError):
                continue

            last_sum += value
            
            statistics.append(
                StatisticData(
                    start=date,
                    sum=last_sum,
                    state=value,
                )
            )

        if statistics:
            _LOGGER.debug("Inserting %s statistics for %s", len(statistics), statistic_id)
            async_add_external_statistics(self.hass, metadata, statistics)

