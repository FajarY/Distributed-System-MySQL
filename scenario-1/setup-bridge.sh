#!/bin/bash

#Run in bridge
apt-get update -y
apt-get install bridge-utils -y

brctl addbr br0
ip addr add 192.168.100.1/24 dev br0
brctl addif br0 eth1
brctl addif br0 eth2
brctl addif br0 eth3
brctl addif br0 eth4
ip link set br0 up

sysctl -w net.ipv4.ip_forward=1
iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE