"""Config flow for Dominion Energy integration."""
from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DominionEnergyApi, DominionEnergyAuthError
from .const import CONF_ACCOUNT_NUMBER, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_ACCOUNT_NUMBER): str,
    }
)

STEP_TFA_SCHEMA = vol.Schema(
    {
        vol.Required("tfa_code"): str,
    }
)


class DominionEnergyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dominion Energy."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._username: str | None = None
        self._password: str | None = None
        self._account_number: str | None = None
        self._tfa_code: str | None = None
        self._tfa_event: threading.Event | None = None
        self._tfa_required: bool = False
        self._api: DominionEnergyApi | None = None
        self._auth_task: asyncio.Future | None = None

    def _get_tfa_code(self) -> str:
        """Callback to get TFA code - blocks until code is provided.
        
        This is called from a background thread during Selenium auth.
        """
        _LOGGER.info("TFA code requested, waiting for user input...")
        
        # Signal that TFA is required
        self._tfa_required = True
        
        # Wait for the TFA code to be provided (timeout after 5 minutes)
        if self._tfa_event:
            self._tfa_event.wait(timeout=300)
        
        code = self._tfa_code or ""
        _LOGGER.info("TFA code provided (length: %d)", len(code))
        return code

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Store credentials for potential TFA step
            self._username = user_input[CONF_USERNAME]
            self._password = user_input[CONF_PASSWORD]
            self._account_number = user_input[CONF_ACCOUNT_NUMBER]

            # Check if this account is already configured
            await self.async_set_unique_id(self._account_number)
            self._abort_if_unique_id_configured()

            # Set up TFA event for thread synchronization
            self._tfa_event = threading.Event()
            self._tfa_required = False
            self._tfa_code = None

            # Create API client
            session = async_get_clientsession(self.hass)
            self._api = DominionEnergyApi(
                username=self._username,
                password=self._password,
                account_number=self._account_number,
                session=session,
            )
            self._api.set_tfa_callback(self._get_tfa_code)

            try:
                # Start authentication - this may require TFA
                result = await self._try_authenticate()
                
                if result == "success":
                    return self.async_create_entry(
                        title=f"Dominion Energy ({self._account_number})",
                        data=user_input,
                    )
                elif result == "tfa_required":
                    # Show TFA form
                    return await self.async_step_tfa()
                else:
                    errors["base"] = "invalid_auth"
                    
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception during authentication")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def _try_authenticate(self) -> str:
        """Try to authenticate, detecting if TFA is required.
        
        Returns: "success", "tfa_required", or "failed"
        """
        loop = asyncio.get_event_loop()
        
        # Start authentication in executor (runs in thread pool)
        self._auth_task = loop.run_in_executor(
            None,
            self._authenticate_sync,
        )
        
        # Poll for completion or TFA requirement
        for _ in range(60):  # 30 seconds max for initial auth
            # Check if TFA was requested
            if self._tfa_required:
                _LOGGER.info("TFA is required")
                return "tfa_required"
            
            # Check if auth completed
            if self._auth_task.done():
                try:
                    result = self._auth_task.result()
                    return "success" if result else "failed"
                except Exception as err:
                    _LOGGER.error("Auth task error: %s", err)
                    return "failed"
            
            await asyncio.sleep(0.5)
        
        # Timeout
        _LOGGER.error("Authentication timed out")
        return "failed"

    def _authenticate_sync(self) -> bool:
        """Synchronous authentication wrapper for thread pool."""
        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self._api.authenticate())
            finally:
                loop.close()
        except DominionEnergyAuthError as err:
            _LOGGER.error("Auth error: %s", err)
            return False
        except Exception as err:
            _LOGGER.error("Unexpected auth error: %s", err)
            return False

    async def async_step_tfa(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle TFA verification step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # User provided TFA code
            self._tfa_code = user_input["tfa_code"]
            
            # Signal the waiting authentication thread
            if self._tfa_event:
                self._tfa_event.set()
            
            # Wait for authentication to complete
            if self._auth_task:
                try:
                    # Wait for auth to complete (should be quick after TFA)
                    for _ in range(60):  # 30 seconds
                        if self._auth_task.done():
                            break
                        await asyncio.sleep(0.5)
                    
                    if self._auth_task.done():
                        result = self._auth_task.result()
                        if result:
                            return self.async_create_entry(
                                title=f"Dominion Energy ({self._account_number})",
                                data={
                                    CONF_USERNAME: self._username,
                                    CONF_PASSWORD: self._password,
                                    CONF_ACCOUNT_NUMBER: self._account_number,
                                },
                            )
                        else:
                            errors["base"] = "invalid_tfa"
                    else:
                        errors["base"] = "timeout"
                        
                except Exception as err:
                    _LOGGER.error("TFA verification error: %s", err)
                    errors["base"] = "unknown"
            else:
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="tfa",
            data_schema=STEP_TFA_SCHEMA,
            errors=errors,
            description_placeholders={
                "email": self._username or "",
            },
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> FlowResult:
        """Handle reauthorization request."""
        self._username = entry_data.get(CONF_USERNAME)
        self._account_number = entry_data.get(CONF_ACCOUNT_NUMBER)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reauthorization confirmation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
            if entry:
                self._username = user_input[CONF_USERNAME]
                self._password = user_input[CONF_PASSWORD]
                self._account_number = entry.data[CONF_ACCOUNT_NUMBER]

                self._tfa_event = threading.Event()
                self._tfa_required = False
                self._tfa_code = None

                session = async_get_clientsession(self.hass)
                self._api = DominionEnergyApi(
                    username=self._username,
                    password=self._password,
                    account_number=self._account_number,
                    session=session,
                )
                self._api.set_tfa_callback(self._get_tfa_code)

                try:
                    result = await self._try_authenticate()
                    
                    if result == "success":
                        data = {
                            CONF_USERNAME: self._username,
                            CONF_PASSWORD: self._password,
                            CONF_ACCOUNT_NUMBER: self._account_number,
                        }
                        self.hass.config_entries.async_update_entry(entry, data=data)
                        await self.hass.config_entries.async_reload(entry.entry_id)
                        return self.async_abort(reason="reauth_successful")
                    elif result == "tfa_required":
                        return await self.async_step_reauth_tfa()
                    else:
                        errors["base"] = "invalid_auth"
                        
                except CannotConnect:
                    errors["base"] = "cannot_connect"
                except InvalidAuth:
                    errors["base"] = "invalid_auth"
                except Exception:
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=self._username): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth_tfa(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle TFA during reauth."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._tfa_code = user_input["tfa_code"]
            
            if self._tfa_event:
                self._tfa_event.set()
            
            if self._auth_task:
                try:
                    for _ in range(60):
                        if self._auth_task.done():
                            break
                        await asyncio.sleep(0.5)
                    
                    if self._auth_task.done() and self._auth_task.result():
                        entry = self.hass.config_entries.async_get_entry(
                            self.context["entry_id"]
                        )
                        if entry:
                            data = {
                                CONF_USERNAME: self._username,
                                CONF_PASSWORD: self._password,
                                CONF_ACCOUNT_NUMBER: self._account_number,
                            }
                            self.hass.config_entries.async_update_entry(entry, data=data)
                            await self.hass.config_entries.async_reload(entry.entry_id)
                            return self.async_abort(reason="reauth_successful")
                    errors["base"] = "invalid_tfa"
                except Exception:
                    errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reauth_tfa",
            data_schema=STEP_TFA_SCHEMA,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
