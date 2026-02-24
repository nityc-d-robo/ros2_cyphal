#!/bin/bash
# setup_vcan.sh

IFACE=${1:-vcan0}

echo "Setting up $IFACE..."

if ! lsmod | grep -q vcan; then
    echo "Loading vcan kernel module..."
    sudo modprobe vcan
fi

if ! ip link show "$IFACE" > /dev/null 2>&1; then
    echo "Creating $IFACE..."
    sudo ip link add dev "$IFACE" type vcan
fi

echo "Bringing up $IFACE with CAN FD support..."
sudo ip link set "$IFACE" mtu 72
sudo ip link set up "$IFACE"

echo "Done. You can check it with 'ip link show $IFACE'"
