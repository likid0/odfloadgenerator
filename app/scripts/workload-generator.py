#!/usr/bin/env python
# Generates load to test OCS HA.
#
# Author/s:
#   Daniel Dominguez <ddomingu@redhat.com>
#   Daniel Parkes <dparkes@redhat.com>
#   Raul Mahiques <rmahique@redhat.com>
#

# Example usage:
#   export CEPH_TEST_COMP=fs
#   export CEPH_TEST_TYPE=read
#   python3 workload-generator.py

import re
import boto3
from botocore.exceptions import ClientError
import progressbar
import os
import sys
import datetime
from datetime import timedelta
import traceback
import socket
import threading
from threading import Thread
#from prometheus_client import start_http_server, Summary, Info
import random
import time
from time import sleep
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# class taken from: https://stackoverflow.com/questions/6893968/how-to-get-the-return-value-from-a-thread-in-python  author unknown
class ThreadWithReturnValue(Thread):
    def __init__(self, group=None, target=None, name=None,
                 args=(), kwargs={}, Verbose=None):
        Thread.__init__(self, group, target, name, args, kwargs)
        self._return = None


    def run(self):
        if self._target is not None:
            self._return = self._target(*self._args,
                                                **self._kwargs)


    def join(self, *args):
        Thread.join(self, *args)
        return self._return



