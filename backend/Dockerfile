FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN apt-get update \
	&& apt-get install -y --no-install-recommends libvulkan1 \
	&& rm -rf /var/lib/apt/lists/*
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY ./app ./app
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh
EXPOSE 8000
VOLUME /app/export
CMD ["/app/entrypoint.sh"]
