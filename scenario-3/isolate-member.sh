#!/bin/bash

tc qdisc add dev eth1 root netem loss 100%
#tc qdisc add dev eth2 root netem loss 100%
#tc qdisc add dev eth3 root netem loss 100%