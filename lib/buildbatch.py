import argparse
import black
import os
import pathlib

from django import conf

from lib.baseclasses import (
    TableType,
    TaskOperator,
    Task,
    SQLDataCheckTask,
    SQLDataCheckParameter,
    todict,
)

from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from lib.helper import FileType, format_description
from lib.logger import ILogger, pop_stack
from lib.sql_helper import create_sql_file
from shutil import copy

__all__ = [
    "builddags",
]


def builddags(logger: ILogger, output_directory: str, config: dict) -> int:

    logger.info(f"batch files - {pop_stack()} STARTED".center(100, "-"))

    # for config file provided use the content of the JSON to create
    # the statements needed to be inserted into the template
    logger.info(f"building process - {config['name']}")

    tasks = []
    sub_process_list = []
    dependencies = []
    scripts = []

    # for each item in the task array, check the operator type and use this
    # to determine the task parameters to be used
    for t in config["tasks"]:
        task = Task(
            t.get("task_id"),
            t.get("operator"),
            t.get("parameters"),
            t.get("dependencies"),
            t.get("description"),
        )
        logger.info(f'creating task "{task.task_id}" - {pop_stack()}')
        if task.operator == TaskOperator.CREATETABLE.name:
            # for each task, add a new one to config["tasks"] with data check tasks.
            if (
                "block_data_check" not in task.parameters.keys()
                or not task.parameters["block_data_check"]
            ):
                data_check_tasks = create_data_check_tasks(
                    logger, task, config["properties"]
                )
                for d in data_check_tasks:
                    if not d in config["tasks"]:
                        config["tasks"].append(d)

            task.parameters = create_table_task(logger, task, config.get("properties"))

        elif task.operator == TaskOperator.TRUNCATETABLE.name:
            task.parameters = create_table_task(logger, task, config.get("properties"))

        sub_process_list.append(
            create_table_task(logger, task, config.get("properties"))
        )
        tasks.append(task.task_id)
        tasks.append(f"{task.task_id}.sql")

        dependencies.extend([(task.task_id, d) for d in task.dependencies])

    logger.info(f"creating template parameters")

    logger.info(f"populating templates")
    file_loader = FileSystemLoader("./templates")
    env = Environment(loader=file_loader)

    scr_template = env.get_template("template_scr.txt")
    scr_output = scr_template.render(
        job_id=config.get("name", "").lower(),
        created_date=datetime.now().strftime("%d %b %Y"),
        tasks=format_description(" ".join(tasks), "", FileType.SH),
        description=format_description(task.description, "Description", FileType.SH),
        scripts=format_description(" ".join(scripts), "", FileType.SH),
        cut=len(config.get("properties", {}).get("prefix")) + 1,
        sub_process_list=sub_process_list,
    )

    scr_file = f"{output_directory}{config['name']}.sh"
    with open(scr_file, "w") as outfile:
        outfile.write(scr_output)

    logger.info(f"Job file created: {config['name']}.sh")

    pct_template = env.get_template("template_pct.txt")
    pct_output = pct_template.render(
        job_id=config.get("name", "").lower(),
        created_date=datetime.now().strftime("%d %b %Y"),
    )

    pct_file = f"{output_directory}pct_{config['name']}.sh"
    with open(pct_file, "w") as outfile:
        outfile.write(pct_output).lower

    logger.info(f"Pop control file created: pct_{config['name']}.sh")

    logger.info(f"batch files {pop_stack()} COMPLETED SUCCESSFULLY".center(100, "-"))
    return 0


def create_data_check_tasks(logger: ILogger, task: Task, properties: dict) -> list:
    """
    This function creates a list of data check tasks for a given task

    Args:
      logger (ILogger): ILogger - this is the logger object that is passed to the function.
      task (Task): The task object that is being created.
      properties (dict): a dictionary of properties that are used to create the DAG.

    Returns:
      A list of data check tasks.
    """
    logger.info(f"{pop_stack()} STARTED".center(100, "-"))
    data_check_tasks = []

    table_keys = [
        field["name"]
        for field in task.parameters.get("source_to_target", [])
        if "pk" in field.keys()
    ]

    history_keys = [
        field["name"]
        for field in task.parameters.get("source_to_target", [])
        if "hk" in field.keys()
    ]

    logger.info(f"creating row count check")
    dataset = (
        task.parameters["destination_dataset"]
        if "destination_dataset" in task.parameters.keys()
        else properties["dataset_publish"]
    )
    table = task.parameters["destination_table"]
    row_count_check_task = SQLDataCheckTask(
        f"{task.parameters['destination_table']}_data_check_row_count",
        TaskOperator.DATACHECK,
        SQLDataCheckParameter(f"select count(*) from {dataset}.{table}"),
        [f"{task.task_id}"],
    )
    data_check_tasks.append(todict(row_count_check_task))

    # create task to check for duplicates on primary key - if primary key
    # fields specified in config.
    if len(table_keys) > 0:
        logger.info(f"creating duplicate data check")
        dupe_check_task = SQLDataCheckTask(
            f"{task.parameters['destination_table']}_data_check_duplicate_records",
            TaskOperator.DATACHECK,
            SQLDataCheckParameter(
                "sql/data_check_duplicate_records.sql",
                params={
                    "DATASET_ID": f"{task.parameters['destination_dataset']}"
                    if "destination_dataset" in task.parameters.keys()
                    else f"{properties['dataset_publish']}",
                    "FROM": f"{task.parameters['destination_table']}",
                    "KEY": f"{', '.join(table_keys)}",
                },
            ),
            [task.task_id],
        )
        data_check_tasks.append(todict(dupe_check_task))

    # create task to check for multiple open records - if primary key
    # fields specified in config.
    if len(table_keys) > 0 and task.parameters["target_type"] == TableType.HISTORY.name:
        logger.info(f"creating duplicate active history data check")
        dupe_check_task = SQLDataCheckTask(
            f"{task.parameters['destination_table']}_data_check_open_history_items",
            TaskOperator.DATACHECK,
            SQLDataCheckParameter(
                "sql/data_check_open_history_items.sql",
                params={
                    "DATASET_ID": f"{task.parameters['destination_dataset']}"
                    if "destination_dataset" in task.parameters.keys()
                    else f"{properties['dataset_publish']}",
                    "FROM": f"{task.parameters['destination_table']}",
                    "KEY": f"{', '.join(history_keys)}",
                },
            ),
            [task.task_id],
        )
        data_check_tasks.append(todict(dupe_check_task))

    logger.info(f"dag files {pop_stack()} COMPLETED SUCCESSFULLY".center(100, "-"))
    return data_check_tasks


def create_table_task(logger: ILogger, task: Task, properties: dict) -> dict:
    """
    It creates a SQL file that creates a table in the destination dataset

    Args:
      logger (ILogger): ILogger - this is the logger that is passed in from the main function.
      task (Task): the task object
      properties (dict): a dictionary of properties that are used in the script.
    """

    logger.info(f"{pop_stack()} STARTED".center(100, "-"))
    dataset_staging = properties["dataset_staging"]

    if not "sql" in task.parameters.keys():
        task.parameters["source_to_target"] = [
            field
            for field in task.parameters.get("source_to_target")
            if not field.get("name") in ["dw_created_dt", "dw_last_modified_dt"]
        ]
        file_path = create_sql_file(logger, task, dataset_staging=dataset_staging)

    outp = f"{task.task_id.upper()}|{task.task_id}'|Y'\\"

    logger.info(f"{pop_stack()} COMPLETED SUCCESSFULLY".center(100, "-"))
    return outp