class WorkloadGenerator:
    def __init__(self, t_component, t_type, t_r_cache, t_w_cache, t_tmp_dir, t_timeout = 60, t_sleep = '0.001'):
        self.t_component  = t_component
        self.t_type       = t_type
        self.t_r_cache    = self.str2bool(t_r_cache)
        self.t_w_cache    = self.str2bool(t_w_cache)
        self.t_tmp_dir    = t_tmp_dir
        self.t_timeout    = t_timeout
        self.t_sleep      = float(t_sleep)
        # This is the number of iterations it will skip before writting to the application logs (a low number will cause a lot of unnecessary IO on the local filesystem).
        self.tmp_iter     = 100
        self.file_name=f'{self.t_tmp_dir}ceph_{t_type}_workload.txt'
        self.object_name=os.path.basename(self.file_name)
        # create the variable for prometheus info
        # Next version


    def str2bool(self, v):
        if not isinstance(v, bool):
            return v.lower() in ("yes", "true", "t", "1")
        else:
            return v

    def object_calculate_avg_response_time(self, s3client, s3_bucket_name, s3_avg_attempts):
        if (int(s3_avg_attempts) <= 100):
            print(f'Calculating avg response time. Number of S3 operations to calculate the average time: {s3_avg_attempts}', flush=True)
        else:
            s3_avg_attempts=100
            print(f'Parameter S3_AVG_ATTEMPTS too high. Calculating avg response time. Number of S3 operations to calculate the average time: {s3_avg_attempts}', flush=True)
        # Create initial object of 1KB at CEPH_TEST_TMP_DIR
        # As we want to perform as many operations as possible do not offer the possibility to the user to configure this parameter. If we specify bigger values (such as 100MB), PUT and GET operations will last a lot of time.
        with open(self.file_name,'w') as f:
            num_chars = 1024
            f.write('a' * num_chars)
        s3client.upload_file(self.file_name, s3_bucket_name, self.object_name)
        bar = progressbar.ProgressBar(maxval=int(s3_avg_attempts), widgets=[progressbar.Bar('=', '[', ']'), ' ', progressbar.Percentage()])
        bar.start()
        sum_time=0
        for i in range(int(s3_avg_attempts)):
            initial_time = datetime.datetime.now()
            if (self.t_type == 'write'):
                s3client.upload_file(self.file_name, s3_bucket_name, self.object_name)
            elif (self.t_type == 'read'):
                s3client.download_file(s3_bucket_name, self.object_name, self.file_name)
            final_time = datetime.datetime.now()
            elapsed_microsec = self.get_microsec(initial_time, final_time)
            sum_time=sum_time + elapsed_microsec
            bar.update(i+1)
        bar.finish()
        avg_time=int(sum_time/int(s3_avg_attempts))
        avg_time_hr_format=str(timedelta(microseconds=avg_time))
        print(f'Average S3 operation time calculated: {avg_time} microsec. Human readable format: {avg_time_hr_format}. Please set the parameter LOG_SECONDS accordingly')

    def get_microsec(self, initial_time, final_time):
        elapsed_time = final_time - initial_time
        elapsed_microsec = (elapsed_time.days * 86400000000) + (elapsed_time.seconds * 1000000) + (elapsed_time.microseconds)
        return elapsed_microsec


    def return_message(self, mytime, t_component, t_type, i, msgType, elapsed_microsec = 0, d_o_m = 'data'):
                    if   msgType == 1:
                        return f'{mytime} - {ocpId} - {t_component} - {t_type}: File created for {d_o_m} testing.\n'
                    elif msgType == 2:
                        return f'{mytime} - {ocpId} - {t_component} - {t_type}: {t_timeout} seconds timeout during test number {i} for {d_o_m}.\n'
                    elif msgType == 3:
                        return f'{mytime} - {ocpId} - {t_component} - {t_type}: Elapsed (microseconds): {elapsed_microsec}\n{mytime} - {ocpId} - {t_component} - {t_type} - {d_o_m}: Iteration number: {i}.\n'
                    else:
                        return f'{mytime} - {ocpId} - {t_component} - {t_type}: Iteration number: {i}.\n'


    def generate_load(self, workload_file, o_type, i, msgType = 0, elapsed_microsec = 0, s3client = None, perm = False, d_o_m = 'data', fperm = None):
        initial_time = datetime.datetime.now()
        if s3client != None:
            if o_type == "r":
                s3client.download_file(s3_bucket_name, self.object_name, self.file_name)
            elif o_type == "w":
                s3client.upload_file(self.file_name, s3_bucket_name, self.object_name)
            e = i % self.tmp_iter
            if e == 0:
                self.generate_load(f'{self.t_tmp_dir}ceph_{o_type}_workload.log','a', i)
        else:
            if perm:
                if o_type == "r":
                    # Python reads all the metadata and stores it in memory once we open the object, if we don't want this we advice the kernel to not cache this.
                    if not self.t_r_cache:
                        os.posix_fadvise(fperm.fileno(), 0, os.fstat(fperm.fileno()).st_size, os.POSIX_FADV_DONTNEED)
                    sentence = fperm.read()
                    e = i % self.tmp_iter
                    if e == 0:
                        self.generate_load(f'{t_tmp_dir}ceph_{o_type}_workload.log','a', i)
                if o_type == "a" or o_type == "w":
                    mymsg = self.return_message(str(initial_time), t_component, t_type, i, msgType, elapsed_microsec, d_o_m)
                    fperm.write(mymsg)
                    if not self.t_w_cache:
                        fperm.flush()
            else:
                with open(workload_file, o_type) as f:
                    if o_type == "r":
                        # Python reads all the metadata and stores it in memory once we open the object, if we don't want this we advice the kernel to not cache this.
                        if not self.t_r_cache:
                            os.posix_fadvise(f.fileno(), 0, os.fstat(f.fileno()).st_size, os.POSIX_FADV_DONTNEED)
                        sentence = f.read()
                        e = i % self.tmp_iter
                        if e == 0:
                            self.generate_load(f'{t_tmp_dir}ceph_{o_type}_workload.log','a', i)
                    if o_type == "a" or o_type == "w":
                        mymsg = self.return_message(str(initial_time), t_component, t_type, i, msgType, elapsed_microsec, d_o_m)
                        f.write(mymsg)
                        if not self.t_w_cache:
                            f.flush()
        return initial_time, datetime.datetime.now()


    def check_time(self, initial_time, final_time, d_type, o_type, i, sec, d_o_m = 'data'):
        microsec_limit = sec * 1000000
        elapsed_microsec = self.get_microsec(initial_time, final_time)
        if ( elapsed_microsec > microsec_limit ):
            current_time = datetime.datetime.now()
            elapsed_sec = elapsed_microsec / 1000000
            print(f'{str(current_time)} - {ocpId} - {t_component} - {t_type} - Iteration number: {i}. Elapsed {d_type} {o_type} {d_o_m} file (seconds): {int(elapsed_sec)} - elapsed_microsec: {elapsed_microsec}', flush=True)


    def initial_file_creation(self, data_workload_file, metadata_workload_file=''):
        if metadata_workload_file is not '':
            self.generate_load(metadata_workload_file, 'w', 0, 1, 0, None, False, 'metadata')
        self.generate_load(data_workload_file, 'w', 0, 1)


    def rbd_read_generate_workload(self, data_workload_file, metadata_workload_file):
        self.initial_file_creation(str(data_workload_file))
        i = 0
        while True:
            initial_time = final_time = ''
            loop_iteration_initial_time = datetime.datetime.now()
            try:
                t = ThreadWithReturnValue(target=self.generate_load, args=(data_workload_file, "r", i))
                t.start()
                initial_time, final_time = t.join(t_timeout)
            except:
                initial_time = loop_iteration_initial_time
                final_time = datetime.datetime.now()
                self.generate_load(f'{t_tmp_dir}ceph_rbd_read_data_workload.log','a', i, 2)
                pass
            self.check_time(initial_time, final_time, 'data', t_type, i, log_seconds)
            i = i + 1
            sleep(self.t_sleep)


    def rbd_write_generate_workload(self, data_workload_file, metadata_workload_file):
        i = 0
        elapsed_microsec = 0
        while True:
            loop_iteration_initial_time = datetime.datetime.now()
            initial_time = final_time = ''
            try:
                t = ThreadWithReturnValue(target=self.generate_load, args=(data_workload_file, "a", i, 3, elapsed_microsec))
                t.start()
                initial_time, final_time = t.join(t_timeout)
            except:
                initial_time = loop_iteration_initial_time
                final_time = datetime.datetime.now()
                self.generate_load(f'{t_tmp_dir}ceph_rbd_write_data_workload.log','a', i, 2)
                pass
            elapsed_microsec = self.get_microsec(initial_time, final_time)
            self.check_time(initial_time, final_time, 'data', t_type, i, log_seconds)
            i = i + 1
            sleep(self.t_sleep)


    def metadata_writes(self, metadata_workload_file, i, fperm = None):
        metadata_workload_file = f'{metadata_workload_file}_{i}'
        initial_time, final_time = self.generate_load(metadata_workload_file, "w", i, 0, 0, None, False, 'metadata')
        self.check_time(initial_time, final_time, 'metadata', 'delete', i, log_seconds, 'metadata')
        # Delete the file created, this should talk directly with the MDS servers
        initial_time = datetime.datetime.now()
        os.remove(metadata_workload_file)
        final_time = datetime.datetime.now()
        self.check_time(initial_time, final_time, 'metadata', 'delete', i, log_seconds, 'metadata')


    def data_writes(self, data_workload_file, i, fperm = None):
        # In the data file, insert a new line. This should talk directly with the OSDs.
        initial_time, final_time = self.generate_load(data_workload_file, "a", i, 0, 0, None, True, 'data', fperm)
        elapsed_microsec = self.get_microsec(initial_time, final_time)
        fperm.write(f'{ocpId} - {t_component} - {t_type} - data: Elapsed (microseconds): {int(elapsed_microsec)}\n')
        if not self.t_w_cache:
            fperm.flush()
        self.check_time(initial_time, final_time, 'data', t_type, i, log_seconds)


    def fs_write_generate_workload(self, data_workload_file, metadata_workload_file):
        i = 0
        elapsed_microsec = 0
        try:
            t_typem = 'a'
            # This can be improved in the next version
            # Due to how ceph works we want to open a file at the start of the process so we interact later on with the metadata part which is handled by osd primarely.
            fperm = open(data_workload_file, t_typem)
            while True:
                # Creating new file, this should talk directly with the MDS servers, this is the case of the metadata_writes, for data_writes we keep a file open to not be affected
                loop_iteration_initial_time = datetime.datetime.now()
                initial_time = final_time = ''
                try:
                    n = 0
                    t = {}
                    for task in [[self.metadata_writes, metadata_workload_file], [self.data_writes, data_workload_file]]:
                        t[n] = ThreadWithReturnValue(target=task[0], args=(task[1], i, fperm))
                        t[n].start()
                        n = n + 1
                    for key in t:
                        try:
                            t[key].join(t_timeout)
                        except RuntimeError as e:
                            print(f'Could not join or check the time: {e}')
                            initial_time = loop_iteration_initial_time
                            final_time = datetime.datetime.now()
                            self.generate_load(f'{t_tmp_dir}ceph_{t_type}_workload.log','a', i, 2)
                except RuntimeError as e:
                    print(f'Somethings wrong: {e}')
                    for key in t:
                        try:
                            t[key].join(t_timeout)
                        except RuntimeError as e:
                            print(f'Could not join or check the time: {e}')
                            initial_time = loop_iteration_initial_time
                            final_time = datetime.datetime.now()
                            self.generate_load(f'{t_tmp_dir}ceph_{t_type}_workload.log','a', i, 2)
                i = i + 1
                sleep(self.t_sleep)
                if final_time and initial_time:
                    self.check_time(initial_time, final_time, 'data', t_type, i, log_seconds)
        finally:
            fperm.close()


    def fs_read_generate_workload(self, data_workload_file, metadata_workload_file):
        i = 0
        # First we want to check if metadata reads are working properly. To do so, we stat a file stored in CephFS
        # Creating new file, this should talk directly with the MDS servers
        self.initial_file_creation(str(data_workload_file), str(metadata_workload_file))
        t_typem = 'r'
        # This can be improved in the next version
        try:
            # Due to how ceph works we want to open a file at the start of the process so we interact later on with the metadata part which is handled by osd primarely.
            fperm = open(data_workload_file, t_typem)
            while True:
                n = 0
                t = {}
                loop_iteration_initial_time = datetime.datetime.now()
                initial_time = final_time = ''
                try:
                    t[n] = ThreadWithReturnValue(target=self.generate_load, args=(data_workload_file, "r", i, None, None, None, True, 'data', fperm))
                    t[n].start()
                    for key in t:
                        try:
                            initial_time, final_time = t[key].join(t_timeout)
                            self.check_time(initial_time, final_time, 'data', t_type, i, log_seconds)
                        except:
                            print(f'Could not join or checking the time: {n}')
                            initial_time = loop_iteration_initial_time
                            final_time = datetime.datetime.now()
                            self.generate_load(f'{t_tmp_dir}ceph_{t_type}_workload.log','a', i, 2)
                            self.check_time(initial_time, final_time, 'data', t_type, i, log_seconds)
                finally:
                    initial_time = datetime.datetime.now()
                    # Stat the file created, this should talk directly with the MDS servers
                    os.stat(metadata_workload_file)
                    final_time = datetime.datetime.now()
                    self.check_time(initial_time, final_time, 'metadata', 'stat file', i, log_seconds)
                i = i + 1
                sleep(self.t_sleep)
        finally:
            fperm.close()

    def object_write_generate_workload(self, data_workload_file, metadata_workload_file):
        i = 0
        s3client = self.init_s3client()
        while True:
            initial_time, final_time = self.generate_load(self.file_name, "w", i, 0, 0, s3client)
            self.check_time(initial_time, final_time, 'put', t_type, i, log_seconds)
            i = i +1
            sleep(self.t_sleep)

    def object_read_generate_workload(self, data_workload_file, metadata_workload_file):
        i = 0
        s3client = self.init_s3client()
        while True:
            initial_time, final_time = self.generate_load(self.file_name, "r", i, 0, 0, s3client)
            self.check_time(initial_time, final_time, 'get', t_type, i, log_seconds)
            i = i +1
            sleep(self.t_sleep)

    def init_s3client(self):
        if self.str2bool(s3_secure):
            s3_endpoint='https://'+s3_host+':'+s3_port
        else:
            s3_endpoint='http://'+s3_host+':'+s3_port
        s3client = boto3.client('s3', use_ssl=self.str2bool(s3_secure), verify=self.str2bool(s3_verify_ssl), endpoint_url=s3_endpoint, aws_access_key_id=s3_access_key, aws_secret_access_key=s3_secret_key)
        return s3client


    def main(self):
        starting_time = datetime.datetime.now()
        if t_component == 'object':
            #s3client = boto3.client('s3', use_ssl=self.s3_secure, verify=self.s3_verify_ssl, endpoint_url=self.s3_endpoint, aws_access_key_id=s3_access_key, aws_secret_access_key=s3_secret_key)
            #s3client.create_bucket(Bucket=s3_bucket_name)
            s3client = self.init_s3client()
            #s3client.create_bucket(Bucket=s3_bucket_name)
            self.object_calculate_avg_response_time(s3client, s3_bucket_name, s3_avg_attempts)
        print(f'{str(starting_time)} - {ocpId} - {t_component} - {t_type}: Starting workload generator.\n\tUsing file/s: {data_workload_file} {metadata_workload_file}', flush=True)
        print(f'{str(starting_time)} - {ocpId} - {t_component} - {t_type}: All I/O operations longer than {log_seconds} second/s will be logged here :)', flush=True)
        launchme = getattr( self, f"{t_component}_{t_type}_generate_workload")
        launchme(data_workload_file, metadata_workload_file)

