FROM python:3.12-slim

WORKDIR /app

# Copy the whole azd service project, then run from the nested code dir where
# main.py + requirements.txt live (azd scaffolds the code under src/<name>/).
COPY . user_agent/
WORKDIR /app/user_agent/src/agent-framework-agent-with-remote-mcp-tools-responses

RUN if [ -f requirements.txt ]; then \
        pip install --no-cache-dir -r requirements.txt; \
    else \
        echo "No requirements.txt found"; \
    fi

EXPOSE 8088

CMD ["python", "main.py"]
