FROM python:3.9.5

ENV SCHEMA_FILE="schema.json"
ENV ROOT_FOLDER="/github/workspace"

WORKDIR /usr/src/app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["/usr/src/app/validate.py"]

ENTRYPOINT ["python3"]