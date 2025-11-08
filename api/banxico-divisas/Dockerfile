# Use AWS Lambda Python base image
FROM public.ecr.aws/lambda/python:3.11

# Install build dependencies for pandas/numpy
RUN yum install -y gcc gcc-c++ make && \
    yum clean all && \
    rm -rf /var/cache/yum

# Copy requirements.txt and install dependencies
COPY requirements.txt ${LAMBDA_TASK_ROOT}
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

# Copy function code
COPY lambda_function.py ${LAMBDA_TASK_ROOT}

# Set the CMD to your handler
CMD [ "lambda_function.handler" ]

