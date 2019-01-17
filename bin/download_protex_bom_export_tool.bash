#!/bin/bash

# download the Protex bom export tool from a BD Hub server
export BD_URL=${1:-https://ec2-18-217-189-8.us-east-2.compute.amazonaws.com}

 wget ${BD_URL}/download/scan.protex.cli.zip --no-check-certificate