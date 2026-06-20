FROM python:3.13-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpcap-dev nmap git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY capture.py port_scan.py traffic_sniff.py .

# No USER directive: Scapy raw-socket capture requires the Python interpreter
# to run as root inside the container (Python cannot receive file-level
# capabilities). Host-level privilege is still restricted to CAP_NET_RAW /
# CAP_NET_ADMIN via Compose cap_add — never --privileged (D-03).
CMD ["python", "capture.py"]
