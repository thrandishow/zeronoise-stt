FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml /app/
RUN pip install uv
RUN uv sync

COPY . /app/

CMD [ "uvicorn","src.main:app", "--reload"]

