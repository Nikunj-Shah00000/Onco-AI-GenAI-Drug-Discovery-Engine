FROM continuumio/miniconda3:latest

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    build-essential \
    libboost-all-dev \
    && rm -rf /var/lib/apt/lists/*

# Install AutoDock Vina
RUN wget https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v1.2.5/vina_1.2.5_linux_x86_64 && \
    chmod +x vina_1.2.5_linux_x86_64 && \
    mv vina_1.2.5_linux_x86_64 /usr/local/bin/vina

# Install Python packages
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application code
COPY docking_worker.py .
COPY prepare_receptor.py .
COPY prepare_ligand.py .

# Entry point
CMD ["python", "docking_worker.py"]