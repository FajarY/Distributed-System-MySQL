#/bin/bash

#Iperf
iperf3 -s
iperf3 -c 192.168.100.2 -u -b 10G

#Lag simulation
tc qdisc add dev eth1 root netem loss 40%
tc qdisc del dev eth1 root

#Bridge utils
brctl show
brctl delbr br0