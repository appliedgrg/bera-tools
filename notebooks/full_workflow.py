"""
Provide a full workflow that runs the centerline, canopy and ground footprint tools.

usage: 
    python full_workflow.py [-f some.yml] [-p PARALLEL_MODE]

    PARALLEL_MODE: MULTIPROCESSING = 2
                   SLURM = 5
"""

import argparse
import configparser
import os
import sys
from pathlib import Path
from pprint import pprint

sys.path.append(Path(__file__).resolve().parents[1].as_posix())

import yaml
from beratools.core.algo_split_with_lines import split_with_lines

from beratools.core.algo_footprint_rel import line_footprint_rel
from beratools.core.constants import ParallelMode
from beratools.tools.centerline import centerline
from beratools.tools.line_footprint_absolute import line_footprint_abs
from beratools.tools.line_footprint_fixed import line_footprint_fixed

print = pprint

gdal_env = os.environ.get("GDAL_DATA")

processes = 2
verbose = False

def check_arguments():
    # Create the argument parser
    parser = argparse.ArgumentParser(description="Run the full workflow parameters.")
    
    # Make the YAML file optional by setting required=False
    parser.add_argument(
        '-f', '--file', 
        type=str, 
        required=False,  # This makes the file parameter optional
        help="Path to the YAML configuration file (optional)"
    )

    parser.add_argument(
        '-p', '--parallel', 
        type=int, 
        required=False,  # This makes the file parameter optional
        default=ParallelMode.MULTIPROCESSING,
        help="Parallel computing mode (optional)"
    )
    
    # Parse the arguments
    args = parser.parse_args()

    # Print out the arguments to debug
    print(f"Parsed arguments: {args}")
    return args

def print_message(message):
    print('-'*50)
    print(message)
    print('-'*50)

if __name__ == '__main__':
    script_dir = Path(__file__).parent
    args = check_arguments()

    # Access the parameters
    yml_file = args.file

    # Set default file
    if not yml_file:
        yml_file = script_dir.joinpath('params_config.yml')

    # Get available CPU cores
    processes = os.cpu_count()
    parallel_mode= ParallelMode.MULTIPROCESSING
    if args.parallel:
        parallel_mode = args.parallel

    # Print the received arguments (you can replace this with actual processing code)
    print(f"Cores: {processes}")
    print(f'Parallel mode: {parallel_mode}')
    print(f"Configuration file: {yml_file}")

    with open(yml_file) as in_params:
        params = yaml.safe_load(in_params)

    # Read config.ini to get the base directory
    config = configparser.ConfigParser()
    config.read(script_dir.joinpath('config.ini'))
    data_dir = config['Paths']['DATA_DIR']

    # Replace all occurrences of ${DATA_DIR} with the actual path
    for key, value in params.items():
        if isinstance(value, dict):  # nested dictionary
            for sub_key, sub_value in value.items():
                if isinstance(sub_value, str) and '${DATA_DIR}' in sub_value:
                    value[sub_key] = sub_value.replace('${DATA_DIR}', data_dir)
        elif isinstance(value, str) and '${DATA_DIR}' in value:
            params[key] = value.replace('${DATA_DIR}', data_dir)

    # centerline
    print_message("Starting centerline")
    args_centerline = params['args_centerline']
    args_centerline['processes'] = processes
    args_centerline['parallel_mode'] = parallel_mode
    print(args_centerline)
    centerline(**args_centerline)
    
    # canopy footprint abs
    # print_message("Starting canopy footprint abs")
    # args_footprint_abs = params["args_footprint_abs"]
    # args_footprint_abs['processes'] = processes
    # args_footprint_abs['parallel_mode'] = parallel_mode
    # print(args_footprint_abs)
    # line_footprint_abs(**args_footprint_abs)
    
    # canopy footprint relative
    print_message("Starting canopy footprint rel")
    args_footprint_rel = params["args_footprint_rel"]
    args_footprint_rel['processes'] = processes
    args_footprint_rel['parallel_mode'] = parallel_mode
    print(args_footprint_rel)
    line_footprint_rel(**args_footprint_rel)

    # ground footprint (grouped)
    print_message("Starting ground footprint fixed")
    args_footprint_fixed = params["args_footprint_fixed"]
    args_footprint_fixed['processes'] = processes
    args_footprint_fixed['parallel_mode'] = parallel_mode
    print(args_footprint_fixed)
    line_footprint_fixed(**args_footprint_fixed)

    # Split with lines
    # print_message("Splitting lines")
    # args_split_lines = params["args_split_lines"]
    # print(args_split_lines)
    # split_with_lines(**args_split_lines)

    # ground footprint (intersection)
    # print_message("Starting ground footprint intersection")
    # args_footprint_inter = params["args_footprint_inter"]
    # args_footprint_inter['processes'] = processes
    # args_footprint_inter['parallel_mode'] = parallel_mode
    # print(args_footprint_inter)
    # line_footprint_fixed(**args_footprint_inter)