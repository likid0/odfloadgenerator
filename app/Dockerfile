FROM registry.redhat.io/ubi8/python-36
USER root 
COPY scripts/ .
COPY libraries/ .
#RUN pip install prometheus-client --no-index --user --find-links file:libraries/prometheus_client-0.8.0-py2.py3-none-any.whl
RUN pip install prometheus-client --find-links file:prometheus_client-0.8.0-py2.py3-none-any.whl
RUN pip install boto3 progressbar2
RUN chmod +x run-load.sh
USER nobody
CMD [ "./run-load.sh" ]
