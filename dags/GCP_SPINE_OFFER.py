from airflow import DAG
from airflow.contrib.operators.bigquery_operator import (
    BigQueryOperator,
    BigQueryCheckOperator,
)
from airflow.contrib.operators.gcs_to_bq import GoogleCloudStorageToBigQueryOperator
from airflow.operators.dummy_operator import DummyOperator
from airflow.sensors.external_task import ExternalTaskSensor
from datetime import datetime, timedelta


dataset_source = "uk_arc_chordiant_is"
dataset_staging = "uk_pre_customer_spine_offer_is"
dataset_publish = "uk_pub_customer_spine_offer_is"
gs_source_bucket = "uk_customer_tds_is"


default_args = {
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 5,
    "retry_delay": timedelta(seconds=60),
    "priority_weight": 10,
    "wait_for_downstream": False,
    "sla": timedelta(seconds=7200),
    "execution_timeout": timedelta(seconds=300),
    "owner": "customerbtprod",
    "email": ["sean.conkie@sky.uk"],
}

with DAG(
    "GCP_SPINE_OFFER",
    concurrency=10,
    max_active_runs=1,
    default_args=default_args,
    schedule_interval=None,
    start_date=datetime.now(),
    catchup=False,
    description="Populates portfolio offer tables uk_pub_customer_spine_offer_is",
    tags=["offer", "customer"],
) as dag:

    start_pipeline = DummyOperator(task_id="start_pipeline", dag=dag)

    load_teams = GoogleCloudStorageToBigQueryOperator(
        task_id="load_teams",
        bucket=f"""{gs_source_bucket}""",
        destination_dataset_table=f"""{dataset_source}.arc_teams""",
        write_disposition=f"""WRITE_APPEND""",
        create_disposition=f"""CREATE_IF_NEEDED""",
        source_objects=["team*.json"],
        source_format=f"""NEWLINE_DELIMITED_JSON""",
        field_delimiter=f""",""",
        skip_leading_rows=1,
        schema_object=f"""schema/arc_team.json""",
        dag=dag,
    )
    delta_table = BigQueryOperator(
        task_id="delta_table",
        sql=f"""dags/sql/delta_table.sql""",
        destination_dataset_table=f"""{dataset_publish}.dim_delta""",
        write_disposition=f"""WRITE_TRUNCATE""",
        create_disposition=f"""CREATE_IF_NEEDED""",
        allow_large_results=True,
        use_legacy_sql=False,
        params={"dataset_publish": "f'{dataset_publish}'"},
        dag=dag,
    )
    dim_offer_type = BigQueryOperator(
        task_id="dim_offer_type",
        sql=f"""dags/sql/dim_offer_type.sql""",
        destination_dataset_table=f"""{dataset_publish}.dim_offer_type""",
        write_disposition=f"""WRITE_TRUNCATE""",
        create_disposition=f"""CREATE_IF_NEEDED""",
        allow_large_results=True,
        use_legacy_sql=False,
        params={"dataset_publish": "f'{dataset_publish}'"},
        dag=dag,
    )
    td_offer_status_core = BigQueryOperator(
        task_id="td_offer_status_core",
        sql=f"""dags/sql/td_offer_status_core.sql""",
        destination_dataset_table=f"""uk_pre_customer_spine_offer_is.td_offer_status_core""",
        write_disposition=f"""WRITE_TRUNCATE""",
        create_disposition=f"""CREATE_IF_NEEDED""",
        allow_large_results=True,
        use_legacy_sql=False,
        params={"dataset_publish": "uk_pre_customer_spine_offer_is"},
        dag=dag,
    )
    td_offer_priceable_unit_core = BigQueryOperator(
        task_id="td_offer_priceable_unit_core",
        sql=f"""dags/sql/td_offer_priceable_unit_core.sql""",
        destination_dataset_table=f"""uk_pre_customer_spine_offer_is.td_offer_priceable_unit_core""",
        write_disposition=f"""WRITE_TRUNCATE""",
        create_disposition=f"""CREATE_IF_NEEDED""",
        allow_large_results=True,
        use_legacy_sql=False,
        params={"dataset_publish": "uk_pre_customer_spine_offer_is"},
        dag=dag,
    )
    td_offer_priceable_unit_soip = BigQueryOperator(
        task_id="td_offer_priceable_unit_soip",
        sql=f"""sql/spine_offer_td_offer_priceable_unit_soip.sql""",
        destination_dataset_table=f"""uk_pre_customer_spine_offer_is.td_offer_priceable_unit_soip""",
        write_disposition=f"""WRITE_TRUNCATE""",
        create_disposition=f"""CREATE_IF_NEEDED""",
        allow_large_results=True,
        use_legacy_sql=False,
        params={"dataset_publish": "uk_pre_customer_spine_offer_is"},
        dag=dag,
    )
    truncate_dim_offer_priceable_unit = BigQueryOperator(
        task_id="truncate_dim_offer_priceable_unit",
        sql=f"""truncate table uk_pub_customer_spine_offer_is.dim_offer_priceable_unit;""",
        destination_dataset_table=f"""{dataset_publish}.dim_offer_priceable_unit""",
        write_disposition=f"""WRITE_TRUNCATE""",
        create_disposition=f"""CREATE_IF_NEEDED""",
        allow_large_results=True,
        use_legacy_sql=False,
        params={"dataset_publish": "f'{dataset_publish}'"},
        dag=dag,
    )
    dim_offer_priceable_unit_core = BigQueryOperator(
        task_id="dim_offer_priceable_unit_core",
        sql=f"""dags/sql/dim_offer_priceable_unit_core.sql""",
        destination_dataset_table=f"""{dataset_publish}.dim_offer_priceable_unit""",
        write_disposition=f"""WRITE_APPEND""",
        create_disposition=f"""CREATE_IF_NEEDED""",
        allow_large_results=True,
        use_legacy_sql=False,
        params={"dataset_publish": "f'{dataset_publish}'"},
        dag=dag,
    )
    dim_offer_priceable_unit_soip = BigQueryOperator(
        task_id="dim_offer_priceable_unit_soip",
        sql=f"""dags/sql/dim_offer_priceable_unit_soip.sql""",
        destination_dataset_table=f"""{dataset_publish}.dim_offer_priceable_unit""",
        write_disposition=f"""WRITE_APPEND""",
        create_disposition=f"""CREATE_IF_NEEDED""",
        allow_large_results=True,
        use_legacy_sql=False,
        params={"dataset_publish": "f'{dataset_publish}'"},
        dag=dag,
    )
    dim_offer_priceable_unit_data_check_row_count = BigQueryCheckOperator(
        task_id="dim_offer_priceable_unit_data_check_row_count",
        sql=f"""select count(*) from uk_pub_customer_spine_offer_is.dim_offer_priceable_unit""",
        dag=dag,
    )
    dim_offer_priceable_unit_data_check_duplicate_records = BigQueryCheckOperator(
        task_id="dim_offer_priceable_unit_data_check_duplicate_records",
        sql=f"""sql/data_check_duplicate_records.sql""",
        params={
            "DATASET_ID": "uk_pub_customer_spine_offer_is",
            "FROM": "dim_offer_priceable_unit",
            "KEY": "['id']",
        },
        dag=dag,
    )
    td_offer_discount_core_pt1 = BigQueryOperator(
        task_id="td_offer_discount_core_pt1",
        sql=f"""sql/spine_offer_td_offer_discount_1.sql""",
        destination_dataset_table=f"""uk_pre_customer_spine_offer_is.td_offer_discount_core_pt1""",
        write_disposition=f"""WRITE_TRUNCATE""",
        create_disposition=f"""CREATE_IF_NEEDED""",
        allow_large_results=True,
        use_legacy_sql=False,
        params={"dataset_publish": "uk_pre_customer_spine_offer_is"},
        dag=dag,
    )
    td_offer_discount_core_pt2 = BigQueryOperator(
        task_id="td_offer_discount_core_pt2",
        sql=f"""sql/spine_offer_td_offer_discount_2.sql""",
        destination_dataset_table=f"""uk_pre_customer_spine_offer_is.td_offer_discount_core_pt2""",
        write_disposition=f"""WRITE_TRUNCATE""",
        create_disposition=f"""CREATE_IF_NEEDED""",
        allow_large_results=True,
        use_legacy_sql=False,
        params={"dataset_publish": "uk_pre_customer_spine_offer_is"},
        dag=dag,
    )
    td_offer_discount_soip = BigQueryOperator(
        task_id="td_offer_discount_soip",
        sql=f"""sql/spine_offer_td_offer_discount_soip.sql""",
        destination_dataset_table=f"""uk_pre_customer_spine_offer_is.td_offer_discount_soip""",
        write_disposition=f"""WRITE_TRUNCATE""",
        create_disposition=f"""CREATE_IF_NEEDED""",
        allow_large_results=True,
        use_legacy_sql=False,
        params={"dataset_publish": "uk_pre_customer_spine_offer_is"},
        dag=dag,
    )
    dim_offer_discount = BigQueryOperator(
        task_id="dim_offer_discount",
        sql=f"""sql/spine_offer_dim_offer_discount.sql""",
        destination_dataset_table=f"""{dataset_publish}.dim_offer_discount""",
        write_disposition=f"""WRITE_TRUNCATE""",
        create_disposition=f"""CREATE_IF_NEEDED""",
        allow_large_results=True,
        use_legacy_sql=False,
        params={"dataset_publish": "f'{dataset_publish}'"},
        dag=dag,
    )
    td_offer_status_soip = BigQueryOperator(
        task_id="td_offer_status_soip",
        sql=f"""sql/spine_offer_td_offer_status_soip.sql""",
        destination_dataset_table=f"""uk_pre_customer_spine_offer_is.td_offer_status_soip""",
        write_disposition=f"""WRITE_TRUNCATE""",
        create_disposition=f"""CREATE_IF_NEEDED""",
        allow_large_results=True,
        use_legacy_sql=False,
        params={"dataset_publish": "uk_pre_customer_spine_offer_is"},
        dag=dag,
    )
    ext_task_one = ExternalTaskSensor(
        task_id="ext_task_one",
        external_dag_id=f"""another_dag""",
        external_task_id=f"""task_one""",
        check_existence=True,
        timeout=600,
        allowed_states=["success"],
        failed_states=["failed", "skipped"],
        mode=f"""reschedule""",
        dag=dag,
    )
    dim_offer_status = BigQueryOperator(
        task_id="dim_offer_status",
        sql=f"""sql/spine_offer_dim_offer_status.sql""",
        destination_dataset_table=f"""{dataset_publish}.dim_offer_status""",
        write_disposition=f"""WRITE_TRUNCATE""",
        create_disposition=f"""CREATE_IF_NEEDED""",
        allow_large_results=True,
        use_legacy_sql=False,
        params={"dataset_publish": "f'{dataset_publish}'"},
        dag=dag,
    )
    dim_offer_status_data_check_new_value_status_code = BigQueryCheckOperator(
        task_id="dim_offer_status_data_check_new_value_status_code",
        sql=f"""sql/data_check_new_value.sql""",
        params={
            "DATASET_ID": "uk_pub_customer_spine_offer_is",
            "FROM": "dim_offer_status",
            "CHECK_FIELD": "status_code",
            "DATE_FIELD": "effective_from_dt",
        },
        dag=dag,
    )
    dim_offer_status_data_check_new_value_reason_code = BigQueryCheckOperator(
        task_id="dim_offer_status_data_check_new_value_reason_code",
        sql=f"""sql/data_check_new_value.sql""",
        params={
            "DATASET_ID": "uk_pub_customer_spine_offer_is",
            "FROM": "dim_offer_status",
            "CHECK_FIELD": "reason_code",
            "DATE_FIELD": "effective_from_dt",
        },
        dag=dag,
    )
    dim_delta_data_check_row_count = BigQueryCheckOperator(
        task_id="dim_delta_data_check_row_count",
        sql=f"""select count(*) from uk_pub_customer_spine_offer_is.dim_delta""",
        dag=dag,
    )
    dim_delta_data_check_duplicate_records = BigQueryCheckOperator(
        task_id="dim_delta_data_check_duplicate_records",
        sql=f"""sql/data_check_duplicate_records.sql""",
        params={
            "DATASET_ID": "uk_pub_customer_spine_offer_is",
            "FROM": "dim_delta",
            "KEY": "id",
        },
        dag=dag,
    )
    dim_offer_type_data_check_row_count = BigQueryCheckOperator(
        task_id="dim_offer_type_data_check_row_count",
        sql=f"""select count(*) from uk_pub_customer_spine_offer_is.dim_offer_type""",
        dag=dag,
    )
    dim_offer_type_data_check_duplicate_records = BigQueryCheckOperator(
        task_id="dim_offer_type_data_check_duplicate_records",
        sql=f"""sql/data_check_duplicate_records.sql""",
        params={
            "DATASET_ID": "uk_pub_customer_spine_offer_is",
            "FROM": "dim_offer_type",
            "KEY": "id",
        },
        dag=dag,
    )
    dim_offer_discount_data_check_row_count = BigQueryCheckOperator(
        task_id="dim_offer_discount_data_check_row_count",
        sql=f"""select count(*) from uk_pub_customer_spine_offer_is.dim_offer_discount""",
        dag=dag,
    )
    dim_offer_discount_data_check_duplicate_records = BigQueryCheckOperator(
        task_id="dim_offer_discount_data_check_duplicate_records",
        sql=f"""sql/data_check_duplicate_records.sql""",
        params={
            "DATASET_ID": "uk_pub_customer_spine_offer_is",
            "FROM": "dim_offer_discount",
            "KEY": "portfolio_offer_id, effective_from_dt",
        },
        dag=dag,
    )
    dim_offer_discount_data_check_open_history_items = BigQueryCheckOperator(
        task_id="dim_offer_discount_data_check_open_history_items",
        sql=f"""sql/data_check_open_history_items.sql""",
        params={
            "DATASET_ID": "uk_pub_customer_spine_offer_is",
            "FROM": "dim_offer_discount",
            "KEY": "portfolio_offer_id",
        },
        dag=dag,
    )
    dim_offer_status_data_check_row_count = BigQueryCheckOperator(
        task_id="dim_offer_status_data_check_row_count",
        sql=f"""select count(*) from uk_pub_customer_spine_offer_is.dim_offer_status""",
        dag=dag,
    )
    dim_offer_status_data_check_duplicate_records = BigQueryCheckOperator(
        task_id="dim_offer_status_data_check_duplicate_records",
        sql=f"""sql/data_check_duplicate_records.sql""",
        params={
            "DATASET_ID": "uk_pub_customer_spine_offer_is",
            "FROM": "dim_offer_status",
            "KEY": "portfolio_offer_id, effective_from_dt, effective_from_dt_csn_seq, effective_from_dt_seq, status_code, reason_code",
        },
        dag=dag,
    )
    dim_offer_status_data_check_open_history_items = BigQueryCheckOperator(
        task_id="dim_offer_status_data_check_open_history_items",
        sql=f"""sql/data_check_open_history_items.sql""",
        params={
            "DATASET_ID": "uk_pub_customer_spine_offer_is",
            "FROM": "dim_offer_status",
            "KEY": "portfolio_offer_id",
        },
        dag=dag,
    )

    finish_pipeline = DummyOperator(task_id="finish_pipeline", trigger_ruke="all_done")

    # Define task dependencies
    start_pipeline >> load_teams
    start_pipeline >> delta_table
    start_pipeline >> dim_offer_type
    start_pipeline >> td_offer_status_core
    start_pipeline >> td_offer_priceable_unit_core
    start_pipeline >> td_offer_priceable_unit_soip
    td_offer_priceable_unit_soip >> truncate_dim_offer_priceable_unit
    td_offer_priceable_unit_core >> truncate_dim_offer_priceable_unit
    truncate_dim_offer_priceable_unit >> dim_offer_priceable_unit_core
    truncate_dim_offer_priceable_unit >> dim_offer_priceable_unit_soip
    dim_offer_priceable_unit_soip >> dim_offer_priceable_unit_data_check_row_count
    dim_offer_priceable_unit_core >> dim_offer_priceable_unit_data_check_row_count
    (
        dim_offer_priceable_unit_soip
        >> dim_offer_priceable_unit_data_check_duplicate_records
    )
    (
        dim_offer_priceable_unit_core
        >> dim_offer_priceable_unit_data_check_duplicate_records
    )
    start_pipeline >> td_offer_discount_core_pt1
    td_offer_discount_core_pt1 >> td_offer_discount_core_pt2
    start_pipeline >> td_offer_discount_soip
    td_offer_discount_core_pt2 >> dim_offer_discount
    td_offer_discount_soip >> dim_offer_discount
    start_pipeline >> ext_task_one
    ext_task_one >> td_offer_status_soip
    td_offer_status_core >> dim_offer_status
    td_offer_status_soip >> dim_offer_status
    dim_offer_status >> dim_offer_status_data_check_new_value_status_code
    dim_offer_status >> dim_offer_status_data_check_new_value_reason_code
    delta_table >> dim_delta_data_check_row_count
    delta_table >> dim_delta_data_check_duplicate_records
    dim_offer_type >> dim_offer_type_data_check_row_count
    dim_offer_type >> dim_offer_type_data_check_duplicate_records
    dim_offer_discount >> dim_offer_discount_data_check_row_count
    dim_offer_discount >> dim_offer_discount_data_check_duplicate_records
    dim_offer_discount >> dim_offer_discount_data_check_open_history_items
    dim_offer_status >> dim_offer_status_data_check_row_count
    dim_offer_status >> dim_offer_status_data_check_duplicate_records
    dim_offer_status >> dim_offer_status_data_check_open_history_items
    load_teams >> finish_pipeline
    dim_offer_priceable_unit_data_check_row_count >> finish_pipeline
    dim_offer_priceable_unit_data_check_duplicate_records >> finish_pipeline
    dim_offer_status_data_check_new_value_status_code >> finish_pipeline
    dim_offer_status_data_check_new_value_reason_code >> finish_pipeline
    dim_delta_data_check_row_count >> finish_pipeline
    dim_delta_data_check_duplicate_records >> finish_pipeline
    dim_offer_type_data_check_row_count >> finish_pipeline
    dim_offer_type_data_check_duplicate_records >> finish_pipeline
    dim_offer_discount_data_check_row_count >> finish_pipeline
    dim_offer_discount_data_check_duplicate_records >> finish_pipeline
    dim_offer_discount_data_check_open_history_items >> finish_pipeline
    dim_offer_status_data_check_row_count >> finish_pipeline
    dim_offer_status_data_check_duplicate_records >> finish_pipeline
    dim_offer_status_data_check_open_history_items >> finish_pipeline
