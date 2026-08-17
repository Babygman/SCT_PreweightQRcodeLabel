from sqlalchemy.dialects import mssql

from app.auth.routes import _active_stations_statement
from app.auth.uat_bypass import _active_station_statement, _active_user_statement
from scripts.uat_master_detail import active_other_work_set_statement


def _mssql_sql(statement):
    return str(
        statement.compile(
            dialect=mssql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


def test_active_user_filter_compiles_for_sql_server_bit():
    sql = _mssql_sql(_active_user_statement("uat_admin"))
    assert "users.is_active = 1" in sql
    assert "users.is_active IS 1" not in sql


def test_active_station_filters_compile_for_sql_server_bit():
    bypass_sql = _mssql_sql(_active_station_statement("UAT-ST01"))
    selection_sql = _mssql_sql(_active_stations_statement())
    for sql in (bypass_sql, selection_sql):
        assert "stations.is_active = 1" in sql
        assert "stations.is_active IS 1" not in sql


def test_uat_work_set_filter_compiles_for_sql_server_bit():
    sql = _mssql_sql(active_other_work_set_statement(1))
    assert "production_orders.work_set_active = 1" in sql
    assert "production_orders.work_set_active IS 1" not in sql
