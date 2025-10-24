FROM python:3.11-slim
WORKDIR /

# Installer gsutil (Google Cloud SDK light)
RUN apt-get update && apt-get install -y curl && \
    curl -sSL https://sdk.cloud.google.com | bash -s -- --disable-prompts && \
    /root/google-cloud-sdk/install.sh --quiet && \
    apt-get clean

ENV PATH="/root/google-cloud-sdk/bin:${PATH}"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "updatedb.py"]
