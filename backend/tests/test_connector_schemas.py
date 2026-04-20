import pytest
from pydantic import ValidationError
from app.schemas.connectors.rest_api import RestApiConfig
from app.schemas.connectors.odbc import ODBCConfig
from app.schemas.connectors import ConnectorConfig


class TestRestApiConfig:
    def test_defaults(self):
        cfg = RestApiConfig(
            base_url="https://api.example.gov",
            endpoint_path="/records",
            auth_method="none",
        )
        assert cfg.pagination_style == "none"
        assert cfg.max_records == 10_000
        assert cfg.connector_type == "rest_api"

    def test_cursor_pagination_requires_json(self):
        with pytest.raises(ValidationError, match="pagination_style='cursor' requires response_format='json'"):
            RestApiConfig(
                base_url="https://api.example.gov",
                endpoint_path="/records",
                auth_method="none",
                pagination_style="cursor",
                response_format="csv",
            )

    def test_cursor_pagination_with_json_is_valid(self):
        cfg = RestApiConfig(
            base_url="https://api.example.gov",
            endpoint_path="/records",
            auth_method="none",
            pagination_style="cursor",
            response_format="json",
        )
        assert cfg.pagination_style == "cursor"


class TestODBCConfig:
    def test_valid_config(self):
        cfg = ODBCConfig(
            connection_string="Server=db.example.gov;Database=test",
            table_name="public_records",
            pk_column="id",
        )
        assert cfg.connector_type == "odbc"
        assert cfg.batch_size == 500

    def test_invalid_table_name_rejects_sql_injection(self):
        with pytest.raises(ValidationError):
            ODBCConfig(
                connection_string="Server=db.example.gov;Database=test",
                table_name="records; DROP TABLE users--",
                pk_column="id",
            )

    def test_invalid_pk_column(self):
        with pytest.raises(ValidationError):
            ODBCConfig(
                connection_string="Server=db.example.gov;Database=test",
                table_name="records",
                pk_column="1invalid",
            )

    def test_modified_column_none_is_valid(self):
        cfg = ODBCConfig(
            connection_string="Server=db.example.gov;Database=test",
            table_name="records",
            pk_column="id",
            modified_column=None,
        )
        assert cfg.modified_column is None


class TestConnectorConfigDiscriminatedUnion:
    def test_parse_rest_api(self):
        from pydantic import TypeAdapter
        adapter = TypeAdapter(ConnectorConfig)
        cfg = adapter.validate_python({
            "connector_type": "rest_api",
            "base_url": "https://api.example.gov",
            "endpoint_path": "/records",
            "auth_method": "none",
        })
        assert isinstance(cfg, RestApiConfig)

    def test_parse_odbc(self):
        from pydantic import TypeAdapter
        adapter = TypeAdapter(ConnectorConfig)
        cfg = adapter.validate_python({
            "connector_type": "odbc",
            "connection_string": "Server=db.example.gov;Database=test",
            "table_name": "records",
            "pk_column": "id",
        })
        assert isinstance(cfg, ODBCConfig)
