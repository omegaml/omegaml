#!/bin/bash
# native alternative to sphinx-autobuild with bash
#
# Works by polling the file system for changes every 10 seconds
#
# Whenever a build is triggered it will show a notification on start
# and another notification on being done.
#
# You can trigger a build by pressing ctrl-c.
# Exit by ctrl-z

INTERVAL=45

function serve() {
   (cd build/html && python -m http.server 8002 &)
}

function rebuild() {
    notify-send "sphinx: building docs... "
    make html
    notify-send "sphinx: docs are ready at http://localhost:8002"
}

function countdown() {
    count=0
    sleep=$1
    while [ $count -lt $1 ]; do
        echo -ne "sphinx livehtml: waiting another $((sleep - count)) seconds... Ctrl-C to build now\r"
        sleep 1
        count=$((count +1))
    done
}

function rebuild_serve() {
    rebuild
    serve
}

trap rebuild_serve INT

rebuild_serve

while true; do
  find source -mmin 0.2 -name "*rst" | egrep '.*' && rebuild_serve
  countdown $INTERVAL
done

