# Pull base image
FROM python:3.11

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /code

# Install dependencies
COPY requirements.txt /code/
# setuptools<82 keeps pkg_resources, which CLIP's setup.py imports. Recent pip
# no longer applies PIP_CONSTRAINT to build dependencies, so use --build-constraint.
RUN echo 'setuptools<82' > /tmp/build-constraints.txt && \
    pip install --upgrade pip && \
    pip install --build-constraint /tmp/build-constraints.txt -r requirements.txt


# Install Node.js and npm
RUN curl -fsSL https://deb.nodesource.com/setup_16.x | bash - && \
    apt-get install -y nodejs


# Verify installations
RUN node -v && npm -v


# Copy project
COPY . /code/
