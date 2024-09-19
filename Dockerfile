FROM continuumio/miniconda3

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN conda install -y -c conda-forge pyfmi && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .


# Install the current package
RUN pip install .

RUN  mkdir /tmp/app 
RUN  cp /app/main.py /tmp/app/
RUN  cp -r /app/example/* /tmp/app
RUN  rm -rf /app/*
RUN  mv /tmp/app/* /app/

# Set the default command
CMD ["/bin/bash"]