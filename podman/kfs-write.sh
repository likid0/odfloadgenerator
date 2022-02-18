#!/bin/bash

HOST_PATH=/mnt/kfswrite
CEPH_TEST_COMP=fs
CEPH_TEST_TYPE=write
CEPH_PV_MOUNT_DIR=/mnt/pv
CEPH_TEST_SLEEP=1
CEPH_TEST_W_CACHE=False
CONTAINER_IMAGE=quay.io/ddomingu/ocsloadgeneratorroot

# Clean all the files in the CephFS volume

if [ -d ${HOST_PATH} ]
then
        rm -rf ${HOST_PATH}/*
fi

semanage fcontext -a -t container_file_t "${HOST_PATH}(/.*)?" 2>/dev/null
restorecon -R ${HOST_PATH}

podman run -d --name ocsloadgenerator-${CEPH_TEST_COMP}-${CEPH_TEST_TYPE} -v ${HOST_PATH}:${CEPH_PV_MOUNT_DIR} -e CEPH_TEST_COMP=${CEPH_TEST_COMP} -e CEPH_TEST_TYPE=${CEPH_TEST_TYPE} -e CEPH_TEST_SLEEP=${CEPH_TEST_SLEEP} -e CEPH_TEST_W_CACHE=${CEPH_TEST_W_CACHE} ${CONTAINER_IMAGE}
