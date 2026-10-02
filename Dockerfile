# Dockerfile for the ACR artifact.
# Build (from the repository root, where this file lives):
#     docker build -t acr-artifact .
# See README "Running with Docker" for how to run it.

# Base image: Debian Linux with Python preinstalled.
# Use the same Python minor version you developed and tested with.
FROM python:3.13-slim

# - PYTHONDONTWRITEBYTECODE / PYTHONUNBUFFERED: no .pyc files, live log output
# - MPLBACKEND=Agg: matplotlib draws figures to files (a container has no screen)
# - MPLCONFIGDIR: a writable cache folder for matplotlib, whichever user runs the container
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/matplotlib

WORKDIR /app

# 0) Install tshark (command-line Wireshark), used to read the .pcap files.
#    - DEBIAN_FRONTEND=noninteractive and the debconf line answer the
#      installer's "allow non-root users to capture packets?" question ("no"),
#      which would otherwise stop the build waiting for input. Live capture is
#      not needed; tshark only reads existing pcap files here.
#    - --no-install-recommends and removing /var/lib/apt/lists keep the image small.
#    This layer comes first because it rarely changes, so Docker can cache it.
RUN echo "wireshark-common wireshark-common/install-setuid boolean false" | debconf-set-selections \
 && apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends tshark \
 && rm -rf /var/lib/apt/lists/* \
 && tshark --version | head -n 1

# 1) Install the Python dependencies.
#    They go into /app/scripts/venv because manager_volume_analysis.py and
#    manager_analysis.py call scripts/venv/bin/python directly.
#    requirements.txt is copied on its own first so Docker can reuse this
#    (slow) layer when only the code changes.
COPY scripts/requirements.txt scripts/requirements.txt
RUN python -m venv /app/scripts/venv \
 && /app/scripts/venv/bin/pip install --no-cache-dir --upgrade pip \
 && /app/scripts/venv/bin/pip install --no-cache-dir -r scripts/requirements.txt

# Make "python" and "pip" mean the venv versions from here on.
ENV PATH="/app/scripts/venv/bin:${PATH}"

# Fail the build right away if requirements.txt is missing a package the pipeline needs.
RUN python -c "import pandas, numpy, scipy, matplotlib, pyarrow, requests"

# 2) Copy the code and the small input files that ship with the repository.
#    Large data (parquets, pcaps, CSVs) is NOT built into the image: it is
#    downloaded at run time into data/, which is mounted from the host.
COPY scripts/ scripts/
COPY data/experiment_timings/ data/experiment_timings/
COPY data/reference/ data/reference/

# Commands run from scripts/, matching the paths used in the README.
WORKDIR /app/scripts

# With no command given, open a shell inside the container.
CMD ["bash"]
