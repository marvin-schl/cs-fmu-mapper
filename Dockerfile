FROM continuumio/miniconda3

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN conda install -y -c conda-forge pyfmi && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY cs_fmu_mapper .
COPY setup.py .
COPY requirements.txt .

# Install the current package
RUN pip install .

#remove sources
RUN  rm -rf /app/*

# Set the default command
CMD ["/bin/bash"]
