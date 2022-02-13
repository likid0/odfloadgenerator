# Workload generator for HA tests in OCS (converged and external Ceph cluster)

This project will store the python scripts to generate workloads (block, file and object) when performing HA tests in OCS (converged and external Ceph cluster).

There is a Dockerfile included to create a new container image containing the Python script to run the different IO workloads. There are 3 types of test available, We set the type of tests we want to run via environment files.

* Block (RBD):
  - Write: export envs like `CEPH_TEST_COMP=rbd` and `CEPH_TEST_TYPE=write`
  - Read: export envs like `CEPH_TEST_COMP=rbd` and `CEPH_TEST_TYPE=read`
* File (CephFS):
  - Write: export envs like `CEPH_TEST_COMP=fs` and `CEPH_TEST_TYPE=write`
  - Read: export envs like `CEPH_TEST_COMP=fs` and `CEPH_TEST_TYPE=read`
* Object (Noobaa or Ceph RadosGW):
  - Write (PUT): export envs like `CEPH_TEST_COMP=object` and `CEPH_TEST_TYPE=write`
  - Read (GET): export envs like `CEPH_TEST_COMP=object` and `CEPH_TEST_TYPE=read`
  - Mandatory envs when using object workloads, when using OCS we are using a OBC so there is no need to fill in the envs:
    - `S3_HOST=host.example.com`
    - `S3_ACCESS_KEY=6JAXXXXXXXXXXXXXX78I`
    - `S3_SECRET_KEY=OBzXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXMnB`
    - `S3_BUCKET_NAME=test-bucket`

There are other env vars available that we can set:

- All workloads:
  - `CEPH_TEST_SLEEP`: This var sets the amount of time to sleep between loop iterations.
  - `LOG_SECONDS`: This var sets the number of seconds where we consider an I/O operation is delayed.
- RBD and CephFS workloads:
  - `CEPH_PV_MOUNT_DIR`: This var sets where we are going to write the data and metadata during the test, the files get generated automatically depending on the kind of test.
  - `CEPH_TEST_R_CACHE`: If we set this var to False. We use the `POSIX_FADV_DONTNEED` flag during the read tests. [POSIX_FADV_DONTNEED INFO](https://insights.oetiker.ch/linux/fadvise.html)
  - `CEPH_TEST_W_CACHE`: If we set this var to False. We run a flush after each write.
  - `CEPH_TEST_TMP_DIR`: We can use this var to tell the script where to write the script logs, by default they are written into /tmp/ to avoid compiting for I/O.
- Object workloads:
  - `S3_PORT`: This var sets where the S3 server is listening for requests.
  - `S3_SECURE`: This var sets if HTTP/S should be used.
  - `S3_VERIFY_SSL`: This var sets if the validity of the TLS certificate should be verified.
  - `S3_AVG_ATTEMPTS`: This var sets the number of operations to calculate the request average time.


**NOTE:** The example is using the `nodeSelector: compute=true`. Before creating the deployments label the worker nodes appropiately or remove the `nodeSelector` section from the yaml file.

```
$ for node in $(oc get nodes -l node-role.kubernetes.io/worker --no-headers=true -o name);do oc label $node compute="true";done
```

## Block (RBD)

* Write:
  - Inside an infinite loop, we write a line per iteration.
  - If the write I/O elapsed time is greater than `LOG_SECONDS` second/s, we log the operation.
  - Ideally, we need to perform our writes in a Persistent Volume provided by OCS.

* Read:
  - First, we create a new file. Ideally, this file is stored in a Persistent Volume provided by OCS.
  - Inside an infinite loop, we read the file we have just created per iteration.
  - If the read I/O elapsed time is greater than `LOG_SECONDS` second/s, we log the operation.

## File (CephFS)

* Write:
  - Open a file at the beginning, this is for data testing, we don't want to be reading the metadata all the time.
  - Inside an infinite loop:
    - Create a new metadata file, this will talk directly with the Ceph MDS servers.
    - In our data file we previously opened, write a line per iteration, this will talk directly with the Ceph OSD servers.
    - Delete the metadata file, this will talk directly with the Ceph MDS servers.
  - If any I/O operation (data and metadata) elapsed time is greater than `LOG_SECONDS` second/s, we log the operation.
    - If any operation takes longer than 60 seconds it will get cancelled and report to the logs.
  - Ideally, we need to perform our writes in a Persistent Volume provided by OCS.

* Read:
  - Open a file at the beginning, this is for data testing, we don't want to be reading the metadata all the time.
  - Create a new metadata file, this will talk directly with the Ceph MDS servers.
  - Inside an infinite loop:
    - In our data file, read the whole file, this will talk directly with the Ceph OSD servers.
    - Perform an stat operation in the metadata file, this will talk directly with the Ceph MDS servers.
  - If any I/O operation (data and metadata) elapsed time is greater than `LOG_SECONDS` second/s, we log the operation.
    - If any operation takes longer than 60 seconds it will get cancelled and report to the logs.
  - Ideally, we need to perform all I/O operations in a Persistent Volume provided by OCS.

## Object (Noobaa or Ceph RadosGW)

* Write (PUT):
  - Calculate the average response time and create the bucket if the bucket does not exist.
  - Create a 1KB file.
  - Inside an infinite loop:
    - Upload to the S3 server the file we created in the initial step.
    - If the PUT operation elapsed time is greater than `LOG_SECONDS` second/s, we log the operation.

* Read (GET):
  - Calculate the average response time and create the bucket if the bucket does not exist.
  - Create a 1KB file.
  - Upload the file we have created in the previous step.
  - Inside an infinite loop:
    - Download from the S3 server the file we created in the initial step.
    - If the GET operation elapsed time is greater than `LOG_SECONDS` second/s, we log the operation.
