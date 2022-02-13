#!/bin/bash
#check envs
if   [ -z ${CEPH_TEST_COMP} ] ||  [[ ${CEPH_TEST_COMP}  != 'rbd'  &&  ${CEPH_TEST_COMP} != 'fs' && ${CEPH_TEST_COMP} != 'object' ]] ; then
	echo "CEPH_TEST_COMP var not set correcty please use rbd, fs or object. example export CEPH_TEST_COMP=rbd, export CEPH_TEST_COMP=fs or CEPH_TEST_COMP=object" && exit 1
fi

if  [ -z "${CEPH_TEST_TYPE}" ] || [[ "${CEPH_TEST_TYPE}"  != 'read'  &&  "${CEPH_TEST_TYPE}" != 'write' ]] ; then
        echo "CEPH_TEST_TYPE var not set correctly please use read or write. example export CEPH_TEST_TYPE=read or export CEPH_TEST_TYPE=write " && exit 1
fi

#[ -z "${CEPH_PV_MOUNT_DIR}" ] && echo "CEPH_PV_MOUNT_DIR var not set please export it. Example export CEPH_PV_MOUNT_DIR=/mnt/pv" && exit 1

if [ "${CEPH_TEST_COMP}" == 'object' ] ; then
	[ -z ${S3_HOST} ] && echo "S3_HOST var not set please export it. example export S3_HOST=host.example.com" && exit 1
	[ -z ${S3_ACCESS_KEY} ] && echo "S3_ACCESS_KEY var not set please export it. example export S3_ACCESS_KEY=6JAXXXXXXXXXXXXXX78I" && exit 1
	[ -z ${S3_SECRET_KEY} ] && echo "S3_SECRET_KEY var not set please export it. example export S3_SECRET_KEY=OBzXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXMnB" && exit 1
	[ -z ${S3_BUCKET_NAME} ] && echo "S3_BUCKET_NAME var not set please export it. example export S3_BUCKET_NAME=test-bucket" && exit 1
fi

#run script
python workload-generator.py

