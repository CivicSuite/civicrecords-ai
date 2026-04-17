from typing import Annotated, Union
from pydantic import Field

from app.schemas.connectors.rest_api import RestApiConfig
from app.schemas.connectors.odbc import ODBCConfig

ConnectorConfig = Annotated[
    Union[RestApiConfig, ODBCConfig],
    Field(discriminator="connector_type"),
]

__all__ = ["ConnectorConfig", "RestApiConfig", "ODBCConfig"]
