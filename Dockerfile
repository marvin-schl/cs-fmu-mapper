FROM continuumio/miniconda3


# Set working directory for package installation
RUN mkdir /cs-fmu-mapper
WORKDIR /cs-fmu-mapper

# Copy requirements file
COPY . .

# Install dependencies
RUN conda install -y -c conda-forge pyfmi && \
    pip install --no-cache-dir -r requirements.txt

<<<<<<< HEAD
# Install the current package
RUN pip install .

#Set workdir for custom app
WORKDIR /app

# remove sources
RUN rm -rf /cs-fmu-mapper
=======
# Copy the rest of the application
COPY cs_fmu_mapper .
COPY setup.py .
COPY requirements.txt .

# Install the current package
RUN pip install .

#remove sources
RUN  rm -rf /app/*
>>>>>>> d6d4cf97edfe59748cf85900ac5e98bc54ece1f3

# Set the default command
CMD ["/bin/bash"]
