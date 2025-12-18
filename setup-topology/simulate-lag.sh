#!/bin/bash

#Run in bridge
tc qdisc add dev eth1 root netem delay 100ms loss 40%