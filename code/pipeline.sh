#!/bin/bash
# Full unattended pipeline; every stage skips work that is already saved. Run from the working folder:  setsid nohup code/pipeline.sh &
export EFFORT=${EFFORT:-0.25} RESTARTS=${RESTARTS:-2}
python3 -W ignore code/drawhq.py all >> data/drawhq.log 2>&1
code/sync.sh "Add tentacle-allowed maps" >> data/pipeline.log 2>&1
EVEN=1 python3 -W ignore code/drawhq.py all >> data/drawhq_even.log 2>&1
code/sync.sh "Add maps for the 50-50 states exercise" >> data/pipeline.log 2>&1
if [ "$(ls data/maps_hq | wc -l)" = 50 ] && [ "$(ls data/maps_hq_even | wc -l)" = 50 ] && [ ! -f data/results.json ]; then
  python3 -W ignore code/run.py > data/run.log 2>&1
  code/sync.sh "Add final game results" >> data/pipeline.log 2>&1
fi
