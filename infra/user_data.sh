#!/usr/bin/env bash
set -euxo pipefail

apt-get update
apt-get install -y docker.io git awscli python3 python3-pip
systemctl enable docker
systemctl start docker
usermod -aG docker ubuntu

mkdir -p /home/ubuntu/workforce-mlops
chown -R ubuntu:ubuntu /home/ubuntu/workforce-mlops
