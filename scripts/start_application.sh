#!/bin/bash
cd /home/ubuntu/agentic-api
source venv/bin/activate
export GROQ_API_KEY=$(aws ssm get-parameter --name "/agentic-api/GROQ_API_KEY" --with-decryption --query Parameter.Value --output text)
export TAVILY_API_KEY=$(aws ssm get-parameter --name "/agentic-api/TAVILY_API_KEY" --with-decryption --query Parameter.Value --output text)
export MONGODB_URL=$(aws ssm get-parameter --name "/agentic-api/MONGODB_URL" --with-decryption --query Parameter.Value --output text)
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > /var/log/agentic-api.log 2>&1 &