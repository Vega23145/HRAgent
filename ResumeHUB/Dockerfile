FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# resume_matcher: copy it in and install it too, e.g.
#   COPY resume_matcher /srv/resume_matcher_src
#   RUN pip install --no-cache-dir /srv/resume_matcher_src
COPY app ./app
RUN useradd -r -u 10001 hub && chown -R hub /srv
USER hub
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/healthz')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
