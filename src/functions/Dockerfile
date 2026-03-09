# ==============================================================================
# Dockerfile — Azure Functions (KB Ingestion Pipeline)
# ==============================================================================
# Custom container to support Playwright + Chromium for HTML→PDF rendering
# used by the Mistral Document AI converter (fn_convert_mistral).
# ==============================================================================

FROM mcr.microsoft.com/azure-functions/python:4-python3.11

ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true

WORKDIR /home/site/wwwroot

# Copy everything
COPY . .

# Install Python dependencies (workspace root pulls all member packages)
# Note: shared/ is included via root wheel (hatch.build.targets.wheel.packages)
RUN pip install --no-cache-dir . \
    ./fn_convert_cu \
    ./fn_convert_mistral \
    ./fn_convert_markitdown \
    ./fn_index

# Install Playwright Chromium with all required system libraries
RUN playwright install --with-deps chromium
