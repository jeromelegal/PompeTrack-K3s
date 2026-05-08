FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip && \
    pip install -r /app/requirements.txt

COPY streamlit_admin.py /app/streamlit_admin.py

CMD ["streamlit", "run", "streamlit_admin.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