if __name__ == '__main__':
    # define valid values
    node_id     = socket.gethostname()
    ocpId       = '-'.join(node_id.split('-')[-2:])
    t_type  = t_component = s3_access_key = s3_secret_key = s3_endpoint = ''

    # List of valid components to test
    v_component = ['rbd', 'fs', 'object']
    # list of valid type of operations
    v_type      = ['read', 'write']
    # Thread execution timeout
    t_timeout   = 60
    # load environmental variables
    if 'CEPH_TEST_COMP' in os.environ:
        t_component = os.environ['CEPH_TEST_COMP'].lower()
    if 'CEPH_TEST_TYPE' in os.environ:
        t_type = os.environ['CEPH_TEST_TYPE'].lower()
    # With this we define the temporary folder for the internal logs, it must not be hosted by ceph, or at least not part of what is being tested.
    if 'CEPH_TEST_TMP_DIR' in os.environ:
        t_tmp_dir = os.environ['CEPH_TEST_TMP_DIR'].lower()
    else:
        # By default we cache the reads (or the current OS behaviour)
        t_tmp_dir = '/tmp/'
    if 'CEPH_TEST_R_CACHE' in os.environ:
        t_r_cache = os.environ['CEPH_TEST_R_CACHE'].lower()
    else:
        # By default we cache the reads (or the current OS behaviour)
        t_r_cache = 'true'
    if 'CEPH_TEST_W_CACHE' in os.environ:
        t_w_cache = os.environ['CEPH_TEST_W_CACHE'].lower()
    else:
        # By default we use the buffers for writes
        t_w_cache = 'true'
    if 'CEPH_TEST_SLEEP' in os.environ:
        t_sleep = os.environ['CEPH_TEST_SLEEP'].lower()
    else:
        # by default we git it 0.001 second, this is to reduce the load on servers as we are testing the HA not performance,
        # at the time of writting this there is a FS cache of 4MB which means you won't see the file content being updated until the amount of
        # data reaches that, at which point it will dump the content and will become visible to others.
        t_sleep = '0.001'
    if not t_component in v_component:
        print(f"ERROR: Invalid or undefined test component: \"{t_component}\"\n\tValid components are: {', '.join(v_component)}", flush=True)
        exit(1)
    if not t_type in v_type:
        print(f"ERROR: Invalid or undefined test type: \"{t_type}\"\n\tValid types are: {', '.join(v_type)}", flush=True)
        exit(1)
    # With this option we define the mountpoint for the ceph storage
    if 'CEPH_PV_MOUNT_DIR' in os.environ:
        data_workload_file     = f'{os.getenv("CEPH_PV_MOUNT_DIR")}/{t_component}_{t_type}_{node_id}-data.log'
        metadata_workload_file = f'{os.getenv("CEPH_PV_MOUNT_DIR")}/{t_component}_{t_type}_{node_id}-metadata.log'
    else:
        data_workload_file     = f'/mnt/pv/{t_component}_{t_type}_{node_id}-data.log'
        metadata_workload_file = f'/mnt/pv/{t_component}_{t_type}_{node_id}-metadata.log'
    if 'S3_PORT' in os.environ:
        s3_port = os.environ['S3_PORT'].lower()
    else:
        # by default we use HTTPS port
        s3_port = '443'
    if 'S3_SECURE' in os.environ:
        s3_secure = os.environ['S3_SECURE'].lower()
    else:
        # by default connection is secure using HTTPS
        s3_secure = True
    if 'S3_VERIFY_SSL' in os.environ:
        s3_verify_ssl = os.environ['S3_VERIFY_SSL'].lower()
    else:
        # by default we verify SSL certificates
        s3_verify_ssl = True
    if 'S3_AVG_ATTEMPTS' in os.environ:
        s3_avg_attempts = os.environ['S3_AVG_ATTEMPTS'].lower()
    else:
        # by default we have 10 operations to calculate the average time
        s3_avg_attempts = 10
    if 'LOG_SECONDS' in os.environ:
        log_seconds = int(os.environ['LOG_SECONDS'].lower())
    else:
        # by default we log operations greater than 1 second
        log_seconds = 1
    if t_component == 'object':
        if 'S3_HOST' in os.environ:
            s3_host = os.getenv('S3_HOST')
        else:
            print(f"ERROR: S3_HOST is not defined", flush=True)
            exit(1)
        if 'S3_ACCESS_KEY' in os.environ:
            s3_access_key = os.getenv('S3_ACCESS_KEY')
        else:
            print(f"ERROR: S3_ACCESS_KEY is not defined", flush=True)
            exit(1)
        if 'S3_SECRET_KEY' in os.environ:
            s3_secret_key = os.getenv('S3_SECRET_KEY')
        else:
            print(f"ERROR: S3_SECRET_KEY is not defined", flush=True)
            exit(1)
        if 'S3_BUCKET_NAME' in os.environ:
            s3_bucket_name = os.getenv('S3_BUCKET_NAME')
        else:
            print(f"ERROR: S3_BUCKET_NAME is not defined", flush=True)
            exit(1)
    # start the web server for prometheus
    #start_http_server(8000)
    workload_generator = WorkloadGenerator(t_component.upper(), t_type, t_r_cache, t_w_cache, t_tmp_dir, t_timeout, t_sleep)
    workload_generator.main()
