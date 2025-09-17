# Use an official Python runtime as a parent image
FROM python:3.13-alpine

# Set the working directory
WORKDIR /app

# Copy the script to the container
COPY app.py .
COPY requirements.txt .

# Install dependencies
RUN pip install --upgrade pip --no-cache-dir
RUN pip install --no-cache-dir  -r requirements.txt

# Install SSH
RUN apk add --no-cache openssh git

# Confgure Git
RUN git config --global user.name "goodnotes2git-bot"

# Command to run the Python script
ENTRYPOINT [ "python", "app.py" ]