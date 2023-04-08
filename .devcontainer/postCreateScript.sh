#!/bin/bash

sudo apt update
sudo apt install -y python-dev libpq-dev

pip3 install --user -r requirements.txt
