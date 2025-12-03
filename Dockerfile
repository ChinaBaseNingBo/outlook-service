FROM python:3.9.6
WORKDIR /usr/local/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
EXPOSE 8000

CMD ["python", "-m", "src.app"]
