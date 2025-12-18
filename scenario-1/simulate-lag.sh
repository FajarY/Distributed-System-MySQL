#!/bin/bash

#Run in bridge
tc qdisc add dev eth1 root netem loss 40%