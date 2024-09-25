FROM continuumio/miniconda3


# Set working directory for package installation
RUN mkdir /cs-fmu-mapper
WORKDIR /cs-fmu-mapper

# Copy requirements file
COPY . .

# Install dependencies
RUN conda install -y -c conda-forge pyfmi && \
    pip install --no-cache-dir -r requirements.txt

# Install the current package
RUN pip install .

#Set workdir for custom app
WORKDIR /app

# remove sources
RUN rm -rf /cs-fmu-mapper

# Set the default command
CMD ["/bin/bash"]
