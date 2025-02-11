"""Script to run a simple example with Dask."""
import argparse
import time
from datetime import datetime

from dask.distributed import Client, progress

parser = argparse.ArgumentParser(description="A simple example script")
parser.add_argument('repetitions', type=int)
args = parser.parse_args()
repetitions = args.repetitions

client = Client(scheduler_file='dask_scheduler.json')
tic = time.time()

def slow_increment(x):
    time.sleep(1)
    return x + 1, str(datetime.now())

futures = client.map(slow_increment, range(46*repetitions))
progress(futures)

toc = time.time()
print(client)
print(f"\033[34mTime spent in {repetitions} repetitions: {toc-tic}\033[0m")
