FROM python:3.12-slim

# Set environment variables to prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    libxrender1 \
    libexpat1 \
    libxext6 \
    libx11-6 \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /usr/src/app

# The packages are installed before the code is copied, so a code change does not reinstall them
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

# Copy the current directory contents into the container at /usr/src/app
COPY . .

# The build fails when the vocabularies or generated files do not match the model's release
RUN python -m linkeddata check

# Copy entrypoint script
COPY entrypoint.sh /usr/src/app/entrypoint.sh
RUN chmod +x /usr/src/app/entrypoint.sh

# The database and the records repository are kept in /data (a volume). The database uses the rollback journal,
# which is safe when /data is on a network file system, such as GlusterFS on the cluster.
ENV PLATFORM_STATE=/data/state PLATFORM_RECORDS=/data/records PLATFORM_JOURNAL=delete

# Run as an unprivileged user
RUN useradd --create-home app && mkdir -p /data && chown app /data
VOLUME /data
USER app

# Define the entrypoint script
ENTRYPOINT ["/usr/src/app/entrypoint.sh"]
