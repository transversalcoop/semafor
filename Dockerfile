FROM python:3.12

WORKDIR /code

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

COPY Pipfile Pipfile.lock /code/
RUN pip install pipenv && pipenv install --system

COPY . /code/
