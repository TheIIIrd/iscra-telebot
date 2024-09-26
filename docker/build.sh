#!/usr/bin/env sh

###
# Image name is passed as first positional argument to this script
###

docker build -t $1 . -f docker/Dockerfile
docker push $1
