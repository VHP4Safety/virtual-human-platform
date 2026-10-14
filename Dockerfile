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

# Copy the current directory contents into the container at /usr/src/app
COPY . .

# Install any needed packages specified in requirements.txt
RUN pip install -r requirements.txt -r linkeddata/requirements.txt

# Copy entrypoint script
COPY entrypoint.sh /usr/src/app/entrypoint.sh
RUN chmod +x /usr/src/app/entrypoint.sh

# The database and the records repository are kept in /data (a volume)
ENV PLATFORM_STATE=/data/state PLATFORM_RECORDS=/data/records

# Run as an unprivileged user
RUN useradd --create-home app && mkdir -p /data && chown app /data
USER app

# Define the entrypoint script
ENTRYPOINT ["/usr/src/app/entrypoint.sh"]
