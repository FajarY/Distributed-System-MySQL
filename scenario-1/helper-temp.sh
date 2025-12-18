#/bin/bash

#Iperf
iperf3 -s
iperf3 -c 192.168.100.2 -u -b 10G

#Lag simulation
tc qdisc add dev eth1 root netem loss 40%
tc qdisc del dev eth1 root
tc qdisc add dev eth1 root netem delay 100ms loss 40%
tc qdisc add dev eth1 root handle 1: tbf rate 2mbit burst 32kbit latency 100ms
tc qdisc add dev eth1 parent 1:1 handle 10: netem delay 100ms loss 1%

#Bridge utils
brctl show
brctl delbr br0