from threading import Lock
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from exceptions import AlpacaError, Success


# Thread-safe server transaction ID counter
_stid_lock = Lock()
_stid = 0


def get_next_transaction_id() -> int:
    global _stid
    with _stid_lock:
        _stid += 1
        return _stid


class StateValue(BaseModel):
    """Name/value pair for DeviceState property."""
    Name: str = Field(description="Property name")
    Value: Any = Field(description="Property value")


class AlpacaResponse(BaseModel):
    """Base response model for all Alpaca API responses."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    ClientTransactionID: int = Field(default=0)
    ServerTransactionID: int = Field(default=0)
    ErrorNumber: int = Field(default=0)
    ErrorMessage: str = Field(default="")

    @classmethod
    def create(
        cls,
        client_transaction_id: int = 0,
        error: Optional[AlpacaError] = None,
        **kwargs,
    ) -> "AlpacaResponse":
        err = error or Success()
        return cls(
            ClientTransactionID=client_transaction_id,
            ServerTransactionID=get_next_transaction_id(),
            ErrorNumber=err.Number,
            ErrorMessage=err.Message,
            **kwargs,
        )


class PropertyResponse(AlpacaResponse):
    """Response model for property GET requests."""
    Value: Optional[Any] = Field(default=None)

    @classmethod
    def create(
        cls,
        value: Any,
        client_transaction_id: int = 0,
        error: Optional[AlpacaError] = None,
    ) -> "PropertyResponse":
        err = error or Success()
        return cls(
            Value=value if err.Number == 0 else None,
            ClientTransactionID=client_transaction_id,
            ServerTransactionID=get_next_transaction_id(),
            ErrorNumber=err.Number,
            ErrorMessage=err.Message,
        )


class MethodResponse(AlpacaResponse):
    """Response model for method PUT requests."""
    Value: Optional[Any] = Field(default=None)

    @classmethod
    def create(
        cls,
        client_transaction_id: int = 0,
        error: Optional[AlpacaError] = None,
        value: Any = None,
    ) -> "MethodResponse":
        err = error or Success()
        return cls(
            Value=value if err.Number == 0 and value is not None else None,
            ClientTransactionID=client_transaction_id,
            ServerTransactionID=get_next_transaction_id(),
            ErrorNumber=err.Number,
            ErrorMessage=err.Message,
        )
